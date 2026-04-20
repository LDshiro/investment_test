from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.ops.shadow_ops import _build_downstream_batch_summary, run_shadow_ops


def _base_config(tmp_path: Path) -> dict:
    return {
        "_config_path": str(tmp_path / "shadow_ops.yaml"),
        "ops": {
            "name": "test_shadow_ops",
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
        },
    }


def test_disabled_stage_and_path_propagation(tmp_path: Path, monkeypatch) -> None:
    config = _base_config(tmp_path)
    config["stages"]["validate_data_contract"]["enabled"] = False

    calls: dict[str, str] = {}
    batch_dir = tmp_path / "runs" / "batch_dir"
    batch_dir.mkdir(parents=True)
    for filename in ["batch_summary.csv", "batch_summary.json", "batch_summary.md"]:
        (batch_dir / filename).write_text("ok", encoding="utf-8")
    review_dir = tmp_path / "weekly_review"
    review_dir.mkdir(parents=True)
    (review_dir / "weekly_summary.csv").write_text("week_label\n2025-W48\n", encoding="utf-8")
    gates_dir = tmp_path / "weekly_gates"
    gates_dir.mkdir(parents=True)
    (gates_dir / "promotion_assessment.json").write_text(
        json.dumps({"promotion_status": "HOLD_SHADOW", "failed_checks": ["non_negative_shadow_return"], "blocked_checks": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_batch_stage",
        lambda stage_cfg, context, output_dir: context.update({"batch_dir": batch_dir}) or {"batch_dir": str(batch_dir), "completed": 60, "failed": 0},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_shadow_replay_stage",
        lambda stage_cfg, context, output_dir: context.update({"replay_validation_summary": {"total_days": 60, "completed_days": 60, "failed_days": 0, "packet_run_status_counts": {"GO": 60}, "batch_result_counts": {"completed": 60}}}) or {"status": "PASS"},
    )

    def fake_weekly_review(stage_cfg, context, output_dir):
        calls["weekly_review_batch_dir"] = str(context["batch_dir"])
        context["weekly_review_dir"] = review_dir
        return {"output_dir": str(review_dir), "latest_week": "2025-W48"}

    def fake_weekly_gates(stage_cfg, context, output_dir):
        calls["weekly_gates_review_dir"] = str(context["weekly_review_dir"])
        context["weekly_gates_summary"] = {"latest_week_status": "GO", "latest_week": "2025-W48", "promotion_status": "HOLD_SHADOW"}
        context["promotion_assessment"] = {
            "promotion_status": "HOLD_SHADOW",
            "failed_checks": ["non_negative_shadow_return"],
            "blocked_checks": [],
        }
        return {"output_dir": str(gates_dir), "latest_week_status": "GO", "promotion_status": "HOLD_SHADOW"}

    monkeypatch.setattr("leadlag.ops.shadow_ops._run_weekly_review_stage", fake_weekly_review)
    monkeypatch.setattr("leadlag.ops.shadow_ops._run_weekly_gates_stage", fake_weekly_gates)
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_render_runbook_stage",
        lambda stage_cfg, context, output_dir: {"passed": True, "output_dir": str(output_dir)},
    )

    result = run_shadow_ops(config)
    assert result.passed
    assert any(stage.stage == "validate_data_contract" and stage.status == "DISABLED" for stage in result.stage_results)
    assert calls["weekly_review_batch_dir"] == str(batch_dir)
    assert calls["weekly_gates_review_dir"] == str(review_dir)
    assert Path(result.output_paths["shadow_ops_summary_json"]).exists()
    assert Path(result.output_paths["stage_status_csv"]).exists()
    assert Path(result.output_paths["stage_status_json"]).exists()
    assert Path(result.output_paths["paths_json"]).exists()
    assert Path(result.output_paths["operator_digest_md"]).exists()


def test_skipped_existing_days_count_as_completed_in_summary(tmp_path: Path, monkeypatch) -> None:
    config = _base_config(tmp_path)

    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_data_contract_stage",
        lambda stage_cfg, context, output_dir: {"passed": True},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_batch_stage",
        lambda stage_cfg, context, output_dir: context.update({"batch_dir": tmp_path / "batch_dir"}) or {"batch_dir": str(tmp_path / "batch_dir")},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_shadow_replay_stage",
        lambda stage_cfg, context, output_dir: context.update(
            {
                "replay_validation_summary": {
                    "total_days": 60,
                    "completed_days": 0,
                    "failed_days": 0,
                    "packet_run_status_counts": {"GO": 60},
                    "batch_result_counts": {"skipped_existing": 60},
                }
            }
        )
        or {"status": "PASS"},
    )
    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_weekly_review_stage",
        lambda stage_cfg, context, output_dir: context.update({"weekly_review_dir": output_dir}) or {"output_dir": str(output_dir)},
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

    result = run_shadow_ops(config)
    assert result.summary["batch"]["completed_days"] == 60


def test_build_downstream_batch_summary_restores_packet_run_metadata(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_dir"
    batch_dir.mkdir()
    packet_dir = tmp_path / "runs" / "packet_a"
    packet_dir.mkdir(parents=True)
    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "run_status": "GO",
                "shadow_net_return": 0.01,
                "paper_counterfactual_return": 0.005,
                "expected_cost_bps": 15.0,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "trade_date": "2025-11-28",
                "result": "skipped_existing",
                "status": "SKIPPED",
                "packet_dir": str(packet_dir),
                "shadow_net_return": None,
                "paper_counterfactual_return": None,
            }
        ]
    ).to_csv(batch_dir / "batch_summary.csv", index=False)

    destination = tmp_path / "normalized.csv"
    info = _build_downstream_batch_summary(batch_dir, destination)
    normalized = pd.read_csv(destination)

    assert info["normalized_rows"] == 1
    assert normalized.loc[0, "result"] == "completed"
    assert normalized.loc[0, "status"] == "GO"
    assert normalized.loc[0, "shadow_net_return"] == 0.01
    assert normalized.loc[0, "paper_counterfactual_return"] == 0.005


def test_failed_stage_causes_skipped_following_stages(tmp_path: Path, monkeypatch) -> None:
    config = _base_config(tmp_path)

    monkeypatch.setattr(
        "leadlag.ops.shadow_ops._run_validate_data_contract_stage",
        lambda stage_cfg, context, output_dir: {"passed": True},
    )

    def fail_batch(stage_cfg, context, output_dir):
        raise RuntimeError("batch exploded")

    monkeypatch.setattr("leadlag.ops.shadow_ops._run_batch_stage", fail_batch)

    result = run_shadow_ops(config)
    assert not result.passed
    statuses = {stage.stage: stage.status for stage in result.stage_results}
    assert statuses["run_batch"] == "FAILED"
    assert statuses["validate_shadow_replay"] == "SKIPPED"
    assert statuses["weekly_review"] == "SKIPPED"
    assert statuses["weekly_gates"] == "SKIPPED"
    assert statuses["render_runbook"] == "SKIPPED"
    digest = Path(result.output_paths["operator_digest_md"]).read_text(encoding="utf-8")
    assert "Investigate the failed stage" in digest
