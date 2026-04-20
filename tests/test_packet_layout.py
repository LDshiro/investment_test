from pathlib import Path
import tempfile

from leadlag.config.loader import load_app_config
from leadlag.runtime.packets import ensure_packet_layout


def test_packet_dir_creation() -> None:
    cfg = load_app_config(Path("configs/profiles/shadow_corrected.yaml"))
    with tempfile.TemporaryDirectory() as tmp:
        cfg.run.runs_root = tmp  # type: ignore[misc]
        packet_dir = ensure_packet_layout(cfg)
        assert packet_dir.exists()
        assert (packet_dir / "run.json").exists()
