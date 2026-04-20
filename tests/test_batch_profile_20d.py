from pathlib import Path

from leadlag.config.loader import load_app_config



def test_shadow_batch_20d_local_profile_loads() -> None:
    cfg = load_app_config(Path('configs/profiles/shadow_corrected_batch_20d_local.yaml'))
    assert cfg.run.mode == 'shadow'
    assert cfg.batch.enabled is True
    assert cfg.batch.max_days == 20
    assert str(cfg.batch.end_date) == '2025-11-28'
    assert cfg.run.name == 'shadow_corrected_batch_20d_local'
