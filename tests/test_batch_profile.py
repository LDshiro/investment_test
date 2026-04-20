from pathlib import Path

from leadlag.config.loader import load_app_config


def test_shadow_batch_local_profile_loads() -> None:
    cfg = load_app_config(Path('configs/profiles/shadow_corrected_batch_local.yaml'))
    assert cfg.run.mode == "shadow"
    assert cfg.batch.enabled is True
    assert cfg.batch.date_source == "sample_filter"
    assert str(cfg.batch.end_date) == "2025-11-28"
    assert cfg.batch.max_days == 5
