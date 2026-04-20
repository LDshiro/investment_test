from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.broker.calibration import calibrate_broker_dryrun_outputs
from leadlag.broker.models import BrokerMode, dataclass_to_payload
from leadlag.broker.null_adapter import NullBrokerAdapter
from leadlag.broker.packet_dryrun import intent_record, intents_from_packet


def _write_packet(packet_dir: Path) -> None:
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run-2025-11-27",
                "trade_date": "2025-11-27",
                "run_status": "GO",
                "strategy": "pca_sub",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
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
            }
        ]
    ).to_csv(packet_dir / "orders_shadow.csv", index=False)
    (packet_dir / "risk_report.json").write_text("{}", encoding="utf-8")
    (packet_dir / "alerts.json").write_text("[]", encoding="utf-8")


def _write_source(
    tmp_path: Path,
    *,
    reject_count: int = 0,
    missing_intent_symbol: bool = False,
    broker_mode: str = "DRY_RUN",
    credential_text: str | None = None,
    duplicate_intent: bool = False,
) -> Path:
    root = tmp_path / "legacy_shadow_ops"
    packet_dir = tmp_path / "packets" / "legacy" / "2025-11-27"
    _write_packet(packet_dir)
    _, intents = intents_from_packet(packet_dir)
    adapter = NullBrokerAdapter(mode=BrokerMode.DRY_RUN)
    payloads = [dataclass_to_payload(adapter.prepare_order_payload(intent)) for intent in intents]
    acks = [dataclass_to_payload(adapter.dry_run_order(intent)) for intent in intents]

    if broker_mode != "DRY_RUN":
        for item in payloads:
            item["broker_mode"] = broker_mode
        for item in acks:
            item["broker_mode"] = broker_mode
    if duplicate_intent:
        payloads.append(payloads[0])
        acks.append(acks[0])

    broker_dir = root / "stages" / "broker_dryrun"
    day_dir = broker_dir / "daily" / "2025-11-27"
    day_dir.mkdir(parents=True, exist_ok=True)
    intents_df = pd.DataFrame([intent_record(intent) for intent in intents])
    if missing_intent_symbol:
        intents_df.loc[0, "symbol"] = ""
    if duplicate_intent:
        intents_df = pd.concat([intents_df, intents_df.iloc[[0]]], ignore_index=True)
    intents_df.to_csv(day_dir / "broker_order_intents.csv", index=False)
    (day_dir / "broker_payloads.json").write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    (day_dir / "broker_acks.json").write_text(json.dumps(acks, ensure_ascii=False, indent=2), encoding="utf-8")
    diagnostics = [] if credential_text is None else [{"note": credential_text}]
    (day_dir / "broker_diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    pd.DataFrame(
        [
            {
                "trade_date": "2025-11-27",
                "packet_dir": str(packet_dir.resolve()),
                "run_status": "GO",
                "batch_result": "completed",
                "intent_count": len(intents_df),
                "payload_count": len(payloads),
                "ack_count": len(acks),
                "reject_count": reject_count,
                "missing_intent_count": 0,
                "raw_order_row_count": 1,
                "diagnostic_error_count": 0,
                "diagnostic_warn_count": 0,
                "gross_notional_jpy": 1000.0,
                "buy_notional_jpy": 1000.0,
                "sell_notional_jpy": 0.0,
                "broker_id": "null_broker_v1",
                "broker_mode": broker_mode,
                "runtime_safety_status": "WARN",
                "passed": reject_count == 0 and not missing_intent_symbol and broker_mode == "DRY_RUN" and credential_text is None and not duplicate_intent,
                "reason_if_failed": None,
            }
        ]
    ).to_csv(broker_dir / "broker_dryrun_summary.csv", index=False)
    (broker_dir / "broker_dryrun_summary.json").write_text(
        json.dumps(
            {
                "broker_id": "null_broker_v1",
                "broker_mode": broker_mode,
                "runtime_safety_status": "WARN",
                "total_days": 1,
                "completed_days": 1,
                "failed_days": 0,
                "intent_count_total": len(intents_df),
                "ack_count_total": len(acks),
                "reject_count_total": reject_count,
                "diagnostic_error_count_total": 0,
                "diagnostic_warn_count_total": 0,
                "passed": True,
                "reason_if_failed": None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (broker_dir / "broker_dryrun_validation.json").write_text("{}", encoding="utf-8")
    (root / "shadow_ops_summary.json").write_text(
        json.dumps(
            {
                "broker_dryrun": {
                    "enabled": True,
                    "output_dir": str(broker_dir.resolve()),
                    "runtime_safety_status": "WARN",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return root


def test_rejected_ack_fails_calibration(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path, reject_count=1)
    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=source_dir,
        canonical_shadow_ops_dir=None,
        calibration_config="configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
        output_dir=tmp_path / "calibration",
    )
    assert result.status == "FAIL"


def test_missing_required_field_fails_calibration(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path, missing_intent_symbol=True)
    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=source_dir,
        canonical_shadow_ops_dir=None,
        calibration_config="configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
        output_dir=tmp_path / "calibration",
    )
    assert result.status == "FAIL"


def test_paper_or_live_mode_fails_calibration(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path, broker_mode="LIVE")
    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=source_dir,
        canonical_shadow_ops_dir=None,
        calibration_config="configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
        output_dir=tmp_path / "calibration",
    )
    assert result.status == "FAIL"


def test_credential_like_value_fails_calibration(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path, credential_text="api_key=topsecret")
    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=source_dir,
        canonical_shadow_ops_dir=None,
        calibration_config="configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
        output_dir=tmp_path / "calibration",
    )
    assert result.status == "FAIL"


def test_duplicate_fingerprints_fail_calibration(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path, duplicate_intent=True)
    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=source_dir,
        canonical_shadow_ops_dir=None,
        calibration_config="configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
        output_dir=tmp_path / "calibration",
    )
    assert result.status == "FAIL"
