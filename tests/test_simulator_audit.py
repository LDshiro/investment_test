from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from leadlag.simulator_audit import (
    REQUIRED_AUDIT_SUMMARY_COLUMNS,
    build_audit_summary_frame,
    compare_fingerprint_sets,
    extract_packet_audit_row,
    fingerprint_packet,
    select_golden_days,
)


class _DummyStrategyOutput:
    def __init__(self, dates: pd.DatetimeIndex) -> None:
        self.returns = pd.Series(0.0, index=dates)


def test_select_golden_days_is_deterministic(monkeypatch) -> None:
    trade_dates = pd.DatetimeIndex(
        pd.to_datetime(
            [
                "2025-01-02",
                "2025-01-03",
                "2025-01-07",
                "2025-01-08",
                "2025-01-13",
                "2025-01-14",
                "2025-01-15",
                "2025-01-16",
            ]
        )
    )
    prepared = {
        "strategy_output": _DummyStrategyOutput(trade_dates),
        "sample_dates": trade_dates,
    }
    contract = {
        "audit": {
            "min_golden_days": 5,
            "candidate_pool_recent_n": 20,
            "fallback_pool_recent_n": 60,
            "holiday_gap_days": 4,
        }
    }
    preview_map = {
        "2025-01-02": _preview("2025-01-02", "GO", 0, False, False),
        "2025-01-03": _preview("2025-01-03", "GO", 0, False, False),
        "2025-01-07": _preview("2025-01-07", "GO", 0, False, False),
        "2025-01-08": _preview("2025-01-08", "GO", 1, True, False),
        "2025-01-13": _preview("2025-01-13", "GO", 0, False, True),
        "2025-01-14": _preview("2025-01-14", "WARN", 1, False, False),
        "2025-01-15": _preview("2025-01-15", "GO", 0, False, False),
        "2025-01-16": _preview("2025-01-16", "GO", 0, False, False),
    }

    def fake_preview(_cfg, _prepared, trade_date, *, holiday_gap_days: int = 4):
        return preview_map[pd.Timestamp(trade_date).date().isoformat()]

    monkeypatch.setattr("leadlag.simulator_audit.build_shadow_day_preview", fake_preview)

    selected = select_golden_days(object(), prepared, contract)
    selected_again = select_golden_days(object(), prepared, contract)

    assert [row["trade_date"] for row in selected] == [
        "2025-01-16",
        "2025-01-15",
        "2025-01-14",
        "2025-01-08",
        "2025-01-13",
    ]
    assert selected == selected_again


def test_fingerprint_packet_ignores_volatile_fields(tmp_path: Path) -> None:
    contract = {
        "audit": {
            "fingerprint_files": {
                "raw_csv": ["signals.csv", "orders_shadow.csv", "fills_shadow.csv", "positions.csv", "pnl.csv"],
                "normalized_json": ["run.json", "risk_report.json", "alerts.json"],
            },
            "volatile_run_json_fields": ["run_id", "started_at", "finished_at", "bundle_root"],
        }
    }
    packet_a = tmp_path / "packet_a"
    packet_b = tmp_path / "packet_b"
    _write_packet_fixture(packet_a, run_id="run-a", started_at="2026-01-01T00:00:00Z", bundle_root="C:/tmp/a")
    _write_packet_fixture(packet_b, run_id="run-b", started_at="2026-01-02T00:00:00Z", bundle_root="C:/tmp/b")

    fingerprint_a = fingerprint_packet(packet_a, contract)
    fingerprint_b = fingerprint_packet(packet_b, contract)
    comparison = compare_fingerprint_sets({"2025-11-28": fingerprint_a}, {"2025-11-28": fingerprint_b})

    assert fingerprint_a["stable_fingerprint"] == fingerprint_b["stable_fingerprint"]
    assert comparison["passed"] is True


def test_audit_summary_schema_contains_required_columns(tmp_path: Path) -> None:
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "trade_date": "2025-11-28",
                "asof_us_date": "2025-11-26",
                "run_status": "GO",
                "expected_cost_bps": 15.0,
                "shadow_net_return": 0.001,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (packet_dir / "risk_report.json").write_text(
        json.dumps(
            {
                "selected_names": 5,
                "gross_exposure": 0.75,
                "gate_results": {"cost_too_high": {"triggered": False}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (packet_dir / "alerts.json").write_text(json.dumps({"alerts": [{"code": "scaled_for_single_name_cap"}]}, ensure_ascii=False, indent=2), encoding="utf-8")

    row = extract_packet_audit_row(packet_dir, "packets/2025-11-28")
    row["selection_reason"] = "latest_valid"
    row["stable_fingerprint"] = "abc"
    row["rerun_match"] = True
    frame = build_audit_summary_frame([row])

    assert list(frame.columns[: len(REQUIRED_AUDIT_SUMMARY_COLUMNS)]) == REQUIRED_AUDIT_SUMMARY_COLUMNS


def _preview(
    trade_date: str,
    status: str,
    alert_count: int,
    scaling: bool,
    holiday_edge: bool,
) -> dict[str, object]:
    alert_codes = ["scaled_for_single_name_cap"] if scaling else []
    if alert_count and not alert_codes:
        alert_codes = ["warning_note"]
    return {
        "trade_date": trade_date,
        "asof_us_date": trade_date,
        "status": status,
        "tradable_names": 17,
        "selected_names": 5,
        "gross_exposure": 0.75,
        "net_exposure": 0.75,
        "expected_cost_bps": 15.0,
        "alert_codes": alert_codes,
        "alert_count": len(alert_codes),
        "triggered_gate_codes": [],
        "triggered_gates_count": 0,
        "paper_counterfactual_return": 0.0,
        "sample_filter_start": "2015-01-07",
        "sample_filter_end": "2025-11-28",
        "sample_filter_exact": True,
        "is_holiday_edge": holiday_edge,
    }


def _write_packet_fixture(packet_dir: Path, *, run_id: str, started_at: str, bundle_root: str) -> None:
    packet_dir.mkdir(parents=True, exist_ok=True)
    csv_text = "date,ticker,value\n2025-11-28,1617.T,1.0\n"
    for name in ["signals.csv", "orders_shadow.csv", "fills_shadow.csv", "positions.csv", "pnl.csv"]:
        (packet_dir / name).write_text(csv_text, encoding="utf-8")
    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "trade_date": "2025-11-28",
                "asof_us_date": "2025-11-26",
                "run_status": "GO",
                "expected_cost_bps": 15.0,
                "shadow_net_return": 0.001,
                "started_at": started_at,
                "finished_at": started_at,
                "bundle_root": bundle_root,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (packet_dir / "risk_report.json").write_text(
        json.dumps(
            {
                "selected_names": 5,
                "gross_exposure": 0.75,
                "gate_results": {"cost_too_high": {"triggered": False}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (packet_dir / "alerts.json").write_text(json.dumps({"alerts": []}, ensure_ascii=False, indent=2), encoding="utf-8")
