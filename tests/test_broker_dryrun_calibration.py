from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.broker.calibration import calibrate_broker_dryrun_outputs, intent_fingerprint
from leadlag.broker.models import BrokerMode, dataclass_to_payload
from leadlag.broker.null_adapter import NullBrokerAdapter
from leadlag.broker.packet_dryrun import intent_record, intents_from_packet
from leadlag.ops import load_shadow_ops_config
from leadlag.ops.shadow_ops import run_shadow_ops


def _write_packet(packet_dir: Path, *, trade_date: str = "2025-11-27", run_status: str = "GO") -> None:
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
    pd.DataFrame(
        [
            {
                "date": trade_date,
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


def _write_shadow_ops_source(tmp_path: Path, source_name: str) -> Path:
    root = tmp_path / f"{source_name}_shadow_ops"
    packet_dir = tmp_path / "packets" / source_name / "2025-11-27"
    _write_packet(packet_dir)
    _, intents = intents_from_packet(packet_dir)
    adapter = NullBrokerAdapter(mode=BrokerMode.DRY_RUN)
    payloads = [dataclass_to_payload(adapter.prepare_order_payload(intent)) for intent in intents]
    acks = [dataclass_to_payload(adapter.dry_run_order(intent)) for intent in intents]

    broker_dir = root / "stages" / "broker_dryrun"
    day_dir = broker_dir / "daily" / "2025-11-27"
    day_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([intent_record(intent) for intent in intents]).to_csv(day_dir / "broker_order_intents.csv", index=False)
    (day_dir / "broker_payloads.json").write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    (day_dir / "broker_acks.json").write_text(json.dumps(acks, ensure_ascii=False, indent=2), encoding="utf-8")
    (day_dir / "broker_diagnostics.json").write_text("[]", encoding="utf-8")

    summary_row = {
        "trade_date": "2025-11-27",
        "packet_dir": str(packet_dir.resolve()),
        "run_status": "GO",
        "batch_result": "completed",
        "intent_count": 1,
        "payload_count": 1,
        "ack_count": 1,
        "reject_count": 0,
        "missing_intent_count": 0,
        "raw_order_row_count": 1,
        "diagnostic_error_count": 0,
        "diagnostic_warn_count": 0,
        "gross_notional_jpy": 1000.0,
        "buy_notional_jpy": 1000.0,
        "sell_notional_jpy": 0.0,
        "broker_id": "null_broker_v1",
        "broker_mode": "DRY_RUN",
        "runtime_safety_status": "WARN",
        "passed": True,
        "reason_if_failed": None,
    }
    pd.DataFrame([summary_row]).to_csv(broker_dir / "broker_dryrun_summary.csv", index=False)
    (broker_dir / "broker_dryrun_summary.json").write_text(
        json.dumps(
            {
                "batch_dir": str((tmp_path / "batch").resolve()),
                "broker_id": "null_broker_v1",
                "broker_mode": "DRY_RUN",
                "runtime_safety_status": "WARN",
                "runtime_safety_issue_counts": {"ERROR": 0, "WARN": 3, "INFO": 0},
                "total_days": 1,
                "completed_days": 1,
                "failed_days": 0,
                "intent_count_total": 1,
                "ack_count_total": 1,
                "reject_count_total": 0,
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
    (broker_dir / "broker_dryrun_validation.json").write_text(
        json.dumps({"passed": True, "reason_if_failed": None}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / "shadow_ops_summary.json").write_text(
        json.dumps(
            {
                "ops_run_id": f"{source_name}_run",
                "variant": source_name,
                "batch": {"batch_dir": str((tmp_path / "batch").resolve())},
                "broker_dryrun": {
                    "enabled": True,
                    "output_dir": str(broker_dir.resolve()),
                    "runtime_safety_status": "WARN",
                    "total_days": 1,
                    "completed_days": 1,
                    "failed_days": 0,
                    "intent_count_total": 1,
                    "ack_count_total": 1,
                    "reject_count_total": 0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return root


def test_broker_dryrun_calibration_passes_for_matching_artifacts(tmp_path: Path) -> None:
    legacy_dir = _write_shadow_ops_source(tmp_path, "legacy")

    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=legacy_dir,
        canonical_shadow_ops_dir=None,
        calibration_config="configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
        output_dir=tmp_path / "calibration",
    )

    assert result.status == "PASS"
    assert result.summary["sources"]["legacy"]["status"] == "PASS"
    assert result.summary["provided_sources"]["canonical"] is False
    assert not (tmp_path / "calibration" / "canonical").exists()
    assert (tmp_path / "calibration" / "calibration_summary.md").exists()
    assert (tmp_path / "calibration" / "legacy" / "calibration_summary.md").exists()
    assert result.summary["sources"]["legacy"]["shadow_order_count_total"] == 1
    assert result.summary["sources"]["legacy"]["intent_count_total"] == 1
    assert result.summary["sources"]["legacy"]["ack_count_total"] == 1
    assert result.summary["sources"]["legacy"]["reject_count_total"] == 0


def test_intent_fingerprint_is_stable() -> None:
    record = {
        "run_id": "run-1",
        "trade_date": "2025-11-27",
        "symbol": "1619.T",
        "side": "BUY",
        "order_type": "MARKET",
        "tif": "DAY",
        "quantity": 10.0,
        "notional_jpy": 1000.0,
        "strategy_id": "pca_sub",
    }
    assert intent_fingerprint(record) == intent_fingerprint(record)


def test_shadow_ops_profiles_support_optional_calibration_stage() -> None:
    legacy = load_shadow_ops_config(Path("configs/ops/shadow_ops_broker_dryrun_legacy_60d_local.yaml"))
    calibrated = load_shadow_ops_config(Path("configs/ops/shadow_ops_broker_dryrun_calibrated_legacy_60d_local.yaml"))
    assert legacy["stages"]["broker_dryrun_calibration"]["enabled"] is False
    assert calibrated["stages"]["broker_dryrun_calibration"]["enabled"] is True


def test_shadow_ops_records_broker_dryrun_calibration_outputs(monkeypatch, tmp_path: Path) -> None:
    config = {
        "_config_path": str(tmp_path / "shadow_ops.yaml"),
        "ops": {
            "name": "test_shadow_ops_broker_dryrun_calibration",
            "mode": "shadow_only",
            "variant": "legacy",
            "artifact_root": str(tmp_path / "artifacts"),
            "stop_on_stage_failure": True,
            "overwrite_existing": False,
            "timestamp_outputs": True,
            "operator_digest": True,
        },
        "stages": {
            "validate_data_contract": {"enabled": True, "bundle_dir": "x", "contract": "y"},
            "run_batch": {"enabled": True, "config": "batch.yaml"},
            "validate_shadow_replay": {"enabled": True, "config": "validation.yaml"},
            "weekly_review": {"enabled": True},
            "weekly_gates": {"enabled": True, "rules_config": "rules.yaml"},
            "render_runbook": {"enabled": True, "config": "runbook.yaml"},
            "broker_dryrun": {
                "enabled": True,
                "broker_config": "configs/brokers/null_broker_v1.yaml",
                "dryrun_config": "configs/broker_dryrun/broker_dryrun_batch_v1.yaml",
            },
            "broker_dryrun_calibration": {
                "enabled": True,
                "calibration_config": "configs/broker_dryrun/broker_dryrun_calibration_v1.yaml",
                "output_subdir": "broker_dryrun_calibration",
            },
        },
    }
    batch_dir = tmp_path / "runs" / "batch"
    batch_dir.mkdir(parents=True)
    review_dir = tmp_path / "weekly_review"
    review_dir.mkdir()
    broker_dir = tmp_path / "broker_dryrun"
    broker_dir.mkdir()
    calibration_dir = tmp_path / "broker_dryrun_calibration"
    calibration_dir.mkdir()

    monkeypatch.setattr("leadlag.ops.shadow_ops._run_validate_data_contract_stage", lambda stage_cfg, context, output_dir: {"passed": True})
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_batch_stage",
        lambda stage_cfg, context, output_dir: context.update({"batch_dir": batch_dir}) or {"batch_dir": str(batch_dir), "completed": 1, "failed": 0},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_shadow_replay_stage",
        lambda stage_cfg, context, output_dir: context.update(
            {"replay_validation_summary": {"total_days": 1, "completed_days": 1, "failed_days": 0, "packet_run_status_counts": {"GO": 1}, "batch_result_counts": {"completed": 1}}}
        )
        or {"status": "PASS"},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_weekly_review_stage",
        lambda stage_cfg, context, output_dir: context.update({"weekly_review_dir": review_dir}) or {"output_dir": str(review_dir)},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_weekly_gates_stage",
        lambda stage_cfg, context, output_dir: context.update(
            {"weekly_gates_summary": {"latest_week_status": "GO", "latest_week": "2025-W48"}, "promotion_assessment": {"promotion_status": "HOLD_SHADOW", "failed_checks": [], "blocked_checks": []}}
        )
        or {"output_dir": str(output_dir)},
    )
    monkeypatch.setattr("leadlag.ops.shadow_ops._run_render_runbook_stage", lambda stage_cfg, context, output_dir: {"passed": True, "output_dir": str(output_dir)})
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_broker_dryrun_stage",
        lambda stage_cfg, context, output_dir: context.update({"broker_dryrun_dir": broker_dir, "broker_dryrun_summary": {"runtime_safety_status": "WARN", "total_days": 1, "completed_days": 1, "failed_days": 0, "intent_count_total": 1, "ack_count_total": 1, "reject_count_total": 0, "diagnostic_error_count_total": 0, "diagnostic_warn_count_total": 0, "passed": True}})
        or {"output_dir": str(broker_dir), "passed": True},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_broker_dryrun_calibration_stage",
        lambda stage_cfg, context, output_dir: context.update(
            {
                "broker_dryrun_calibration_dir": calibration_dir,
                "broker_dryrun_calibration_summary": {
                    "status": "PASS",
                    "sources": {
                        "legacy": {
                            "status": "PASS",
                            "completed_days": 1,
                            "failed_days": 0,
                            "shadow_order_count_total": 1,
                            "intent_count_total": 1,
                            "ack_count_total": 1,
                            "reject_count_total": 0,
                            "unmatched_shadow_order_count": 0,
                            "unmatched_intent_count": 0,
                            "missing_required_field_count": 0,
                        }
                    },
                },
            }
        )
        or {"output_dir": str(calibration_dir), "status": "PASS"},
    )

    result = run_shadow_ops(config)
    assert result.passed is True
    assert result.summary["broker_dryrun_calibration"]["enabled"] is True
    assert result.summary["broker_dryrun_calibration"]["status"] == "PASS"
    paths = json.loads(Path(result.output_paths["paths_json"]).read_text(encoding="utf-8"))
    assert paths["broker_dryrun_calibration_dir"] == str(calibration_dir)
    digest = Path(result.output_paths["operator_digest_md"]).read_text(encoding="utf-8")
    assert "Broker Dry-Run Calibration" in digest
