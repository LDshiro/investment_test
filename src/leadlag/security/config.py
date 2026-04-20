from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_POLICY_KEYS = {
    "version",
    "stance",
    "forbidden",
    "forbidden_secret_files",
    "secret_redaction",
    "environment_snapshot_prefixes",
    "runtime_flags",
    "logging",
    "backups",
}
REQUIRED_POLICY_FORBIDDEN_KEYS = {
    "commit_real_secrets",
    "print_secret_values",
    "live_order_submission_without_two_step_enable",
    "broker_network_connection_in_step10",
    "auto_promote_ready_for_small_live",
}
REQUIRED_POLICY_REDACTION_KEYS = {"redact_patterns", "replacement"}
REQUIRED_POLICY_RUNTIME_KEYS = {
    "require_kill_switch_file_check",
    "kill_switch_file",
    "trading_disabled_file",
    "allow_shadow_without_secrets",
    "allow_dryrun_without_secrets",
    "allow_live_without_human_approval",
}
REQUIRED_POLICY_LOGGING_KEYS = {"forbid_secret_values_in_logs", "max_log_file_mb"}
REQUIRED_POLICY_BACKUP_KEYS = {"require_daily_artifact_backup_plan", "require_restore_test_plan"}
REQUIRED_SECRET_ENTRY_KEYS = {"name", "required_for_modes", "required_now", "source", "never_commit"}
REQUIRED_HOST_KEYS = {"version", "expected"}
REQUIRED_HOST_EXPECTED_KEYS = {
    "timezone",
    "python_version_file",
    "required_directories",
    "no_real_secrets_in_repo",
    "git_clean_required_for_live",
    "git_clean_required_for_shadow",
    "network_required_for_shadow",
    "scheduler_installed_required_now",
}


class RuntimeSecurityConfigError(RuntimeError):
    pass


