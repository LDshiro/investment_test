from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]

STATUS_COUNT_COLUMNS = ["dimension", "value", "count"]
ALERT_SUMMARY_COLUMNS = ["code", "severity", "count", "days_with_alert"]
RISK_GATE_SUMMARY_COLUMNS = ["gate_code", "triggered_days", "critical_days", "warning_days"]
CANONICAL_RECON_COLUMNS = [
    "trade_date",
    "reconciliation_status",
    "canonical_status",
    "canonical_net_return",
    "net_return_diff_bps",
    "gross_return_diff_bps",
    "cost_return_diff_bps",
]


@dataclass(slots=True)
class ReplayValidationIssue:
    severity: str
    code: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class ReplayValidationResult:
    status: str
    passed: bool
    issues: list[ReplayValidationIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)

    def issue_counts(self) -> dict[str, int]:
        counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_yaml_with_extends(path: Path) -> dict[str, Any]:
    data = _load_yaml(path)
    merged: dict[str, Any] = {}
    for rel in data.get("extends", []) or []:
        parent = (path.parent / rel).resolve()
        merged = _deep_merge(merged, _load_yaml_with_extends(parent))
    return _deep_merge(merged, data)


def load_validation_config(config_path_or_dict: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config_path_or_dict, dict):
        return dict(config_path_or_dict)
    return _load_yaml_with_extends(Path(config_path_or_dict).resolve())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_packet_dir(batch_dir: Path, packet_dir_value: Any) -> Path | None:
    if packet_dir_value is None or (isinstance(packet_dir_value, float) and pd.isna(packet_dir_value)):
        return None
    raw = Path(str(packet_dir_value))
    if raw.is_absolute():
        return raw
    repo_candidate = (REPO_ROOT / raw).resolve(strict=False)
    if repo_candidate.exists():
        return repo_candidate
    batch_candidate = (batch_dir / raw).resolve(strict=False)
    if batch_candidate.exists():
        return batch_candidate
    return repo_candidate


def _normalize_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        pass
    return float(value)


