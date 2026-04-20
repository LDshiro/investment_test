from __future__ import annotations

from typing import Dict, List

import pandas as pd

from leadlag.config.models import AppConfig


def _severity(code: str, cfg: AppConfig, *, default_critical: bool = False) -> str:
    if code in set(cfg.risk.hard_gates):
        return "critical"
    if code == "missing_price" and cfg.risk.halt_on_missing_price:
        return "critical"
    if code == "unapproved_patch" and cfg.risk.halt_on_unapproved_patch:
        return "critical"
    if default_critical:
        return "critical"
    return "warning"


def evaluate_hard_gates(
    cfg: AppConfig,
    signal: pd.Series,
    candidate_weights: pd.Series | None = None,
    expected_cost_bps: float = 0.0,
    *,
    missing_price: bool = False,
    missing_factor: bool = False,
    patch_approved: bool = True,
    no_common_dates: bool = False,
    universe_expected: int | None = None,
) -> Dict[str, object]:
    signal = signal.dropna().astype(float)
    weights = (candidate_weights if candidate_weights is not None else pd.Series(dtype=float)).fillna(0.0).astype(float)

    tradable_names = int(signal.shape[0])
    selected_names = int((weights != 0.0).sum())
    gross_exposure = float(weights.abs().sum()) if not weights.empty else 0.0
    net_exposure = float(weights.sum()) if not weights.empty else 0.0
    max_name_abs = float(weights.abs().max()) if not weights.empty else 0.0

    gate_results: Dict[str, Dict[str, object]] = {}
    alerts: List[dict] = []

    def register(code: str, triggered: bool, message: str, *, default_critical: bool = False) -> None:
        sev = _severity(code, cfg, default_critical=default_critical) if triggered else "ok"
        gate_results[code] = {
            "triggered": bool(triggered),
            "severity": sev,
            "message": message if triggered else "not triggered",
        }
        if triggered:
            alerts.append({"severity": sev, "code": code, "message": message})

    register("no_common_dates", no_common_dates, "Requested trade date is not in the inferred sample window.", default_critical=True)
    register("missing_price", missing_price, "Open/close price is missing for at least one required name.")
    register("missing_factor", missing_factor, "One or more factor rows are missing for the trade date.")
    register("unapproved_patch", not patch_approved, "Patch table contains unapproved rows or cannot be verified.")
    register(
        "tradable_names_too_few",
        tradable_names < cfg.risk.min_tradable_names,
        f"Tradable names {tradable_names} is below min_tradable_names={cfg.risk.min_tradable_names}.",
        default_critical=True,
    )
    register(
        "cost_too_high",
        expected_cost_bps > cfg.risk.max_expected_cost_bps,
        f"Expected round-trip cost {expected_cost_bps:.2f} bps exceeds max_expected_cost_bps={cfg.risk.max_expected_cost_bps:.2f}.",
        default_critical=True,
    )
    register(
        "gross_exposure_exceeded",
        gross_exposure > cfg.risk.max_gross + 1e-12,
        f"Gross exposure {gross_exposure:.4f} exceeds max_gross={cfg.risk.max_gross:.4f}.",
        default_critical=True,
    )
    if cfg.risk.allow_short:
        register(
            "net_exposure_exceeded",
            abs(net_exposure) > cfg.risk.max_net + 1e-12,
            f"Net exposure {net_exposure:.4f} exceeds max_net={cfg.risk.max_net:.4f}.",
            default_critical=True,
        )
    register(
        "max_single_name_abs_exceeded",
        max_name_abs > cfg.risk.max_single_name_abs + 1e-12,
        f"Max single-name absolute weight {max_name_abs:.4f} exceeds max_single_name_abs={cfg.risk.max_single_name_abs:.4f}.",
        default_critical=True,
    )
    if universe_expected is not None and universe_expected > 0:
        register(
            "universe_shrinkage",
            tradable_names < universe_expected,
            f"Tradable universe shrank to {tradable_names} from expected {universe_expected} names.",
            default_critical=False,
        )

    has_critical = any(a["severity"] == "critical" for a in alerts)
    has_warning = any(a["severity"] == "warning" for a in alerts)
    status = "STOP" if has_critical else ("WARN" if has_warning else "GO")
    return {
        "status": status,
        "alerts": alerts,
        "gate_results": gate_results,
        "expected_cost_bps": expected_cost_bps,
        "tradable_names": tradable_names,
        "selected_names": selected_names,
        "gross_exposure": gross_exposure,
        "net_exposure": net_exposure,
        "max_name_abs": max_name_abs,
    }
