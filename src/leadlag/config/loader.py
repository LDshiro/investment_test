from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml

from .models import AppConfig


class ConfigError(RuntimeError):
    pass


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc


def _load_with_extends(path: Path) -> Dict[str, Any]:
    data = _load_yaml(path)
    merged: Dict[str, Any] = {}
    for rel in data.get("extends", []) or []:
        parent = (path.parent / rel).resolve()
        merged = _deep_merge(merged, _load_with_extends(parent))
    merged = _deep_merge(merged, data)
    return merged


def load_app_config(path: Path) -> AppConfig:
    cfg = _load_with_extends(path.resolve())
    if hasattr(AppConfig, "model_validate"):
        return AppConfig.model_validate(cfg)
    return AppConfig.parse_obj(cfg)