def _build_status_counts(audit_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dimension in ("batch_result", "packet_run_status", "audit_status"):
        if dimension not in audit_df.columns:
            continue
        counts = audit_df[dimension].fillna("MISSING").value_counts(dropna=False)
        for value, count in counts.items():
            rows.append({"dimension": dimension, "value": str(value), "count": int(count)})
    return pd.DataFrame(rows, columns=STATUS_COUNT_COLUMNS)


def _build_alert_summary(audit_df: pd.DataFrame) -> pd.DataFrame:
    exploded = audit_df.get("alert_details")
    if exploded is None:
        return pd.DataFrame(columns=ALERT_SUMMARY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for trade_date, alerts in zip(audit_df["trade_date"], audit_df["alert_details"], strict=False):
        for alert in alerts:
            rows.append(
                {
                    "trade_date": str(trade_date),
                    "code": str(alert.get("code", "unknown")),
                    "severity": str(alert.get("severity", "info")).upper(),
                }
            )
    if not rows:
        return pd.DataFrame(columns=ALERT_SUMMARY_COLUMNS)
    frame = pd.DataFrame(rows)
    summary = (
        frame.groupby(["code", "severity"], dropna=False)
        .agg(count=("trade_date", "size"), days_with_alert=("trade_date", "nunique"))
        .reset_index()
        .sort_values(["count", "code"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return summary.reindex(columns=ALERT_SUMMARY_COLUMNS)


def _build_risk_gate_summary(audit_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade_date, gate_results in zip(audit_df["trade_date"], audit_df["gate_results"], strict=False):
        for gate_code, payload in (gate_results or {}).items():
            if not payload.get("triggered"):
                continue
            rows.append(
                {
                    "trade_date": str(trade_date),
                    "gate_code": str(gate_code),
                    "severity": str(payload.get("severity", "warning")).lower(),
                }
            )
    if not rows:
        return pd.DataFrame(columns=RISK_GATE_SUMMARY_COLUMNS)
    frame = pd.DataFrame(rows)
    summary = (
        frame.groupby("gate_code", dropna=False)
        .agg(
            triggered_days=("trade_date", "nunique"),
            critical_days=("severity", lambda s: int((s == "critical").sum())),
            warning_days=("severity", lambda s: int((s == "warning").sum())),
        )
        .reset_index()
        .sort_values(["triggered_days", "gate_code"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return summary.reindex(columns=RISK_GATE_SUMMARY_COLUMNS)


def _build_canonical_summary(audit_df: pd.DataFrame) -> pd.DataFrame:
    if "reconciliation_status" not in audit_df.columns:
        return pd.DataFrame(columns=CANONICAL_RECON_COLUMNS)
    frame = audit_df.copy()
    return frame.reindex(columns=CANONICAL_RECON_COLUMNS)


def _report_markdown(result: ReplayValidationResult) -> str:
    summary = result.summary
    lines = [
        "# Shadow Replay Validation",
        "",
        f"- status: `{result.status}`",
        f"- batch_dir: `{summary.get('batch_dir', 'n/a')}`",
        f"- total_days: `{summary.get('total_days', 0)}`",
        f"- completed_days: `{summary.get('completed_days', 0)}`",
        f"- skipped_existing_days: `{summary.get('skipped_existing_days', 0)}`",
        f"- failed_days: `{summary.get('failed_days', 0)}`",
        f"- unique_trade_dates: `{summary.get('unique_trade_dates', True)}`",
        f"- monotonic_trade_dates: `{summary.get('monotonic_trade_dates', True)}`",
        "",
        "## Issue Counts",
        "",
    ]
    for severity, count in result.issue_counts().items():
        lines.append(f"- {severity}: {count}")
    lines.append("")

    if summary.get("canonical_enabled"):
        lines.append("## Canonical Reconciliation")
        lines.append("")
        lines.append(f"- max_abs_net_return_diff_bps: `{summary.get('max_abs_net_return_diff_bps')}`")
        lines.append(f"- max_abs_gross_return_diff_bps: `{summary.get('max_abs_gross_return_diff_bps')}`")
        lines.append(f"- max_abs_cost_return_diff_bps: `{summary.get('max_abs_cost_return_diff_bps')}`")
        lines.append("")

    if result.issues:
        lines.append("## Issues")
        lines.append("")
        for issue in result.issues:
            lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}")
    else:
        lines.append("No issues detected.")
    lines.append("")
    return "\n".join(lines)


def _write_outputs(
    output_dir: Path,
    *,
    result: ReplayValidationResult,
    audit_df: pd.DataFrame,
    status_counts: pd.DataFrame,
    alert_summary: pd.DataFrame,
    risk_gate_summary: pd.DataFrame,
    canonical_summary: pd.DataFrame | None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = output_dir / "replay_validation_report.json"
    report_md_path = output_dir / "replay_validation_report.md"
    audit_csv_path = output_dir / "daily_packet_audit.csv"
    status_csv_path = output_dir / "status_counts.csv"
    alert_csv_path = output_dir / "alert_summary.csv"
    gate_csv_path = output_dir / "risk_gate_summary.csv"

    serializable_audit = audit_df.drop(columns=["alert_details", "gate_results"], errors="ignore")
    serializable_audit.to_csv(audit_csv_path, index=False)
    status_counts.to_csv(status_csv_path, index=False)
    alert_summary.to_csv(alert_csv_path, index=False)
    risk_gate_summary.to_csv(gate_csv_path, index=False)

    payload = {
        "status": result.status,
        "passed": result.passed,
        "summary": result.summary,
        "issue_counts": result.issue_counts(),
        "issues": [asdict(issue) for issue in result.issues],
        "output_paths": {
            "daily_packet_audit_csv": str(audit_csv_path),
            "status_counts_csv": str(status_csv_path),
            "alert_summary_csv": str(alert_csv_path),
            "risk_gate_summary_csv": str(gate_csv_path),
        },
    }
    if canonical_summary is not None:
        canonical_path = output_dir / "canonical_reconciliation_summary.csv"
        canonical_summary.to_csv(canonical_path, index=False)
        payload["output_paths"]["canonical_reconciliation_summary_csv"] = str(canonical_path)

    report_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(_report_markdown(result), encoding="utf-8")
    payload["output_paths"]["replay_validation_report_json"] = str(report_json_path)
    payload["output_paths"]["replay_validation_report_md"] = str(report_md_path)
    return payload["output_paths"]


def validate_shadow_replay(
    batch_dir: Path,
    validation_config: Path | str | dict[str, Any],
    output_dir: Path,
) -> ReplayValidationResult:
    batch_dir = Path(batch_dir).resolve()
    cfg = load_validation_config(validation_config)
    issues: list[ReplayValidationIssue] = []
    batch_summary_path = batch_dir / "batch_summary.csv"

    if cfg.get("require_batch_summary", True) and not batch_summary_path.exists():
        result = ReplayValidationResult(
            status="FAIL",
            passed=False,
            issues=[
                ReplayValidationIssue(
                    severity="ERROR",
                    code="missing_batch_summary",
                    message=f"Required batch summary not found: {batch_summary_path}",
                )
            ],
            summary={
                "batch_dir": str(batch_dir),
                "total_days": 0,
                "completed_days": 0,
                "skipped_existing_days": 0,
                "failed_days": 0,
                "unique_trade_dates": False,
                "monotonic_trade_dates": False,
                "canonical_enabled": bool(cfg.get("canonical_required_packet_files")),
            },
        )
        empty = pd.DataFrame()
        outputs = _write_outputs(
            output_dir,
            result=result,
            audit_df=empty,
            status_counts=pd.DataFrame(columns=STATUS_COUNT_COLUMNS),
            alert_summary=pd.DataFrame(columns=ALERT_SUMMARY_COLUMNS),
            risk_gate_summary=pd.DataFrame(columns=RISK_GATE_SUMMARY_COLUMNS),
            canonical_summary=pd.DataFrame(columns=CANONICAL_RECON_COLUMNS) if cfg.get("canonical_required_packet_files") else None,
        )
        result.output_paths = outputs
        return result

    batch_df = pd.read_csv(batch_summary_path)
    if "trade_date" not in batch_df.columns or "result" not in batch_df.columns:
        raise ValueError(f"batch_summary.csv must contain trade_date and result columns: {batch_summary_path}")

    trade_dates = pd.to_datetime(batch_df["trade_date"], errors="coerce")
    unique_trade_dates = bool(trade_dates.is_unique)
    monotonic_trade_dates = bool(trade_dates.is_monotonic_increasing)
    if cfg.get("require_unique_trade_dates", True) and not unique_trade_dates:
        issues.append(
            ReplayValidationIssue(
                severity="ERROR",
                code="duplicate_trade_dates",
                message="Duplicate trade_date rows found in batch_summary.csv.",
            )
        )
    if cfg.get("require_monotonic_trade_dates", True) and not monotonic_trade_dates:
        issues.append(
            ReplayValidationIssue(
                severity="ERROR",
                code="non_monotonic_trade_dates",
                message="trade_date rows are not monotonic increasing in batch_summary.csv.",
            )
        )

    required_files = list(cfg.get("required_packet_files", []))
    canonical_required = list(cfg.get("canonical_required_packet_files", []))
    allow_statuses = set(cfg.get("allow_statuses", []))
    recon_cfg = cfg.get("canonical_reconciliation", {})

    audit_rows: list[dict[str, Any]] = []
    failed_days = 0
    missing_required_files_total = 0

    for row in batch_df.to_dict(orient="records"):
        trade_date = str(row.get("trade_date"))
        batch_result = str(row.get("result"))
        row_issues: list[ReplayValidationIssue] = []
        packet_dir = _resolve_packet_dir(batch_dir, row.get("packet_dir"))
        packet_exists = packet_dir is not None and packet_dir.exists()
        if batch_result == "failed":
            failed_days += 1
        if batch_result in {"completed", "skipped_existing"} and not packet_exists:
            row_issues.append(
                ReplayValidationIssue(
                    severity="ERROR",
                    code="missing_packet_dir",
                    message=f"Packet directory missing for {batch_result} day {trade_date}.",
                    details={"packet_dir": None if packet_dir is None else str(packet_dir)},
                )
            )

        run_meta: dict[str, Any] = {}
        risk_report: dict[str, Any] = {}
        alerts_doc: dict[str, Any] = {"alerts": []}
        pnl_row: dict[str, Any] = {}
        alert_details: list[dict[str, Any]] = []
        gate_results: dict[str, Any] = {}
        missing_required_files: list[str] = []
        canonical_status = None
        canonical_net_return = None
        reconciliation_status = None
        net_return_diff_bps = None
        gross_return_diff_bps = None
        cost_return_diff_bps = None

        if packet_exists:
            for file_name in required_files:
                if not (packet_dir / file_name).exists():
                    missing_required_files.append(file_name)
            missing_required_files_total += len(missing_required_files)
            if missing_required_files:
                row_issues.append(
                    ReplayValidationIssue(
                        severity="ERROR",
                        code="missing_required_packet_files",
                        message=f"Missing required packet files for {trade_date}.",
                        details={"packet_dir": str(packet_dir), "missing_required_files": missing_required_files},
                    )
                )
            if (packet_dir / "run.json").exists():
                run_meta = _read_json(packet_dir / "run.json")
            if (packet_dir / "risk_report.json").exists():
                risk_report = _read_json(packet_dir / "risk_report.json")
                gate_results = risk_report.get("gate_results", {}) if isinstance(risk_report, dict) else {}
            if (packet_dir / "alerts.json").exists():
                alerts_doc = _read_json(packet_dir / "alerts.json")
                alert_details = list(alerts_doc.get("alerts", [])) if isinstance(alerts_doc, dict) else []
            if (packet_dir / "pnl.csv").exists():
                pnl_df = pd.read_csv(packet_dir / "pnl.csv")
                if not pnl_df.empty:
                    pnl_row = pnl_df.iloc[0].to_dict()

            if canonical_required:
                missing_canonical = [name for name in canonical_required if not (packet_dir / name).exists()]
                if missing_canonical:
                    row_issues.append(
                        ReplayValidationIssue(
                            severity="ERROR",
                            code="missing_canonical_packet_files",
                            message=f"Missing canonical packet files for {trade_date}.",
                            details={"packet_dir": str(packet_dir), "missing_canonical_files": missing_canonical},
                        )
                    )
                if (packet_dir / "canonical_simulation_result.json").exists():
                    sim_result = _read_json(packet_dir / "canonical_simulation_result.json")
                    canonical_status = sim_result.get("status")
                    pnl_payload = sim_result.get("pnl") or {}
                    canonical_net_return = _normalize_float(pnl_payload.get("net_return"))
                if (packet_dir / "sim_reconciliation.json").exists():
                    recon = _read_json(packet_dir / "sim_reconciliation.json")
                    reconciliation_status = recon.get("status")
                    net_return_diff_bps = _normalize_float(recon.get("net_return_diff_bps"))
                    diagnostics = recon.get("diagnostics") or {}
                    gross_return_diff_bps = _normalize_float(diagnostics.get("gross_return_diff_bps"))
                    cost_return_diff_bps = _normalize_float(diagnostics.get("cost_return_diff_bps"))
                    if recon_cfg.get("require_status_pass", False) and reconciliation_status != "PASS":
                        row_issues.append(
                            ReplayValidationIssue(
                                severity="ERROR",
                                code="canonical_reconciliation_status",
                                message=f"Canonical reconciliation status must be PASS for {trade_date}.",
                                details={"actual_status": reconciliation_status},
                            )
                        )
                    thresholds = {
                        "net_return_diff_bps": recon_cfg.get("max_abs_net_return_diff_bps"),
                        "gross_return_diff_bps": recon_cfg.get("max_abs_gross_return_diff_bps"),
                        "cost_return_diff_bps": recon_cfg.get("max_abs_cost_return_diff_bps"),
                    }
                    values = {
                        "net_return_diff_bps": net_return_diff_bps,
                        "gross_return_diff_bps": gross_return_diff_bps,
                        "cost_return_diff_bps": cost_return_diff_bps,
                    }
                    for key, limit in thresholds.items():
                        value = values[key]
                        if limit is not None and value is not None and abs(value) > float(limit):
                            row_issues.append(
                                ReplayValidationIssue(
                                    severity="ERROR",
                                    code=f"canonical_{key}_threshold",
                                    message=f"Canonical {key} exceeded threshold on {trade_date}.",
                                    details={"value": value, "limit": float(limit)},
                                )
                            )

        packet_run_status = run_meta.get("run_status")
        if packet_run_status is None and batch_result == "completed":
            packet_run_status = row.get("status")
        if packet_run_status is not None and allow_statuses and packet_run_status not in allow_statuses:
            row_issues.append(
                ReplayValidationIssue(
                    severity="ERROR",
                    code="invalid_packet_status",
                    message=f"Packet run status {packet_run_status} is not allowed for {trade_date}.",
                )
            )

        alert_count = len(alert_details)
        warning_alert_count = int(sum(1 for alert in alert_details if str(alert.get("severity", "")).lower() == "warning"))
        critical_alert_count = int(sum(1 for alert in alert_details if str(alert.get("severity", "")).lower() == "critical"))
        triggered_gate_codes = sorted(
            str(code) for code, payload in gate_results.items() if isinstance(payload, dict) and payload.get("triggered")
        )
        triggered_gate_count = len(triggered_gate_codes)

        audit_status = "FAIL"
        if not any(issue.severity == "ERROR" for issue in row_issues):
            if packet_run_status in {"WARN", "STOP"} or critical_alert_count > 0 or triggered_gate_count > 0:
                audit_status = "WARN"
            else:
                audit_status = "PASS"

        audit_rows.append(
            {
                "trade_date": trade_date,
                "batch_result": batch_result,
                "packet_run_status": packet_run_status,
                "packet_dir": None if packet_dir is None else str(packet_dir),
                "missing_required_files_count": len(missing_required_files),
                "missing_required_files": ";".join(missing_required_files) if missing_required_files else None,
                "alert_count": alert_count,
                "warning_alert_count": warning_alert_count,
                "critical_alert_count": critical_alert_count,
                "triggered_gate_count": triggered_gate_count,
                "triggered_gate_codes": ";".join(triggered_gate_codes) if triggered_gate_codes else None,
                "expected_cost_bps": _normalize_float(run_meta.get("expected_cost_bps", risk_report.get("expected_cost_bps"))),
                "gross_exposure": _normalize_float(risk_report.get("gross_exposure")),
                "net_exposure": _normalize_float(risk_report.get("net_exposure")),
                "shadow_net_return": _normalize_float(pnl_row.get("net_return", row.get("shadow_net_return"))),
                "canonical_status": canonical_status,
                "canonical_net_return": canonical_net_return,
                "reconciliation_status": reconciliation_status,
                "net_return_diff_bps": net_return_diff_bps,
                "gross_return_diff_bps": gross_return_diff_bps,
                "cost_return_diff_bps": cost_return_diff_bps,
                "audit_status": audit_status,
                "audit_notes": " | ".join(issue.message for issue in row_issues) if row_issues else None,
                "alert_details": alert_details,
                "gate_results": gate_results,
            }
        )
        issues.extend(row_issues)

    if failed_days > int(cfg.get("max_failed_days", 0)):
        issues.append(
            ReplayValidationIssue(
                severity="ERROR",
                code="failed_days_exceeded",
                message=f"Failed day count {failed_days} exceeded max_failed_days={cfg.get('max_failed_days', 0)}.",
            )
        )
    if missing_required_files_total > int(cfg.get("max_missing_required_files", 0)):
        issues.append(
            ReplayValidationIssue(
                severity="ERROR",
                code="missing_required_files_exceeded",
                message=(
                    f"Missing required packet file count {missing_required_files_total} exceeded "
                    f"max_missing_required_files={cfg.get('max_missing_required_files', 0)}."
                ),
            )
        )

    audit_df = pd.DataFrame(audit_rows)
    if audit_df.empty:
        audit_df = pd.DataFrame(
            columns=[
                "trade_date",
                "batch_result",
                "packet_run_status",
                "packet_dir",
                "missing_required_files_count",
                "missing_required_files",
                "alert_count",
                "warning_alert_count",
                "critical_alert_count",
                "triggered_gate_count",
                "triggered_gate_codes",
                "expected_cost_bps",
                "gross_exposure",
                "net_exposure",
                "shadow_net_return",
                "canonical_status",
                "canonical_net_return",
                "reconciliation_status",
                "net_return_diff_bps",
                "gross_return_diff_bps",
                "cost_return_diff_bps",
                "audit_status",
                "audit_notes",
                "alert_details",
                "gate_results",
            ]
        )

    status_counts = _build_status_counts(audit_df)
    alert_summary = _build_alert_summary(audit_df)
    risk_gate_summary = _build_risk_gate_summary(audit_df)
    canonical_summary = _build_canonical_summary(audit_df) if canonical_required else None

    max_abs_net = None
    max_abs_gross = None
    max_abs_cost = None
    if canonical_summary is not None and not canonical_summary.empty:
        max_abs_net = float(canonical_summary["net_return_diff_bps"].abs().dropna().max()) if canonical_summary["net_return_diff_bps"].notna().any() else None
        max_abs_gross = float(canonical_summary["gross_return_diff_bps"].abs().dropna().max()) if canonical_summary["gross_return_diff_bps"].notna().any() else None
        max_abs_cost = float(canonical_summary["cost_return_diff_bps"].abs().dropna().max()) if canonical_summary["cost_return_diff_bps"].notna().any() else None

    has_error = any(issue.severity == "ERROR" for issue in issues)
    has_warn = bool((audit_df.get("audit_status", pd.Series(dtype=str)) == "WARN").any())
    status = "FAIL" if has_error else ("WARN" if has_warn else "PASS")
    result = ReplayValidationResult(
        status=status,
        passed=status != "FAIL",
        issues=issues,
        summary={
            "batch_dir": str(batch_dir),
            "total_days": int(batch_df.shape[0]),
            "completed_days": int((batch_df["result"] == "completed").sum()),
            "skipped_existing_days": int((batch_df["result"] == "skipped_existing").sum()),
            "failed_days": int(failed_days),
            "unique_trade_dates": unique_trade_dates,
            "monotonic_trade_dates": monotonic_trade_dates,
            "canonical_enabled": bool(canonical_required),
            "packet_run_status_counts": {
                str(key): int(value)
                for key, value in audit_df["packet_run_status"].fillna("MISSING").value_counts(dropna=False).items()
            } if "packet_run_status" in audit_df else {},
            "batch_result_counts": {
                str(key): int(value)
                for key, value in batch_df["result"].fillna("MISSING").value_counts(dropna=False).items()
            },
            "max_abs_net_return_diff_bps": max_abs_net,
            "max_abs_gross_return_diff_bps": max_abs_gross,
            "max_abs_cost_return_diff_bps": max_abs_cost,
        },
    )
    result.output_paths = _write_outputs(
        output_dir,
        result=result,
        audit_df=audit_df,
        status_counts=status_counts,
        alert_summary=alert_summary,
        risk_gate_summary=risk_gate_summary,
        canonical_summary=canonical_summary,
    )
    return result
