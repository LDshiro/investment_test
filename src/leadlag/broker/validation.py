from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import math

import yaml

from .models import BrokerDiagnostic, BrokerMode, OrderIntent


REPO_ROOT = Path(__file__).resolve().parents[3]
BROKER_STATUSES = {"research_only", "dry_run_only", "paper_candidate", "live_candidate"}
REQUIRED_CANDIDATE_KEYS = {
    "schema_version",
    "broker_id",
    "display_name",
    "status",
    "supported_markets",
    "supported_asset_types",
    "order_types_known",
    "time_in_force_known",
    "supports_paper",
    "supports_live_api",
    "supports_shortability_check",
    "supports_position_query",
    "supports_order_status_query",
    "operational_requirements",
    "known_limits",
    "safety_notes",
    "open_questions",
    "source_urls",
    "decision_scores",
    "research_facts",
}
REQUIRED_SELECTION_KEYS = {
    "schema_version",
    "selection_id",
    "candidate_configs",
    "weights",
    "default_safe_adapter",
    "future_external_comparison",
}
REQUIRED_WEIGHT_KEYS = {
    "operational_safety",
    "jp_cash_equity_fit",
    "dry_run_readiness",
    "paper_progression_clarity",
    "live_api_maturity",
    "observability",
}


class BrokerConfigError(RuntimeError):
    pass


class DuplicateKeyError(BrokerConfigError):
    pass


class BrokerValidationError(BrokerConfigError):
    def __init__(self, message: str, diagnostics: list[BrokerDiagnostic] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or []


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
        raise BrokerConfigError(f"broker config not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=UniqueKeyLoader) or {}
    except DuplicateKeyError:
        raise
    except yaml.YAMLError as exc:
        raise BrokerConfigError(f"invalid YAML in broker config: {path}") from exc
    if not isinstance(data, dict):
        raise BrokerConfigError("broker config must deserialize to a mapping")
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
        raise BrokerConfigError(f"missing required {label}: {', '.join(missing)}")


def _require_list_of_strings(data: dict[str, Any], key: str) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BrokerConfigError(f"{key} must be a list of strings")


def _require_bool(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), bool):
        raise BrokerConfigError(f"{key} must be a boolean")


def load_broker_candidate_config(path: Path | str) -> dict[str, Any]:
    cfg_path = _resolve_repo_path(path)
    data = _load_yaml_with_extends(cfg_path)
    _require_keys(data, REQUIRED_CANDIDATE_KEYS, "candidate config keys")
    if data.get("status") not in BROKER_STATUSES:
        raise BrokerConfigError(f"invalid broker candidate status: {data.get('status')}")

    for key in [
        "supported_markets",
        "supported_asset_types",
        "order_types_known",
        "time_in_force_known",
        "operational_requirements",
        "known_limits",
        "safety_notes",
        "open_questions",
        "source_urls",
    ]:
        _require_list_of_strings(data, key)
    for key in [
        "supports_paper",
        "supports_live_api",
        "supports_shortability_check",
        "supports_position_query",
        "supports_order_status_query",
    ]:
        _require_bool(data, key)

    if not isinstance(data.get("decision_scores"), dict):
        raise BrokerConfigError("decision_scores must be a mapping")
    _require_keys(data["decision_scores"], REQUIRED_WEIGHT_KEYS, "decision_scores keys")
    if not isinstance(data.get("research_facts"), list):
        raise BrokerConfigError("research_facts must be a list")
    for fact in data["research_facts"]:
        if not isinstance(fact, dict):
            raise BrokerConfigError("research_facts entries must be mappings")
        _require_keys(fact, {"fact_id", "summary", "source_url"}, "research_facts entry keys")

    data["_config_path"] = str(cfg_path)
    return data


def load_broker_selection_config(path: Path | str) -> dict[str, Any]:
    cfg_path = _resolve_repo_path(path)
    data = _load_yaml_with_extends(cfg_path)
    _require_keys(data, REQUIRED_SELECTION_KEYS, "selection config keys")
    if not isinstance(data.get("candidate_configs"), list) or not all(isinstance(item, str) for item in data["candidate_configs"]):
        raise BrokerConfigError("candidate_configs must be a list of config paths")
    if not isinstance(data.get("weights"), dict):
        raise BrokerConfigError("weights must be a mapping")
    _require_keys(data["weights"], REQUIRED_WEIGHT_KEYS, "selection weight keys")
    for key in REQUIRED_WEIGHT_KEYS:
        value = data["weights"][key]
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
            raise BrokerConfigError(f"weight '{key}' must be a non-negative finite number")

    for item in data["candidate_configs"]:
        load_broker_candidate_config(item)
    data["_config_path"] = str(cfg_path)
    return data


def validate_order_intent(intent: OrderIntent, *, adapter_mode: BrokerMode | None = None) -> list[BrokerDiagnostic]:
    diagnostics: list[BrokerDiagnostic] = []
    if intent.allow_live_submission:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="live_submission_forbidden",
                message="allow_live_submission must remain false in Step 09.",
            )
        )
    if adapter_mode in {BrokerMode.PAPER, BrokerMode.LIVE}:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="unsafe_adapter_mode",
                message=f"Broker mode {adapter_mode.value} is not allowed for Step 09 dry-run adapters.",
            )
        )
    if intent.quantity is None and intent.notional_jpy is None:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="missing_quantity_and_notional",
                message="OrderIntent must include quantity or notional_jpy.",
            )
        )
    if intent.quantity is not None and float(intent.quantity) <= 0:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="non_positive_quantity",
                message="OrderIntent quantity must be positive when provided.",
                details={"quantity": float(intent.quantity)},
            )
        )
    if intent.notional_jpy is not None and float(intent.notional_jpy) == 0.0:
        diagnostics.append(
            BrokerDiagnostic(
                severity="WARN",
                code="zero_notional",
                message="OrderIntent notional_jpy is zero.",
                details={"notional_jpy": float(intent.notional_jpy)},
            )
        )
    if not intent.run_id:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="missing_run_id",
                message="OrderIntent run_id is required.",
            )
        )
    if not intent.trade_date:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="missing_trade_date",
                message="OrderIntent trade_date is required.",
            )
        )
    if not intent.symbol:
        diagnostics.append(
            BrokerDiagnostic(
                severity="ERROR",
                code="missing_symbol",
                message="OrderIntent symbol is required.",
            )
        )
    return diagnostics


def raise_for_error_diagnostics(diagnostics: list[BrokerDiagnostic], *, context: str) -> None:
    errors = [diag for diag in diagnostics if diag.severity == "ERROR"]
    if errors:
        codes = ", ".join(diag.code for diag in errors)
        raise BrokerValidationError(f"{context}: {codes}", diagnostics=diagnostics)
