from __future__ import annotations

from pathlib import Path
import json

from leadlag.broker import (
    BrokerMode,
    NullBrokerAdapter,
    OrderSide,
    broker_dryrun_from_packet,
    evaluate_broker_candidates,
    intents_from_packet,
)


def _packet_dir(tmp_path: Path) -> Path:
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "shadow_run_1",
                "trade_date": "2025-11-28",
                "strategy": "PCA_SUB",
            }
        ),
        encoding="utf-8",
    )
    (packet_dir / "orders_shadow.csv").write_text(
        "\n".join(
            [
                "date,ticker,side,target_weight,intended_open_qty,intended_close_qty,open_price_adj,close_price_adj,target_notional_jpy,close_side",
                "2025-11-28,1619.T,BUY,0.15,3.5,3.5,42390,42700,150000,SELL",
            ]
        ),
        encoding="utf-8",
    )
    return packet_dir


def test_null_adapter_exposes_contract_methods() -> None:
    adapter = NullBrokerAdapter(mode=BrokerMode.DRY_RUN)
    capabilities = adapter.get_capabilities()
    assert capabilities.supports_dry_run
    assert not capabilities.supports_live_api
    assert adapter.get_positions() == []
    assert adapter.get_account_snapshot().account_id == "DRYRUN"


def test_packet_intent_mapping_is_open_side_only(tmp_path: Path) -> None:
    packet_dir = _packet_dir(tmp_path)
    run_meta, intents = intents_from_packet(packet_dir)
    assert run_meta["run_id"] == "shadow_run_1"
    assert len(intents) == 1
    intent = intents[0]
    assert intent.side == OrderSide.BUY
    assert intent.quantity == 3.5
    assert intent.metadata["close_side"] == "SELL"
    assert intent.metadata["intended_close_qty"] == 3.5


def test_broker_dryrun_writes_artifacts(tmp_path: Path) -> None:
    packet_dir = _packet_dir(tmp_path)
    output_dir = tmp_path / "broker_dryrun"
    out_dir, status = broker_dryrun_from_packet(
        packet_dir=packet_dir,
        broker_config_path=Path("configs/brokers/null_broker_v1.yaml"),
        output_dir=output_dir,
    )
    assert status["intent_count"] == 1
    assert (out_dir / "broker_order_intents.csv").exists()
    assert (out_dir / "broker_payloads.csv").exists()
    assert (out_dir / "broker_acks.csv").exists()
    assert (out_dir / "broker_dryrun_summary.json").exists()


def test_broker_evaluator_writes_reports(tmp_path: Path) -> None:
    out_dir, status = evaluate_broker_candidates(
        Path("configs/brokers/broker_selection_v1.yaml"),
        tmp_path / "broker_selection",
    )
    assert status["default_safe_adapter"] == "null_broker_v1"
    assert (out_dir / "broker_selection_report.md").exists()
    assert (out_dir / "broker_selection_report.json").exists()
    assert (out_dir / "broker_decision_matrix.csv").exists()
