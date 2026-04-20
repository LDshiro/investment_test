from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from leadlag.data_contract import validate_corrected_bundle


US_ALL = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLC", "XLRE"]
JP = [
    "1617.T",
    "1618.T",
    "1619.T",
    "1620.T",
    "1621.T",
    "1622.T",
    "1623.T",
    "1624.T",
    "1625.T",
    "1626.T",
    "1627.T",
    "1628.T",
    "1629.T",
    "1630.T",
    "1631.T",
    "1632.T",
    "1633.T",
]
ALL_TICKERS = US_ALL + JP
DATES = pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-08"])
CONTRACT_PATH = Path("configs/data_contracts/corrected_bundle_v1.yaml")


def test_missing_required_file_produces_error(tmp_path: Path) -> None:
    bundle_dir = _write_valid_bundle(tmp_path)
    (bundle_dir / "returns_oc_jp.csv").unlink()

    result = validate_corrected_bundle(bundle_dir, CONTRACT_PATH)

    assert result.passed is False
    assert _has_issue(result, "ERROR", "required_file_missing")


def test_minimal_valid_synthetic_bundle_passes(tmp_path: Path) -> None:
    bundle_dir = _write_valid_bundle(tmp_path)

    result = validate_corrected_bundle(bundle_dir, CONTRACT_PATH)

    assert result.passed is True
    assert _has_issue(result, "WARN", "patch_table_missing")
    assert not any(issue.severity == "ERROR" for issue in result.issues)


def test_returns_oc_mismatch_produces_error(tmp_path: Path) -> None:
    bundle_dir = _write_valid_bundle(tmp_path)
    returns_oc = pd.read_csv(bundle_dir / "returns_oc_jp.csv")
    returns_oc.loc[1, "1617.T"] += 0.01
    returns_oc.to_csv(bundle_dir / "returns_oc_jp.csv", index=False)

    result = validate_corrected_bundle(bundle_dir, CONTRACT_PATH)

    assert result.passed is False
    assert _has_issue(result, "ERROR", "returns_oc_reconciliation_failed")


def test_returns_cc_mismatch_is_warn_not_error(tmp_path: Path) -> None:
    bundle_dir = _write_valid_bundle(tmp_path)
    returns_cc = pd.read_csv(bundle_dir / "returns_cc.csv")
    returns_cc.loc[1, "XLB"] += 0.05
    returns_cc.to_csv(bundle_dir / "returns_cc.csv", index=False)

    result = validate_corrected_bundle(bundle_dir, CONTRACT_PATH)

    assert result.passed is True
    assert _has_issue(result, "WARN", "returns_cc_differs_from_prices")
    assert not _has_issue(result, "ERROR", "returns_cc_differs_from_prices")


def test_pending_patch_requires_explicit_allowance(tmp_path: Path) -> None:
    bundle_dir = _write_valid_bundle(tmp_path)
    patch_table = pd.DataFrame(
        [
            {
                "ticker": "1617.T",
                "date": "2025-01-07",
                "field": "returns_cc",
                "before": 0.01,
                "after": 0.02,
                "reason": "distribution correction",
                "patch_id": "patch-001",
                "status": "pending",
            }
        ]
    )
    patch_table.to_csv(bundle_dir / "patch_table.csv", index=False)

    default_result = validate_corrected_bundle(bundle_dir, CONTRACT_PATH)
    assert default_result.passed is False
    assert _has_issue(default_result, "ERROR", "patch_table_disallowed_status")

    contract_copy = tmp_path / "contract_allow_pending.yaml"
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["patch_table"]["allowed_statuses_active_bundle"] = ["approved", "pending"]
    contract_copy.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    allowed_result = validate_corrected_bundle(bundle_dir, contract_copy)
    assert allowed_result.passed is True
    assert not _has_issue(allowed_result, "ERROR", "patch_table_disallowed_status")


def _write_valid_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "corrected_bundle"
    bundle_dir.mkdir()

    close_prices = _price_frame(multiplier=1.0)
    open_prices = _price_frame(multiplier=0.99)
    returns_oc = close_prices[JP] / open_prices[JP] - 1.0
    returns_cc = close_prices.pct_change()
    returns_cc.iloc[0] = 0.0

    _write_indexed_csv(bundle_dir / "returns_cc.csv", returns_cc)
    _write_indexed_csv(bundle_dir / "returns_oc_jp.csv", returns_oc)
    _write_indexed_csv(bundle_dir / "open_prices_adj.csv", open_prices)
    _write_indexed_csv(bundle_dir / "close_prices_adj.csv", close_prices)
    _write_date_list_csv(bundle_dir / "common_dates_core.csv", DATES)
    _write_date_list_csv(bundle_dir / "common_dates_full.csv", DATES)
    _write_indexed_csv(
        bundle_dir / "ff3_japan_daily.csv",
        pd.DataFrame(
            {
                "Mkt-RF": [0.01, 0.0, -0.01],
                "SMB": [0.001, 0.002, 0.003],
                "HML": [0.004, 0.003, 0.002],
                "RF": [0.0001, 0.0001, 0.0001],
            },
            index=DATES,
        ),
        date_label="Date",
    )
    _write_indexed_csv(
        bundle_dir / "mom_japan_daily.csv",
        pd.DataFrame({"WML": [0.005, 0.004, 0.003]}, index=DATES),
        date_label="Date",
    )
    _write_indexed_csv(
        bundle_dir / "carhart4_japan_daily.csv",
        pd.DataFrame(
            {
                "Mkt-RF": [0.01, 0.0, -0.01],
                "SMB": [0.001, 0.002, 0.003],
                "HML": [0.004, 0.003, 0.002],
                "RF": [0.0001, 0.0001, 0.0001],
                "WML": [0.005, 0.004, 0.003],
            },
            index=DATES,
        ),
        date_label="Date",
    )
    return bundle_dir


def _price_frame(multiplier: float) -> pd.DataFrame:
    data: dict[str, list[float]] = {}
    for idx, ticker in enumerate(ALL_TICKERS, start=1):
        base = 100.0 + idx
        data[ticker] = [
            base * multiplier,
            base * multiplier * (1.0 + 0.01 + idx * 0.0001),
            base * multiplier * (1.0 + 0.02 + idx * 0.0002),
        ]
    return pd.DataFrame(data, index=DATES)


def _write_indexed_csv(path: Path, frame: pd.DataFrame, date_label: str = "date") -> None:
    output = frame.copy()
    output.insert(0, date_label, frame.index.strftime("%Y-%m-%d"))
    output.to_csv(path, index=False)


def _write_date_list_csv(path: Path, dates: pd.DatetimeIndex) -> None:
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d")}).to_csv(path, index=False)


def _has_issue(result, severity: str, code: str) -> bool:
    return any(issue.severity == severity and issue.code == code for issue in result.issues)
