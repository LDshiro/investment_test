from pathlib import Path

from leadlag.config.loader import load_app_config


def test_load_profile_config() -> None:
    cfg = load_app_config(Path("configs/profiles/backtest_corrected.yaml"))
    assert cfg.run.mode == "backtest"
    assert cfg.strategy.lookback_L == 60
    assert cfg.strategy.lambda_reg == 0.9
