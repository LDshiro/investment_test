from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.broker.batch_dryrun import broker_dryrun_batch


def _write_packet(packet_dir: Path, *, trade_date: str, run_status: str, orders: list[dict]) -> None:
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": f"run-{trade_date}",
                "trade_date": trade_date,
                "run_status": run_status,
                "strategy": "pca_sub",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(orders).to_csv(packet_dir / "orders_shadow.csv", index=False)
    (packet_dir / "risk_report.json").write_text("{}", encoding="utf-8")
    (packet_dir / "alerts.json").write_text("[]", encoding="utf-8")


def _batch_dir(tmp_path: Path, packet_rows: list[dict]) -> Path:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    pd.DataFrame(packet_rows).to_csv(batch_dir / "batch_summary.csv", index=False)
    return batch_dir


def _dryrun_cfg(*, require_runtime_safety: bool = False) -> dict:
    return {
        "version": "broker_dryrun_batch_v1",
        "mode": "DRY_RUN",
        "allowed_broker_ids": ["null_broker_v1"],
        "allow_live_submission": False,
        "allow_paper_submission": False,
        "require_runtime_safety": require_runtime_safety,
        "allow_runtime_safety_warn": True,
        "block_on_runtime_safety_error": True,
        "runtime_safety": {
            "security_config": "configs/security/runtime_security_policy_v1.yaml",
            "secrets_inventory": "configs/security/secrets_inventory_v1.yaml",
            "host_config": "configs/runtime/execution_host_local_v1.yaml",
        },
        "require_packet_files": ["run.json", "orders_shadow.csv", "risk_report.json", "alerts.json"],
        "order_source": "orders_shadow.csv",
        "max_reject_rate": 0.0,
        "max_missing_intent_rate": 0.0,
        "require_ack_for_every_intent": True,
        "write_daily_artifacts": True,
    }


def test_broker_dryrun_batch_produces_artifacts_and_accepts_skipped_existing(tmp_path: Path) -> None:
    packet_a = tmp_path / "runs" / "packet_a"
    packet_b = tmp_path / "runs" / "packet_b"
    _write_packet(
        packet_a,
        trade_date="2025-11-27",
        run_status="GO",
        orders=[
            {
                "date": "2025-11-27",
                "ticker": "1619.T",
                "side": "BUY",
                "target_weight": 0.2,
                "intended_open_qty": 10,
                "intended_close_qty": 0,
                "open_price_adj": 100.0,
                "close_price_adj": 101.0,
                "target_notional_jpy": 1000.0,
                "close_side": "SELL",
            },
            {
                "date": "2025-11-27",
                "ticker": "1306.T",
                "side": "SELL",
                "target_weight": -0.2,
                "intended_open_qty": 5,
                "intended_close_qty": 0,
                "open_price_adj": 200.0,
                "close_price_adj": 199.0,
                "target_notional_jpy": 1000.0,
                "close_side": "BUY_TO_COVER",
            },
        ],
    )
    _write_packet(
        packet_b,
        trade_date="2025-11-28",
        run_status="GO",
        orders=[
            {
                "date": "2025-11-28",
                "ticker": "1321.T",
                "side": "BUY",
                "target_weight": 0.1,
                "intended_open_qty": 8,
                "intended_close_qty": 0,
                "open_price_adj": 125.0,
                "close_price_adj": 126.0,
                "target_notional_jpy": 1000.0,
                "close_side": "SELL",
            }
        ],
    )
    batch_dir = _batch_dir(
        tmp_path,
        [
            {"trade_date": "2025-11-27", "result": "completed", "status": "GO", "packet_dir": str(packet_a)},
            {"trade_date": "2025-11-28", "result": "skipped_existing", "status": "SKIPPED", "packet_dir": str(packet_b)},
        ],
    )

    out_dir, summary = broker_dryrun_batch(
        batch_dir=batch_dir,
        broker_config="configs/brokers/null_broker_v1.yaml",
        dryrun_config=_dryrun_cfg(),
        output_dir=tmp_path / "broker_dryrun_batch",
    )

    assert summary["passed"] is True
    assert summary["completed_days"] == 2
    assert summary["failed_days"] == 0
    assert summary["intent_count_total"] == 3
    assert summary["ack_count_total"] == 3
    assert (out_dir / "broker_dryrun_summary.csv").exists()
    assert (out_dir / "broker_dryrun_summary.json").exists()
    assert (out_dir / "broker_dryrun_summary.md").exists()
    assert (out_dir / "broker_dryrun_validation.json").exists()
    assert (out_dir / "daily" / "2025-11-27" / "broker_order_intents.csv").exists()
    assert (out_dir / "daily" / "2025-11-28" / "broker_acks.json").exists()

    day_a_acks = json.loads((out_dir / "daily" / "2025-11-27" / "broker_acks.json").read_text(encoding="utf-8"))
    assert len(day_a_acks) == 2
    assert all(item["broker_order_id"].startswith("DRYRUN-ORDER-") for item in day_a_acks)


def test_stop_day_with_empty_orders_passes(tmp_path: Path) -> None:
    packet_dir = tmp_path / "runs" / "packet_stop"
    _write_packet(packet_dir, trade_date="2025-11-29", run_status="STOP", orders=[])
    batch_dir = _batch_dir(
        tmp_path,
        [{"trade_date": "2025-11-29", "result": "completed", "status": "STOP", "packet_dir": str(packet_dir)}],
    )

    out_dir, summary = broker_dryrun_batch(
        batch_dir=batch_dir,
        broker_config="configs/brokers/null_broker_v1.yaml",
        dryrun_config=_dryrun_cfg(),
        output_dir=tmp_path / "broker_dryrun_batch",
    )

    assert summary["passed"] is True
    assert summary["intent_count_total"] == 0
    assert summary["ack_count_total"] == 0
    daily = pd.read_csv(out_dir / "broker_dryrun_summary.csv")
    assert bool(daily.loc[0, "passed"]) is True


def test_missing_orders_shadow_file_fails_day(tmp_path: Path) -> None:
    packet_dir = tmp_path / "runs" / "packet_missing"
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "run.json").write_text(
        json.dumps({"run_id": "run-missing", "trade_date": "2025-11-30", "run_status": "GO", "strategy": "pca_sub"}),
        encoding="utf-8",
    )
    (packet_dir / "risk_report.json").write_text("{}", encoding="utf-8")
    (packet_dir / "alerts.json").write_text("[]", encoding="utf-8")
    batch_dir = _batch_dir(
        tmp_path,
        [{"trade_date": "2025-11-30", "result": "completed", "status": "GO", "packet_dir": str(packet_dir)}],
    )

    out_dir, summary = broker_dryrun_batch(
        batch_dir=batch_dir,
        broker_config="configs/brokers/null_broker_v1.yaml",
        dryrun_config=_dryrun_cfg(),
        output_dir=tmp_path / "broker_dryrun_batch",
    )

    assert summary["passed"] is False
    assert summary["failed_days"] == 1
    daily = pd.read_csv(out_dir / "broker_dryrun_summary.csv")
    assert daily.loc[0, "reason_if_failed"] == "diagnostic_errors"
