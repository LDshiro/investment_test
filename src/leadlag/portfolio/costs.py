from __future__ import annotations

from leadlag.config.models import AppConfig


def open_side_cost_bps(cfg: AppConfig) -> float:
    return cfg.costs.commission_bps + cfg.costs.open_half_spread_bps + cfg.costs.slippage_open_bps


def close_side_cost_bps(cfg: AppConfig) -> float:
    return cfg.costs.commission_bps + cfg.costs.close_half_spread_bps + cfg.costs.slippage_close_bps


def expected_roundtrip_cost_bps(
    cfg: AppConfig,
    gross_exposure: float = 1.0,
    short_exposure: float = 0.0,
) -> float:
    carry_bps = 0.0
    if short_exposure > 0.0 and cfg.costs.borrow_fee_bps_annual > 0.0:
        annualization_days = cfg.strategy.annualization_days or 252
        carry_bps = short_exposure * (cfg.costs.borrow_fee_bps_annual / annualization_days)
    return gross_exposure * (open_side_cost_bps(cfg) + close_side_cost_bps(cfg)) + carry_bps
