from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


@dataclass(slots=True)
class DataContractIssue:
    severity: str
    code: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DataContractResult:
    passed: bool
    issues: list[DataContractIssue]
    summaries: dict[str, Any]

    def issue_counts(self) -> dict[str, int]:
        counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts


def load_contract(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    if not isinstance(contract, dict):
        raise ValueError(f"data contract must be a mapping: {path}")
    return contract


def validate_corrected_bundle(bundle_dir: Path, contract_path: Path) -> DataContractResult:
    bundle_dir = Path(bundle_dir).resolve()
    contract_path = Path(contract_path).resolve()
    contract = load_contract(contract_path)

    issues: list[DataContractIssue] = []
    summaries: dict[str, Any] = {
        "contract": {
            "contract_name": contract.get("contract_name"),
            "contract_version": contract.get("contract_version"),
            "bundle_type": contract.get("bundle_type"),
            "path": str(contract_path),
        },
        "bundle_dir": str(bundle_dir),
        "files": {},
        "date_ranges": {},
        "non_null_counts": {},
        "universe_columns": {},
        "factor_columns": {},
        "common_dates": {},
        "returns_oc_reconciliation": {},
        "returns_cc_diagnostic": {},
        "patch_table": {},
        "file_hashes": {},
        "ticker_summary_rows": [],
        "notes": [
            "returns_cc.csv is treated as the canonical predictor return file and is not recomputed from adjusted prices.",
            "returns_oc_jp.csv is reconciled against close_prices_adj.csv / open_prices_adj.csv - 1 within the configured tolerance.",
        ],
    }

    if not bundle_dir.exists():
        _add_issue(
            issues,
            "ERROR",
            "bundle_dir_missing",
            "Bundle directory does not exist.",
            {"bundle_dir": str(bundle_dir)},
        )
        return _finalize_result(issues, summaries)

    if not bundle_dir.is_dir():
        _add_issue(
            issues,
            "ERROR",
            "bundle_dir_not_directory",
            "Bundle path is not a directory.",
            {"bundle_dir": str(bundle_dir)},
        )
        return _finalize_result(issues, summaries)

    summaries["file_hashes"] = _hash_bundle_files(bundle_dir)

    file_map = dict(contract.get("files", {}))
    required_files = set(contract.get("required_files", []))
    optional_files = set(contract.get("optional_files", []))
    date_list_keys = set(contract.get("date_list_keys", []))
    weekend_check_keys = set(contract.get("weekend_check_keys", []))
    table_keys = [
        key
        for key, filename in file_map.items()
        if key not in date_list_keys and key != "patch_table" and str(filename).lower().endswith(".csv")
    ]

    loaded_tables: dict[str, pd.DataFrame] = {}
    loaded_dates: dict[str, pd.DatetimeIndex] = {}

    for filename in sorted(required_files | optional_files):
        path = bundle_dir / filename
        entry = {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
        }
        summaries["files"][filename] = entry
        if filename in required_files and not path.exists():
            _add_issue(
                issues,
                "ERROR",
                "required_file_missing",
                "Required file is missing.",
                {"file": filename},
            )

    for key in table_keys:
        filename = file_map[key]
        path = bundle_dir / filename
        if not path.exists():
            continue
        frame = _read_table_csv(path, filename, issues)
        if frame is None:
            continue
        loaded_tables[key] = frame
        summaries["files"][filename]["row_count"] = int(frame.shape[0])
        summaries["files"][filename]["column_count"] = int(frame.shape[1])
        summaries["date_ranges"][filename] = _date_summary(
            frame.index,
            check_weekends=key in weekend_check_keys,
            issues=issues,
            file_name=filename,
        )
        summaries["non_null_counts"][filename] = _non_null_summary(frame)

    for key in date_list_keys:
        filename = file_map[key]
        path = bundle_dir / filename
        if not path.exists():
            continue
        dates = _read_date_list_csv(path, filename, issues)
        if dates is None:
            continue
        loaded_dates[key] = dates
        summaries["files"][filename]["row_count"] = int(len(dates))
        summaries["files"][filename]["column_count"] = 1
        summaries["date_ranges"][filename] = _date_summary(
            dates,
            check_weekends=False,
            issues=issues,
            file_name=filename,
        )

    patch_cfg = contract.get("patch_table", {})
    patch_key = patch_cfg.get("file_key", "patch_table")
    patch_filename = file_map.get(patch_key, "patch_table.csv")
    patch_path = bundle_dir / patch_filename
    patch_table: pd.DataFrame | None = None
    if patch_path.exists():
        patch_table = _read_plain_csv(patch_path, patch_filename, issues)
        if patch_table is not None:
            summaries["files"][patch_filename]["row_count"] = int(patch_table.shape[0])
            summaries["files"][patch_filename]["column_count"] = int(patch_table.shape[1])
            summaries["patch_table"] = _validate_patch_table(patch_table, patch_cfg, issues)
    else:
        _add_issue(
            issues,
            "WARN",
            "patch_table_missing",
            "Optional patch_table.csv is missing.",
            {"file": patch_filename},
        )
        summaries["patch_table"] = {"present": False}

    _validate_universe_columns(contract, loaded_tables, issues, summaries)
    _validate_factor_columns(contract, loaded_tables, issues, summaries)
    _validate_returns_oc(contract, loaded_tables, issues, summaries)
    _validate_returns_cc(contract, loaded_tables, issues, summaries)
    _validate_common_dates(contract, loaded_tables, loaded_dates, issues, summaries)
    summaries["ticker_summary_rows"] = _build_ticker_summary_rows(contract, loaded_tables)

    return _finalize_result(issues, summaries)


def write_validation_outputs(result: DataContractResult, output_dir: Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_hashes_path = output_dir / "file_hashes.json"
    ticker_summary_path = output_dir / "ticker_summary.csv"
    report_json_path = output_dir / "validation_report.json"
    report_md_path = output_dir / "validation_report.md"

    with file_hashes_path.open("w", encoding="utf-8") as handle:
        json.dump(result.summaries.get("file_hashes", {}), handle, ensure_ascii=False, indent=2)

    ticker_rows = result.summaries.get("ticker_summary_rows", [])
    pd.DataFrame(ticker_rows).to_csv(ticker_summary_path, index=False)

    outputs = {
        "validation_report_json": str(report_json_path.resolve()),
        "validation_report_md": str(report_md_path.resolve()),
        "ticker_summary_csv": str(ticker_summary_path.resolve()),
        "file_hashes_json": str(file_hashes_path.resolve()),
    }
    result.summaries["outputs"] = outputs

    payload = {
        "contract": result.summaries.get("contract", {}),
        "bundle_dir": result.summaries.get("bundle_dir"),
        "passed": result.passed,
        "issue_counts": result.issue_counts(),
        "issues": [issue.to_dict() for issue in result.issues],
        "summaries": result.summaries,
        "outputs": outputs,
    }
    with report_json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    report_md_path.write_text(_render_report_markdown(result), encoding="utf-8")


def _finalize_result(issues: list[DataContractIssue], summaries: dict[str, Any]) -> DataContractResult:
    passed = not any(issue.severity == "ERROR" for issue in issues)
    return DataContractResult(passed=passed, issues=issues, summaries=summaries)


def _add_issue(
    issues: list[DataContractIssue],
    severity: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    issues.append(DataContractIssue(severity=severity, code=code, message=message, details=details))


def _read_table_csv(path: Path, file_name: str, issues: list[DataContractIssue]) -> pd.DataFrame | None:
    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        _add_issue(
            issues,
            "ERROR",
            "csv_read_failed",
            "Failed to read CSV file.",
            {"file": file_name, "error": str(exc)},
        )
        return None

    if raw.empty:
        _add_issue(
            issues,
            "ERROR",
            "csv_empty",
            "CSV file is empty.",
            {"file": file_name},
        )
        return None
    if raw.shape[1] < 2:
        _add_issue(
            issues,
            "ERROR",
            "csv_missing_value_columns",
            "CSV file must contain a date column and at least one value column.",
            {"file": file_name},
        )
        return None

    date_series = pd.to_datetime(raw.iloc[:, 0], errors="coerce")
    if bool(date_series.isna().any()):
        invalid_rows = raw.index[date_series.isna()].tolist()[:5]
        _add_issue(
            issues,
            "ERROR",
            "date_parse_failed",
            "Date values could not be parsed.",
            {"file": file_name, "rows": invalid_rows},
        )
        return None

    frame = raw.iloc[:, 1:].copy()
    frame.columns = [str(column) for column in frame.columns]
    frame.index = pd.DatetimeIndex(date_series)
    frame.index.name = "date"
    return frame


def _read_date_list_csv(path: Path, file_name: str, issues: list[DataContractIssue]) -> pd.DatetimeIndex | None:
    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        _add_issue(
            issues,
            "ERROR",
            "csv_read_failed",
            "Failed to read CSV file.",
            {"file": file_name, "error": str(exc)},
        )
        return None

    if raw.empty or raw.shape[1] < 1:
        _add_issue(
            issues,
            "ERROR",
            "csv_empty",
            "Date list CSV is empty.",
            {"file": file_name},
        )
        return None

    date_series = pd.to_datetime(raw.iloc[:, 0], errors="coerce")
    if bool(date_series.isna().any()):
        invalid_rows = raw.index[date_series.isna()].tolist()[:5]
        _add_issue(
            issues,
            "ERROR",
            "date_parse_failed",
            "Date values could not be parsed.",
            {"file": file_name, "rows": invalid_rows},
        )
        return None

    return pd.DatetimeIndex(date_series, name="date")


def _read_plain_csv(path: Path, file_name: str, issues: list[DataContractIssue]) -> pd.DataFrame | None:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        _add_issue(
            issues,
            "ERROR",
            "csv_read_failed",
            "Failed to read CSV file.",
            {"file": file_name, "error": str(exc)},
        )
        return None

    if frame.empty:
        _add_issue(
            issues,
            "ERROR",
            "csv_empty",
            "CSV file is empty.",
            {"file": file_name},
        )
        return None
    return frame


def _date_summary(
    dates: pd.DatetimeIndex,
    *,
    check_weekends: bool,
    issues: list[DataContractIssue],
    file_name: str,
) -> dict[str, Any]:
    summary = {
        "row_count": int(len(dates)),
        "start": dates.min().strftime("%Y-%m-%d") if len(dates) else None,
        "end": dates.max().strftime("%Y-%m-%d") if len(dates) else None,
        "unique": bool(dates.is_unique),
        "monotonic_increasing": bool(dates.is_monotonic_increasing),
    }

    if not dates.is_unique:
        duplicate_dates = dates[dates.duplicated()].strftime("%Y-%m-%d").tolist()[:5]
        _add_issue(
            issues,
            "ERROR",
            "duplicate_dates",
            "Dates must be unique.",
            {"file": file_name, "sample_duplicates": duplicate_dates},
        )
    if not dates.is_monotonic_increasing:
        _add_issue(
            issues,
            "ERROR",
            "dates_not_monotonic",
            "Dates must be monotonic increasing.",
            {"file": file_name},
        )

    weekend_count = int((dates.dayofweek >= 5).sum()) if check_weekends else 0
    summary["weekend_count"] = weekend_count if check_weekends else None
    if check_weekends and weekend_count > 0:
        weekend_dates = dates[dates.dayofweek >= 5].strftime("%Y-%m-%d").tolist()[:5]
        _add_issue(
            issues,
            "ERROR",
            "weekend_dates_present",
            "Weekend dates are not allowed for price and return files.",
            {"file": file_name, "sample_dates": weekend_dates},
        )
    return summary


def _non_null_summary(frame: pd.DataFrame) -> dict[str, Any]:
    counts = frame.notna().sum()
    return {
        "columns": int(frame.shape[1]),
        "rows": int(frame.shape[0]),
        "min_non_null": int(counts.min()) if len(counts) else 0,
        "max_non_null": int(counts.max()) if len(counts) else 0,
    }


def _validate_universe_columns(
    contract: dict[str, Any],
    loaded_tables: dict[str, pd.DataFrame],
    issues: list[DataContractIssue],
    summaries: dict[str, Any],
) -> None:
    universes = contract.get("universes", {})
    us_all = list(universes.get("us_all", []))
    jp = list(universes.get("jp", []))
    all_tickers = us_all + jp

    for key, expected in {
        "returns_cc": all_tickers,
        "open_prices_adj": all_tickers,
        "close_prices_adj": all_tickers,
    }.items():
        frame = loaded_tables.get(key)
        if frame is None:
            continue
        missing = [ticker for ticker in expected if ticker not in frame.columns]
        extras = sorted(column for column in frame.columns if column not in expected)
        summaries.setdefault("universe_columns", {})[key] = {
            "required_count": len(expected),
            "actual_count": int(frame.shape[1]),
            "missing": missing,
            "extras": extras,
        }
        if missing:
            _add_issue(
                issues,
                "ERROR",
                "missing_required_tickers",
                "Required tickers are missing from a bundle table.",
                {"file_key": key, "missing": missing},
            )

    frame = loaded_tables.get("returns_oc_jp")
    if frame is not None:
        missing = [ticker for ticker in jp if ticker not in frame.columns]
        extras = sorted(column for column in frame.columns if column not in jp)
        summaries.setdefault("universe_columns", {})["returns_oc_jp"] = {
            "required_count": len(jp),
            "actual_count": int(frame.shape[1]),
            "missing": missing,
            "extras": extras,
        }
        if missing:
            _add_issue(
                issues,
                "ERROR",
                "missing_required_tickers",
                "Required JP tickers are missing from returns_oc_jp.csv.",
                {"file_key": "returns_oc_jp", "missing": missing},
            )


def _validate_factor_columns(
    contract: dict[str, Any],
    loaded_tables: dict[str, pd.DataFrame],
    issues: list[DataContractIssue],
    summaries: dict[str, Any],
) -> None:
    factor_specs = contract.get("factor_columns", {})
    for factor_key, spec in factor_specs.items():
        frame = loaded_tables.get(factor_key)
        if frame is None:
            continue
        required = list(spec.get("required", []))
        aliases = spec.get("aliases", {})
        resolved: dict[str, str] = {}
        missing: list[str] = []
        for canonical in required:
            candidates = list(aliases.get(canonical, [canonical]))
            match = next((candidate for candidate in candidates if candidate in frame.columns), None)
            if match is None:
                missing.append(canonical)
            else:
                resolved[canonical] = match
        summaries["factor_columns"][factor_key] = {
            "required": required,
            "resolved": resolved,
            "missing": missing,
        }
        if missing:
            _add_issue(
                issues,
                "ERROR",
                "factor_columns_missing",
                "Required factor columns are missing.",
                {"file_key": factor_key, "missing": missing},
            )
            continue
        alias_usage = {canonical: actual for canonical, actual in resolved.items() if canonical != actual}
        if alias_usage:
            _add_issue(
                issues,
                "INFO",
                "factor_alias_resolved",
                "Factor aliases were resolved without renaming source columns.",
                {"file_key": factor_key, "aliases": alias_usage},
            )


def _validate_returns_oc(
    contract: dict[str, Any],
    loaded_tables: dict[str, pd.DataFrame],
    issues: list[DataContractIssue],
    summaries: dict[str, Any],
) -> None:
    returns_oc = loaded_tables.get("returns_oc_jp")
    open_prices = loaded_tables.get("open_prices_adj")
    close_prices = loaded_tables.get("close_prices_adj")
    jp = list(contract.get("universes", {}).get("jp", []))
    tolerance = float(contract.get("tolerances", {}).get("returns_oc_reconciliation_abs", 1e-10))

    if returns_oc is None or open_prices is None or close_prices is None:
        return
    if any(ticker not in returns_oc.columns for ticker in jp):
        return
    if any(ticker not in open_prices.columns for ticker in jp):
        return
    if any(ticker not in close_prices.columns for ticker in jp):
        return

    reconstructed = close_prices[jp] / open_prices[jp] - 1.0
    aligned_actual = returns_oc[jp]
    diff = (aligned_actual - reconstructed).abs()
    valid_mask = aligned_actual.notna() & reconstructed.notna()
    comparable = diff.where(valid_mask)
    max_abs_diff = _safe_frame_max(comparable)
    mismatch_count = int(((comparable > tolerance).fillna(False)).sum().sum())
    summaries["returns_oc_reconciliation"] = {
        "tolerance": tolerance,
        "max_abs_diff": max_abs_diff,
        "mismatch_count": mismatch_count,
    }
    if mismatch_count > 0:
        _add_issue(
            issues,
            "ERROR",
            "returns_oc_reconciliation_failed",
            "returns_oc_jp.csv does not reconcile with close/open adjusted prices.",
            {
                "tolerance": tolerance,
                "max_abs_diff": max_abs_diff,
                "mismatch_count": mismatch_count,
            },
        )


def _validate_returns_cc(
    contract: dict[str, Any],
    loaded_tables: dict[str, pd.DataFrame],
    issues: list[DataContractIssue],
    summaries: dict[str, Any],
) -> None:
    returns_cc = loaded_tables.get("returns_cc")
    close_prices = loaded_tables.get("close_prices_adj")
    us_all = list(contract.get("universes", {}).get("us_all", []))
    jp = list(contract.get("universes", {}).get("jp", []))
    expected = us_all + jp
    threshold = float(contract.get("tolerances", {}).get("returns_cc_diagnostic_abs", 1e-10))

    if returns_cc is None or close_prices is None:
        return
    if any(ticker not in returns_cc.columns for ticker in expected):
        return
    if any(ticker not in close_prices.columns for ticker in expected):
        return

    reconstructed = close_prices[expected].pct_change()
    aligned_actual = returns_cc[expected]
    diff = (aligned_actual - reconstructed).abs()
    valid_mask = aligned_actual.notna() & reconstructed.notna()
    comparable = diff.where(valid_mask)
    max_abs_diff = _safe_frame_max(comparable)
    mismatch_count = int(((comparable > threshold).fillna(False)).sum().sum())
    summaries["returns_cc_diagnostic"] = {
        "threshold": threshold,
        "max_abs_diff": max_abs_diff,
        "mismatch_count": mismatch_count,
        "policy": "warn_only_canonical_returns",
    }
    if mismatch_count > 0:
        _add_issue(
            issues,
            "WARN",
            "returns_cc_differs_from_prices",
            "returns_cc.csv differs from close_prices_adj.pct_change(); this is diagnostic only because returns_cc.csv is canonical.",
            {
                "threshold": threshold,
                "max_abs_diff": max_abs_diff,
                "mismatch_count": mismatch_count,
            },
        )


def _validate_common_dates(
    contract: dict[str, Any],
    loaded_tables: dict[str, pd.DataFrame],
    loaded_dates: dict[str, pd.DatetimeIndex],
    issues: list[DataContractIssue],
    summaries: dict[str, Any],
) -> None:
    returns_cc = loaded_tables.get("returns_cc")
    if returns_cc is None:
        return

    us_all = list(contract.get("universes", {}).get("us_all", []))
    us_core = list(contract.get("universes", {}).get("us_core", []))
    jp = list(contract.get("universes", {}).get("jp", []))

    for key, required_columns in {
        "common_dates_core": us_core + jp,
        "common_dates_full": us_all + jp,
    }.items():
        dates = loaded_dates.get(key)
        if dates is None:
            continue
        subset_ok = dates.isin(returns_cc.index).all()
        complete_case = False
        if subset_ok and all(column in returns_cc.columns for column in required_columns):
            complete_case = bool(returns_cc.loc[dates, required_columns].notna().all(axis=1).all())
        summaries["common_dates"][key] = {
            "row_count": int(len(dates)),
            "subset_of_returns_cc": bool(subset_ok),
            "complete_case": bool(complete_case),
            "required_column_count": len(required_columns),
        }
        if not subset_ok:
            missing_dates = pd.Index(dates).difference(returns_cc.index).strftime("%Y-%m-%d").tolist()[:5]
            _add_issue(
                issues,
                "ERROR",
                "common_dates_not_subset",
                "Common dates file must be a subset of returns_cc dates.",
                {"file_key": key, "sample_missing_dates": missing_dates},
            )
        if subset_ok and not complete_case:
            _add_issue(
                issues,
                "ERROR",
                "common_dates_not_complete_case",
                "Common dates file does not form a complete-case subset in returns_cc.csv.",
                {"file_key": key, "required_columns": required_columns},
            )


def _validate_patch_table(
    patch_table: pd.DataFrame,
    patch_cfg: dict[str, Any],
    issues: list[DataContractIssue],
) -> dict[str, Any]:
    expected_columns = list(patch_cfg.get("expected_columns", []))
    accepted_status_values = set(patch_cfg.get("accepted_status_values", []))
    allowed_statuses = set(patch_cfg.get("allowed_statuses_active_bundle", []))
    missing = [column for column in expected_columns if column not in patch_table.columns]

    summary: dict[str, Any] = {
        "present": True,
        "row_count": int(patch_table.shape[0]),
        "missing_columns": missing,
    }
    if missing:
        _add_issue(
            issues,
            "ERROR",
            "patch_table_columns_missing",
            "patch_table.csv is missing required columns.",
            {"missing": missing},
        )
        return summary

    status_series = patch_table["status"].astype(str)
    status_counts = status_series.value_counts(dropna=False).to_dict()
    summary["status_counts"] = {str(key): int(value) for key, value in status_counts.items()}

    invalid_statuses = sorted({status for status in status_series.unique() if status not in accepted_status_values})
    summary["invalid_statuses"] = invalid_statuses
    if invalid_statuses:
        _add_issue(
            issues,
            "ERROR",
            "patch_table_invalid_status",
            "patch_table.csv contains invalid status values.",
            {"invalid_statuses": invalid_statuses},
        )

    disallowed_statuses = sorted({status for status in status_series.unique() if status not in allowed_statuses})
    summary["disallowed_statuses_active_bundle"] = disallowed_statuses
    if disallowed_statuses:
        _add_issue(
            issues,
            "ERROR",
            "patch_table_disallowed_status",
            "patch_table.csv contains statuses that are not allowed in the active bundle.",
            {"disallowed_statuses": disallowed_statuses},
        )
    return summary


def _build_ticker_summary_rows(
    contract: dict[str, Any],
    loaded_tables: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    universes = contract.get("universes", {})
    us_all = list(universes.get("us_all", []))
    us_core = set(universes.get("us_core", []))
    jp = list(universes.get("jp", []))
    tickers = us_all + jp

    returns_cc = loaded_tables.get("returns_cc")
    returns_oc = loaded_tables.get("returns_oc_jp")
    open_prices = loaded_tables.get("open_prices_adj")
    close_prices = loaded_tables.get("close_prices_adj")

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        market = "US" if ticker in us_all else "JP"
        if ticker in jp:
            group = "jp"
        elif ticker in us_core:
            group = "us_core"
        else:
            group = "us_extended"
        rows.append(
            {
                "ticker": ticker,
                "market": market,
                "group": group,
                "present_in_returns_cc": _frame_has_column(returns_cc, ticker),
                "present_in_returns_oc_jp": _frame_has_column(returns_oc, ticker),
                "present_in_open_prices_adj": _frame_has_column(open_prices, ticker),
                "present_in_close_prices_adj": _frame_has_column(close_prices, ticker),
                "non_null_returns_cc": _non_null_count_for_column(returns_cc, ticker),
                "non_null_returns_oc_jp": _non_null_count_for_column(returns_oc, ticker),
                "non_null_open_prices_adj": _non_null_count_for_column(open_prices, ticker),
                "non_null_close_prices_adj": _non_null_count_for_column(close_prices, ticker),
            }
        )
    return rows


def _frame_has_column(frame: pd.DataFrame | None, column: str) -> bool:
    return frame is not None and column in frame.columns


def _non_null_count_for_column(frame: pd.DataFrame | None, column: str) -> int | None:
    if frame is None or column not in frame.columns:
        return None
    return int(frame[column].notna().sum())


def _hash_bundle_files(bundle_dir: Path) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for path in sorted(bundle_dir.iterdir()):
        if not path.is_file():
            continue
        relative = path.name
        hashes[relative] = {
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    return hashes


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_frame_max(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    max_value = frame.max(skipna=True).max(skipna=True)
    if pd.isna(max_value):
        return 0.0
    return float(max_value)


def _render_report_markdown(result: DataContractResult) -> str:
    contract = result.summaries.get("contract", {})
    issue_counts = result.issue_counts()
    lines = [
        "# Data Contract Validation Report",
        "",
        f"- Contract: `{contract.get('contract_name')}` v`{contract.get('contract_version')}`",
        f"- Bundle path: `{result.summaries.get('bundle_dir')}`",
        f"- Result: `{'PASS' if result.passed else 'FAIL'}`",
        "",
        "## Issue Counts",
        "",
        f"- ERROR: {issue_counts.get('ERROR', 0)}",
        f"- WARN: {issue_counts.get('WARN', 0)}",
        f"- INFO: {issue_counts.get('INFO', 0)}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(_render_issue_list(result.issues, "ERROR"))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_render_issue_list(result.issues, "WARN"))
    lines.extend(["", "## Info", ""])
    lines.extend(_render_issue_list(result.issues, "INFO"))
    lines.extend(["", "## Date Range Summary", ""])
    for file_name, summary in result.summaries.get("date_ranges", {}).items():
        lines.append(
            f"- `{file_name}`: rows={summary.get('row_count')} start={summary.get('start')} end={summary.get('end')} unique={summary.get('unique')} monotonic={summary.get('monotonic_increasing')} weekend_count={summary.get('weekend_count')}"
        )
    lines.extend(["", "## Non-Null Summary", ""])
    for file_name, summary in result.summaries.get("non_null_counts", {}).items():
        lines.append(
            f"- `{file_name}`: rows={summary.get('rows')} columns={summary.get('columns')} min_non_null={summary.get('min_non_null')} max_non_null={summary.get('max_non_null')}"
        )
    returns_oc = result.summaries.get("returns_oc_reconciliation", {})
    if returns_oc:
        lines.extend(
            [
                "",
                "## Returns OC Reconciliation",
                "",
                f"- tolerance={returns_oc.get('tolerance')}",
                f"- max_abs_diff={returns_oc.get('max_abs_diff')}",
                f"- mismatch_count={returns_oc.get('mismatch_count')}",
            ]
        )
    returns_cc = result.summaries.get("returns_cc_diagnostic", {})
    if returns_cc:
        lines.extend(
            [
                "",
                "## Returns CC Diagnostic",
                "",
                f"- threshold={returns_cc.get('threshold')}",
                f"- max_abs_diff={returns_cc.get('max_abs_diff')}",
                f"- mismatch_count={returns_cc.get('mismatch_count')}",
                "",
                "## Canonical Returns Policy",
                "",
                "- `returns_cc.csv` is canonical and is not recomputed or overwritten from adjusted prices.",
                "- Differences versus `close_prices_adj.pct_change()` are diagnostic warnings only because approved manual corrections may exist.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Canonical Returns Policy",
                "",
                "- `returns_cc.csv` is canonical and is not recomputed or overwritten from adjusted prices.",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_issue_list(issues: list[DataContractIssue], severity: str) -> list[str]:
    filtered = [issue for issue in issues if issue.severity == severity]
    if not filtered:
        return ["- none"]
    lines: list[str] = []
    for issue in filtered:
        detail_text = ""
        if issue.details:
            detail_text = f" details={json.dumps(issue.details, ensure_ascii=False, sort_keys=True)}"
        lines.append(f"- `{issue.code}`: {issue.message}{detail_text}")
    return lines
