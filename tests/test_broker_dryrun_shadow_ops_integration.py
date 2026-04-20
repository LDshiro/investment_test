from __future__ import annotations

from pathlib import Path
import json

from leadlag.ops import load_shadow_ops_config
from leadlag.ops.shadow_ops import run_shadow_ops


def _base_config(tmp_path: Path) -> dict:
    return {
        "_config_path": str(tmp_path / "shadow_ops.yaml"),
        "ops": {
            "name": "test_shadow_ops_broker_dryrun",
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
                "output_subdir": "broker_dryrun",
                "require_runtime_safety": True,
                "allow_runtime_safety_warn": True,
            },
        },
    }


def test_old_shadow_ops_profiles_still_load_without_broker_dryrun_requirement() -> None:
    legacy = load_shadow_ops_config(Path("configs/ops/shadow_ops_legacy_60d_local.yaml"))
    canonical = load_shadow_ops_config(Path("configs/ops/shadow_ops_canonical_60d_local.yaml"))
    assert legacy["stages"]["broker_dryrun"]["enabled"] is False
    assert canonical["stages"]["broker_dryrun"]["enabled"] is False


def test_broker_dryrun_shadow_ops_profiles_include_stage() -> None:
    legacy = load_shadow_ops_config(Path("configs/ops/shadow_ops_broker_dryrun_legacy_60d_local.yaml"))
    canonical = load_shadow_ops_config(Path("configs/ops/shadow_ops_broker_dryrun_canonical_60d_local.yaml"))
    assert legacy["stages"]["broker_dryrun"]["enabled"] is True
    assert canonical["stages"]["broker_dryrun"]["enabled"] is True


def test_shadow_ops_records_broker_dryrun_outputs(monkeypatch, tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    batch_dir = tmp_path / "runs" / "batch_dir"
    batch_dir.mkdir(parents=True)
    review_dir = tmp_path / "weekly_review"
    review_dir.mkdir()
    broker_dir = tmp_path / "broker_dryrun_stage"
    broker_dir.mkdir()

    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_data_contract_stage",
        lambda stage_cfg, context, output_dir: {"passed": True},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_batch_stage",
        lambda stage_cfg, context, output_dir: context.update({"batch_dir": batch_dir}) or {"batch_dir": str(batch_dir), "completed": 60, "failed": 0},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_shadow_replay_stage",
        lambda stage_cfg, context, output_dir: context.update(
            {
                "replay_validation_summary": {
                    "total_days": 60,
                    "completed_days": 60,
                    "failed_days": 0,
                    "packet_run_status_counts": {"GO": 60},
                    "batch_result_counts": {"completed": 60},
                }
            }
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
            {
                "weekly_gates_summary": {"latest_week_status": "GO", "latest_week": "2025-W48"},
                "promotion_assessment": {"promotion_status": "HOLD_SHADOW", "failed_checks": [], "blocked_checks": []},
            }
        )
        or {"output_dir": str(output_dir)},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_render_runbook_stage",
        lambda stage_cfg, context, output_dir: {"passed": True, "output_dir": str(output_dir)},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_broker_dryrun_stage",
        lambda stage_cfg, context, output_dir: context.update(
            {
                "broker_dryrun_dir": broker_dir,
                "broker_dryrun_summary": {
                    "runtime_safety_status": "WARN",
                    "total_days": 60,
                    "completed_days": 60,
                    "failed_days": 0,
                    "intent_count_total": 300,
                    "ack_count_total": 300,
                    "reject_count_total": 0,
                    "diagnostic_error_count_total": 0,
                    "diagnostic_warn_count_total": 60,
                    "passed": True,
                },
            }
        )
        or {"output_dir": str(broker_dir), "passed": True},
    )

    result = run_shadow_ops(config)
    assert result.passed is True
    assert result.summary["broker_dryrun"]["enabled"] is True
    assert result.summary["broker_dryrun"]["ack_count_total"] == 300
    paths = json.loads(Path(result.output_paths["paths_json"]).read_text(encoding="utf-8"))
    assert paths["broker_dryrun_dir"] == str(broker_dir)
    digest = Path(result.output_paths["operator_digest_md"]).read_text(encoding="utf-8")
    assert "Broker Dry-Run" in digest
    assert "ack_count_total" in digest
