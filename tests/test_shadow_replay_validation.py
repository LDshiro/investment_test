from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.config.loader import load_app_config
from leadlag.ops import load_validation_config, validate_shadow_replay


LEGACY_CONFIG = {
    "required_packet_files": [
        "summary.md",
        "run.json",
        "signals.csv",
        "orders_shadow.csv",
        "fills_shadow.csv",
        "positions.csv",
        "pnl.csv",
        "risk_report.json",
        "alerts.json",
    ],
    "optional_packet_files": [
        "figure_signals.png",
        "figure_equity_curve.png",
    ],
    "allow_statuses": ["GO", "WARN", "STOP"],
    "max_failed_days": 0,
    "max_missing_required_files": 0,
    "require_batch_summary": True,
    "require_monotonic_trade_dates": True,
    "require_unique_trade_dates": True,
}


def test_minimal_valid_legacy_batch_passes(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_dir = _write_packet(batch_dir, "2025-11-27")
    _write_batch_summary(batch_dir, [{"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_dir)}])

    result = validate_shadow_replay(batch_dir, LEGACY_CONFIG, batch_dir / "out")
    assert result.status == "PASS"
    assert result.passed is True
    assert (batch_dir / "out" / "daily_packet_audit.csv").exists()


def test_missing_required_packet_file_fails(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_dir = _write_packet(batch_dir, "2025-11-27", omit={"risk_report.json"})
    _write_batch_summary(batch_dir, [{"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_dir)}])

    result = validate_shadow_replay(batch_dir, LEGACY_CONFIG, batch_dir / "out")
    assert result.status == "FAIL"


def test_duplicate_trade_dates_fail_if_disallowed(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_a = _write_packet(batch_dir, "2025-11-27_a")
    packet_b = _write_packet(batch_dir, "2025-11-27_b")
    _write_batch_summary(
        batch_dir,
        [
            {"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_a)},
            {"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_b)},
        ],
    )

    result = validate_shadow_replay(batch_dir, LEGACY_CONFIG, batch_dir / "out")
    assert result.status == "FAIL"


def test_non_monotonic_trade_dates_fail_if_disallowed(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_a = _write_packet(batch_dir, "2025-11-28")
    packet_b = _write_packet(batch_dir, "2025-11-27")
    _write_batch_summary(
        batch_dir,
        [
            {"trade_date": "2025-11-28", "result": "completed", "packet_dir": str(packet_a)},
            {"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_b)},
        ],
    )

    result = validate_shadow_replay(batch_dir, LEGACY_CONFIG, batch_dir / "out")
    assert result.status == "FAIL"


def test_canonical_reconciliation_diff_exceeding_threshold_fails(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_dir = _write_packet(
        batch_dir,
        "2025-11-27",
        canonical=True,
        recon_overrides={
            "status": "PASS",
            "net_return_diff_bps": 1.5,
            "diagnostics": {"gross_return_diff_bps": 0.5, "cost_return_diff_bps": 0.5},
        },
    )
    _write_batch_summary(batch_dir, [{"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_dir)}])

    result = validate_shadow_replay(batch_dir, load_validation_config(Path("configs/validation/shadow_replay_canonical_v1.yaml")), batch_dir / "out")
    assert result.status == "FAIL"


def test_canonical_reconciliation_within_threshold_passes(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_dir = _write_packet(batch_dir, "2025-11-27", canonical=True)
    _write_batch_summary(batch_dir, [{"trade_date": "2025-11-27", "result": "completed", "packet_dir": str(packet_dir)}])

    result = validate_shadow_replay(batch_dir, Path("configs/validation/shadow_replay_canonical_v1.yaml"), batch_dir / "out")
    assert result.status == "PASS"
    assert (batch_dir / "out" / "canonical_reconciliation_summary.csv").exists()


def test_skipped_existing_with_valid_packet_is_accepted(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    packet_dir = _write_packet(batch_dir, "2025-11-27")
    _write_batch_summary(batch_dir, [{"trade_date": "2025-11-27", "result": "skipped_existing", "packet_dir": str(packet_dir)}])

    result = validate_shadow_replay(batch_dir, LEGACY_CONFIG, batch_dir / "out")
    audit = pd.read_csv(batch_dir / "out" / "daily_packet_audit.csv")
    assert result.status == "PASS"
    assert audit.loc[0, "packet_run_status"] == "GO"


def test_new_60d_profiles_load() -> None:
    legacy_cfg = load_app_config(Path("configs/profiles/shadow_corrected_batch_60d_local.yaml"))
    canonical_cfg = load_app_config(Path("configs/profiles/shadow_corrected_canonical_batch_60d_local.yaml"))
    assert legacy_cfg.batch.max_days == 60
    assert legacy_cfg.run.name == "shadow_corrected_batch_60d_local"
    assert canonical_cfg.batch.max_days == 60
    assert canonical_cfg.run.name == "shadow_corrected_canonical_batch_60d_local"
    assert canonical_cfg.simulator.enabled is True


def _write_batch_summary(batch_dir: Path, rows: list[dict[str, object]]) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(batch_dir / "batch_summary.csv", index=False)


def _write_packet(
    batch_dir: Path,
    name: str,
    *,
    omit: set[str] | None = None,
    canonical: bool = False,
    recon_overrides: dict[str, object] | None = None,
) -> Path:
    omit = omit or set()
    packet_dir = batch_dir / "packets" / name
    packet_dir.mkdir(parents=True, exist_ok=True)

    csv_stub = "ticker,value\n1617.T,1.0\n"
    files = {
        "summary.md": "# summary\n",
        "signals.csv": csv_stub,
        "orders_shadow.csv": csv_stub,
        "fills_shadow.csv": csv_stub,
        "positions.csv": csv_stub,
    }
    for file_name, content in files.items():
        if file_name not in omit:
            (packet_dir / file_name).write_text(content, encoding="utf-8")

    if "run.json" not in omit:
        (packet_dir / "run.json").write_text(
            json.dumps({"run_status": "GO", "expected_cost_bps": 15.0}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if "risk_report.json" not in omit:
        (packet_dir / "risk_report.json").write_text(
            json.dumps(
                {
                    "gross_exposure": 0.75,
                    "net_exposure": 0.75,
                    "gate_results": {"cost_too_high": {"triggered": False, "severity": "ok"}},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    if "alerts.json" not in omit:
        (packet_dir / "alerts.json").write_text(json.dumps({"alerts": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    if "pnl.csv" not in omit:
        pd.DataFrame([{"date": "2025-11-27", "net_return": 0.001}]).to_csv(packet_dir / "pnl.csv", index=False)

    if canonical:
        if "canonical_pnl.csv" not in omit:
            pd.DataFrame(
                [
                    {
                        "trade_date": "2025-11-27",
                        "net_return": 0.0011,
                        "gross_return": 0.0020,
                        "cost_return": -0.0009,
                    }
                ]
            ).to_csv(packet_dir / "canonical_pnl.csv", index=False)
        if "canonical_simulation_result.json" not in omit:
            (packet_dir / "canonical_simulation_result.json").write_text(
                json.dumps({"status": "GO", "pnl": {"net_return": 0.0011}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if "sim_reconciliation.json" not in omit:
            payload = {
                "status": "PASS",
                "net_return_diff_bps": 0.4,
                "diagnostics": {
                    "gross_return_diff_bps": 0.2,
                    "cost_return_diff_bps": 0.3,
                },
            }
            payload.update(recon_overrides or {})
            diagnostics = payload.get("diagnostics", {})
            base_diag = {
                "gross_return_diff_bps": 0.2,
                "cost_return_diff_bps": 0.3,
            }
            base_diag.update(diagnostics if isinstance(diagnostics, dict) else {})
            payload["diagnostics"] = base_diag
            (packet_dir / "sim_reconciliation.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    return packet_dir
