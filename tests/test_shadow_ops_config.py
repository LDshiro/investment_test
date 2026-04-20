from __future__ import annotations

from pathlib import Path

import pytest

from leadlag.ops import load_shadow_ops_config
from leadlag.ops.shadow_ops import ShadowOpsConfigError


def test_legacy_shadow_ops_config_loads() -> None:
    cfg = load_shadow_ops_config(Path("configs/ops/shadow_ops_legacy_60d_local.yaml"))
    assert cfg["ops"]["name"] == "shadow_ops_legacy_60d_local"
    assert cfg["ops"]["mode"] == "shadow_only"
    assert cfg["ops"]["variant"] == "legacy"


def test_canonical_shadow_ops_config_inherits_and_overrides() -> None:
    cfg = load_shadow_ops_config(Path("configs/ops/shadow_ops_canonical_60d_local.yaml"))
    assert cfg["ops"]["name"] == "shadow_ops_canonical_60d_local"
    assert cfg["ops"]["mode"] == "shadow_only"
    assert cfg["ops"]["variant"] == "canonical"
    assert cfg["stages"]["run_batch"]["config"] == "configs/profiles/shadow_corrected_canonical_batch_60d_local.yaml"
    assert cfg["stages"]["validate_shadow_replay"]["config"] == "configs/validation/shadow_replay_canonical_v1.yaml"


def test_required_stages_exist() -> None:
    cfg = load_shadow_ops_config(Path("configs/ops/shadow_ops_legacy_60d_local.yaml"))
    for stage_name in [
        "validate_data_contract",
        "run_batch",
        "validate_shadow_replay",
        "weekly_review",
        "weekly_gates",
        "render_runbook",
    ]:
        assert stage_name in cfg["stages"]
        assert "enabled" in cfg["stages"][stage_name]


def test_missing_existing_batch_dir_rejected_when_run_batch_disabled(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_shadow_ops.yaml"
    config_path.write_text(
        """
ops:
  name: invalid_shadow_ops
  mode: shadow_only
  variant: legacy
  artifact_root: artifacts/shadow_ops
  stop_on_stage_failure: true
  overwrite_existing: false
  timestamp_outputs: true
  operator_digest: true
stages:
  validate_data_contract:
    enabled: true
    bundle_dir: data/normalized/corrected_bundle
    contract: configs/data_contracts/corrected_bundle_v1.yaml
  run_batch:
    enabled: false
    config: configs/profiles/shadow_corrected_batch_60d_local.yaml
  validate_shadow_replay:
    enabled: true
    config: configs/validation/shadow_replay_v1.yaml
  weekly_review:
    enabled: true
  weekly_gates:
    enabled: true
    rules_config: configs/review/weekly_rules_shadow_pre_live_v1.yaml
  render_runbook:
    enabled: true
    config: configs/ops/runbook_shadow_v1.yaml
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ShadowOpsConfigError):
        load_shadow_ops_config(config_path)


def test_missing_existing_review_dir_rejected_when_weekly_review_disabled(tmp_path: Path) -> None:
    existing_batch_dir = tmp_path / "existing_batch"
    existing_batch_dir.mkdir()
    config_path = tmp_path / "invalid_shadow_ops_review.yaml"
    config_path.write_text(
        f"""
ops:
  name: invalid_shadow_ops_review
  mode: shadow_only
  variant: legacy
  artifact_root: artifacts/shadow_ops
  stop_on_stage_failure: true
  overwrite_existing: false
  timestamp_outputs: true
  operator_digest: true
stages:
  validate_data_contract:
    enabled: true
    bundle_dir: data/normalized/corrected_bundle
    contract: configs/data_contracts/corrected_bundle_v1.yaml
  run_batch:
    enabled: false
    config: configs/profiles/shadow_corrected_batch_60d_local.yaml
    existing_batch_dir: {existing_batch_dir}
  validate_shadow_replay:
    enabled: true
    config: configs/validation/shadow_replay_v1.yaml
  weekly_review:
    enabled: false
  weekly_gates:
    enabled: true
    rules_config: configs/review/weekly_rules_shadow_pre_live_v1.yaml
  render_runbook:
    enabled: true
    config: configs/ops/runbook_shadow_v1.yaml
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ShadowOpsConfigError):
        load_shadow_ops_config(config_path)
