from pathlib import Path

from leadlag.config.loader import load_app_config


def test_corrected_bundle_profile_uses_session_filenames() -> None:
    cfg_path = Path('configs/profiles/backtest_corrected.yaml')
    cfg = load_app_config(cfg_path)
    assert cfg.data.files['ff3'] == 'ff3_japan_daily.csv'
    assert cfg.data.files['mom'] == 'mom_japan_daily.csv'
    assert cfg.data.files['carhart4'] == 'carhart4_japan_daily.csv'
