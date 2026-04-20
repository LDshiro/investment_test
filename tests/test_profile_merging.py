from pathlib import Path

from leadlag.config.loader import load_app_config


def test_shadow_profile_preserves_component_overrides() -> None:
    cfg = load_app_config(Path('configs/profiles/shadow_corrected.yaml'))
    assert cfg.costs.open_half_spread_bps == 6.0
    assert cfg.costs.slippage_open_bps == 4.0
    assert cfg.risk.max_gross == 1.0
    assert cfg.risk.max_single_name_abs == 0.15
    assert cfg.risk.allow_short is False


def test_shadow_local_profile_has_historical_trade_date() -> None:
    cfg = load_app_config(Path('configs/profiles/shadow_corrected_local.yaml'))
    assert str(cfg.run.historical_trade_date) == '2025-11-28'
    assert cfg.run.shadow_nav_jpy == 1_000_000.0
