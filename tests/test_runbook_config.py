from __future__ import annotations

from pathlib import Path

from leadlag.ops import load_runbook_config, render_runbook_artifacts, validate_runbook_config


def test_runbook_config_loads_and_contains_required_keys() -> None:
    result = validate_runbook_config(Path("configs/ops/runbook_shadow_v1.yaml"))
    assert result.passed
    summary = result.summary
    assert summary["runbook_id"] == "shadow_ops_runbook_v1"
    assert summary["scope"] == "shadow_pre_live"


def test_runbook_has_required_packet_files_and_statuses() -> None:
    config = load_runbook_config(Path("configs/ops/runbook_shadow_v1.yaml"))
    for required_file in [
        "summary.md",
        "run.json",
        "signals.csv",
        "orders_shadow.csv",
        "fills_shadow.csv",
        "positions.csv",
        "pnl.csv",
        "risk_report.json",
        "alerts.json",
    ]:
        assert required_file in config["required_daily_packet_files"]
    for status_name in ["GO", "WARN", "STOP", "HOLD_SHADOW", "READY_FOR_SMALL_LIVE", "BLOCKED"]:
        assert status_name in config["status_actions"]


def test_runbook_has_required_incident_levels() -> None:
    config = load_runbook_config(Path("configs/ops/runbook_shadow_v1.yaml"))
    for level_name in ["P0", "P1", "P2", "P3"]:
        assert level_name in config["incident_levels"]


def test_validator_catches_missing_key(tmp_path: Path) -> None:
    broken = tmp_path / "broken_runbook.yaml"
    broken.write_text(
        """
runbook_id: broken
version: 1
status_actions: {}
incident_levels: {}
required_daily_packet_files: []
canonical_sidecars_when_enabled: []
checklists: {}
manual_override_policy: text
kill_switch_policy: text
ai_review_policy: text
""".strip(),
        encoding="utf-8",
    )
    result = validate_runbook_config(broken)
    assert not result.passed
    assert any(issue.code == "missing_top_level_keys" for issue in result.issues)


def test_validator_catches_duplicate_yaml_keys(tmp_path: Path) -> None:
    broken = tmp_path / "duplicate_runbook.yaml"
    broken.write_text(
        """
runbook_id: duplicate
version: 1
scope: shadow_pre_live
status_actions:
  GO:
    summary: one
    required_action: action
    shadow_continues: true
    escalation: none
    notes: note
  GO:
    summary: two
    required_action: action
    shadow_continues: true
    escalation: none
    notes: note
incident_levels: {}
required_daily_packet_files: []
canonical_sidecars_when_enabled: []
checklists: {}
manual_override_policy: text
kill_switch_policy: text
ai_review_policy: text
""".strip(),
        encoding="utf-8",
    )
    result = validate_runbook_config(broken)
    assert not result.passed
    assert any(issue.code == "duplicate_yaml_key" for issue in result.issues)


def test_renderer_writes_expected_artifacts(tmp_path: Path) -> None:
    result = render_runbook_artifacts(
        Path("configs/ops/runbook_shadow_v1.yaml"),
        tmp_path / "runbook_artifacts",
    )
    assert result.passed
    for artifact_name in [
        "runbook_validation_json",
        "runbook_summary_md",
        "daily_checklist_md",
        "weekly_checklist_md",
        "incident_matrix_md",
    ]:
        assert artifact_name in result.output_paths
        assert Path(result.output_paths[artifact_name]).exists()
