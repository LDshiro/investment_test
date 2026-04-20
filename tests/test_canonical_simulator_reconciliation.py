from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import pytest

from leadlag.sim.reconciliation import reconcile_shadow_packet, reconciliation_frame, write_reconciliation_outputs


def test_reconciliation_detects_known_return_difference_in_bps(tmp_path: Path) -> None:
    packet_dir = tmp_path / "packet"
    _write_reconciliation_fixture(
        packet_dir,
        legacy_net_return=0.0010,
        canonical_net_return=0.0008,
        legacy_gross_exposure=0.80,
        canonical_gross_exposure=0.75,
        legacy_cost_return=-0.0010,
        canonical_cost_return=-0.0011,
    )
    result = reconcile_shadow_packet(packet_dir, tolerance_net_return_bps=1.0, fail_on_tolerance_breach=False)
    outputs = write_reconciliation_outputs(result, packet_dir)

    assert result.net_return_diff_bps == pytest.approx(-2.0)
    assert result.status == "WARN"
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["json"]).exists()
    assert Path(outputs["md"]).exists()


def test_reconciliation_can_fail_on_tolerance_breach(tmp_path: Path) -> None:
    packet_dir = tmp_path / "packet"
    _write_reconciliation_fixture(
        packet_dir,
        legacy_net_return=0.0010,
        canonical_net_return=0.0006,
        legacy_gross_exposure=0.80,
        canonical_gross_exposure=0.75,
        legacy_cost_return=-0.0010,
        canonical_cost_return=-0.0014,
    )
    result = reconcile_shadow_packet(packet_dir, tolerance_net_return_bps=1.0, fail_on_tolerance_breach=True)
    assert result.status == "FAIL"
    assert result.within_tolerance is False


def test_reconciliation_emits_fields_when_legacy_cost_return_missing(tmp_path: Path) -> None:
    packet_dir = tmp_path / "packet"
    _write_reconciliation_fixture(
        packet_dir,
        legacy_net_return=0.0010,
        canonical_net_return=0.0010,
        legacy_gross_exposure=0.80,
        canonical_gross_exposure=0.80,
        legacy_cost_return=None,
        canonical_cost_return=-0.0005,
    )
    result = reconcile_shadow_packet(packet_dir, tolerance_net_return_bps=1.0)
    frame = reconciliation_frame(result)

    assert result.status == "PASS"
    assert result.legacy_cost_return is None
    assert frame.loc[0, "canonical_cost_return"] == pytest.approx(-0.0005)
    assert frame.loc[0, "legacy_gross_exposure"] == pytest.approx(0.80)


def _write_reconciliation_fixture(
    packet_dir: Path,
    *,
    legacy_net_return: float,
    canonical_net_return: float,
    legacy_gross_exposure: float,
    canonical_gross_exposure: float,
    legacy_cost_return: float | None,
    canonical_cost_return: float,
) -> None:
    packet_dir.mkdir(parents=True, exist_ok=True)
    legacy_payload = {
        "date": "2025-11-28",
        "gross_return": 0.0020,
        "net_return": legacy_net_return,
        "gross_pnl_jpy": 20.0,
        "net_pnl_jpy": legacy_net_return * 10000.0,
        "cost_pnl_jpy": (legacy_net_return - 0.0020) * 10000.0,
        "borrow_pnl_jpy": -1.0,
        "cumulative_return": 1.0 + legacy_net_return,
    }
    if legacy_cost_return is not None:
        legacy_payload["cost_return"] = legacy_cost_return
    pd.DataFrame([legacy_payload]).to_csv(packet_dir / "pnl.csv", index=False)

    pd.DataFrame(
        [
            {
                "trade_date": "2025-11-28",
                "nav_start_jpy": 10000.0,
                "nav_end_jpy": 10000.0 * (1.0 + canonical_net_return),
                "gross_pnl_jpy": 19.0,
                "cost_jpy": abs(canonical_cost_return) * 10000.0,
                "borrow_cost_jpy": 1.0,
                "net_pnl_jpy": canonical_net_return * 10000.0,
                "gross_return": 0.0019,
                "cost_return": canonical_cost_return,
                "net_return": canonical_net_return,
                "gross_exposure": canonical_gross_exposure,
                "net_exposure": canonical_gross_exposure,
                "turnover_entry": canonical_gross_exposure,
                "turnover_exit": canonical_gross_exposure,
                "n_positions": 5,
                "execution_cost_jpy": abs(canonical_cost_return) * 10000.0 - 1.0,
                "status": "GO",
            }
        ]
    ).to_csv(packet_dir / "canonical_pnl.csv", index=False)

    (packet_dir / "risk_report.json").write_text(
        json.dumps({"gross_exposure": legacy_gross_exposure}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
