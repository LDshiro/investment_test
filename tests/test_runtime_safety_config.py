from __future__ import annotations

from pathlib import Path

import pytest

from leadlag.security.config import (
    DuplicateKeyError,
    load_execution_host_config,
    load_runtime_security_policy,
    load_secrets_inventory,
)


def test_runtime_safety_configs_load() -> None:
    policy = load_runtime_security_policy("configs/security/runtime_security_policy_v1.yaml")
    inventory = load_secrets_inventory("configs/security/secrets_inventory_v1.yaml")
    host = load_execution_host_config("configs/runtime/execution_host_local_v1.yaml")

    assert policy["runtime_flags"]["allow_live_without_human_approval"] is False
    assert inventory["secrets"][0]["required_now"] is False
    assert host["expected"]["timezone"] == "Asia/Tokyo"


def test_loader_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    broken = tmp_path / "duplicate_policy.yaml"
    broken.write_text(
        """
version: runtime_security_policy_v1
version: duplicate
stance: shadow_only_until_explicit_human_approval
forbidden: {}
forbidden_secret_files: []
secret_redaction:
  redact_patterns: []
  replacement: "***REDACTED***"
environment_snapshot_prefixes: []
runtime_flags: {}
logging: {}
backups: {}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateKeyError):
        load_runtime_security_policy(broken)


def test_loader_rejects_missing_required_fields(tmp_path: Path) -> None:
    broken = tmp_path / "host.yaml"
    broken.write_text(
        """
version: execution_host_local_v1
expected:
  timezone: Asia/Tokyo
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        load_execution_host_config(broken)