class DuplicateKeyError(RuntimeSecurityConfigError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(f"duplicate YAML key detected: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve(strict=False)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeSecurityConfigError(f"config not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=UniqueKeyLoader) or {}
    except DuplicateKeyError:
        raise
    except yaml.YAMLError as exc:
        raise RuntimeSecurityConfigError(f"invalid YAML in config: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeSecurityConfigError("config must deserialize to a mapping")
    return data


def _load_yaml_with_extends(path: Path) -> dict[str, Any]:
    data = _load_yaml(path)
    merged: dict[str, Any] = {}
    for rel in data.get("extends", []) or []:
        parent = (path.parent / rel).resolve()
        merged = _deep_merge(merged, _load_yaml_with_extends(parent))
    return _deep_merge(merged, data)


def _require_keys(data: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(data.keys()))
    if missing:
        raise RuntimeSecurityConfigError(f"missing required {label}: {', '.join(missing)}")


def _require_bool(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), bool):
        raise RuntimeSecurityConfigError(f"{key} must be a boolean")


def _require_list_of_strings(data: dict[str, Any], key: str) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeSecurityConfigError(f"{key} must be a list of strings")


def load_runtime_security_policy(path: Path | str) -> dict[str, Any]:
    cfg_path = _resolve_repo_path(path)
    data = _load_yaml_with_extends(cfg_path)
    _require_keys(data, REQUIRED_POLICY_KEYS, "runtime security policy keys")
    if not isinstance(data.get("forbidden"), dict):
        raise RuntimeSecurityConfigError("forbidden must be a mapping")
    _require_keys(data["forbidden"], REQUIRED_POLICY_FORBIDDEN_KEYS, "forbidden policy keys")
    for key in REQUIRED_POLICY_FORBIDDEN_KEYS:
        _require_bool(data["forbidden"], key)

    if not isinstance(data.get("secret_redaction"), dict):
        raise RuntimeSecurityConfigError("secret_redaction must be a mapping")
    _require_keys(data["secret_redaction"], REQUIRED_POLICY_REDACTION_KEYS, "secret_redaction keys")
    _require_list_of_strings(data, "forbidden_secret_files")
    _require_list_of_strings(data, "environment_snapshot_prefixes")
    _require_list_of_strings(data["secret_redaction"], "redact_patterns")
    if not isinstance(data["secret_redaction"].get("replacement"), str):
        raise RuntimeSecurityConfigError("secret_redaction.replacement must be a string")

    if not isinstance(data.get("runtime_flags"), dict):
        raise RuntimeSecurityConfigError("runtime_flags must be a mapping")
    _require_keys(data["runtime_flags"], REQUIRED_POLICY_RUNTIME_KEYS, "runtime_flags keys")
    for key in {
        "require_kill_switch_file_check",
        "allow_shadow_without_secrets",
        "allow_dryrun_without_secrets",
        "allow_live_without_human_approval",
    }:
        _require_bool(data["runtime_flags"], key)
    for key in {"kill_switch_file", "trading_disabled_file"}:
        if not isinstance(data["runtime_flags"].get(key), str):
            raise RuntimeSecurityConfigError(f"runtime_flags.{key} must be a string")

    if not isinstance(data.get("logging"), dict):
        raise RuntimeSecurityConfigError("logging must be a mapping")
    _require_keys(data["logging"], REQUIRED_POLICY_LOGGING_KEYS, "logging keys")
    _require_bool(data["logging"], "forbid_secret_values_in_logs")
    if not isinstance(data["logging"].get("max_log_file_mb"), (int, float)) or float(data["logging"]["max_log_file_mb"]) <= 0:
        raise RuntimeSecurityConfigError("logging.max_log_file_mb must be a positive number")

    if not isinstance(data.get("backups"), dict):
        raise RuntimeSecurityConfigError("backups must be a mapping")
    _require_keys(data["backups"], REQUIRED_POLICY_BACKUP_KEYS, "backups keys")
    for key in REQUIRED_POLICY_BACKUP_KEYS:
        _require_bool(data["backups"], key)

    data["_config_path"] = str(cfg_path)
    return data


def load_secrets_inventory(path: Path | str) -> dict[str, Any]:
    cfg_path = _resolve_repo_path(path)
    data = _load_yaml_with_extends(cfg_path)
    _require_keys(data, {"version", "secrets"}, "secrets inventory keys")
    if not isinstance(data.get("secrets"), list):
        raise RuntimeSecurityConfigError("secrets must be a list")
    for entry in data["secrets"]:
        if not isinstance(entry, dict):
            raise RuntimeSecurityConfigError("each secrets entry must be a mapping")
        _require_keys(entry, REQUIRED_SECRET_ENTRY_KEYS, "secret entry keys")
        if "value" in entry:
            raise RuntimeSecurityConfigError("secret entry must not define a value field")
        _require_list_of_strings(entry, "required_for_modes")
        _require_bool(entry, "required_now")
        _require_bool(entry, "never_commit")
        if not isinstance(entry.get("name"), str) or not entry["name"]:
            raise RuntimeSecurityConfigError("secret entry name must be a non-empty string")
        if not isinstance(entry.get("source"), str) or not entry["source"]:
            raise RuntimeSecurityConfigError("secret entry source must be a non-empty string")

    data["_config_path"] = str(cfg_path)
    return data


def load_execution_host_config(path: Path | str) -> dict[str, Any]:
    cfg_path = _resolve_repo_path(path)
    data = _load_yaml_with_extends(cfg_path)
    _require_keys(data, REQUIRED_HOST_KEYS, "execution host config keys")
    if not isinstance(data.get("expected"), dict):
        raise RuntimeSecurityConfigError("expected must be a mapping")
    _require_keys(data["expected"], REQUIRED_HOST_EXPECTED_KEYS, "execution host expected keys")
    _require_list_of_strings(data["expected"], "required_directories")
    for key in {
        "no_real_secrets_in_repo",
        "git_clean_required_for_live",
        "git_clean_required_for_shadow",
        "network_required_for_shadow",
        "scheduler_installed_required_now",
    }:
        _require_bool(data["expected"], key)
    for key in {"timezone", "python_version_file"}:
        if not isinstance(data["expected"].get(key), str) or not data["expected"][key]:
            raise RuntimeSecurityConfigError(f"expected.{key} must be a non-empty string")

    data["_config_path"] = str(cfg_path)
    return data
