from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

from leadlag.config.models import AppConfig


DEFAULT_REQUIRED = [
    "summary.md",
    "run.json",
    "signals.csv",
    "orders_shadow.csv",
    "fills_shadow.csv",
    "positions.csv",
    "pnl.csv",
    "risk_report.json",
    "alerts.json",
]


def ensure_packet_layout(cfg: AppConfig, packet_name: str | None = None) -> Path:
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    leaf = packet_name or f"{cfg.run.name}_{run_ts}"
    packet_dir = Path(cfg.run.runs_root) / leaf
    packet_dir.mkdir(parents=True, exist_ok=True)

    required = cfg.packet.required_files or DEFAULT_REQUIRED
    for name in required:
        p = packet_dir / name
        if not p.exists():
            if name.endswith(".json"):
                p.write_text(json.dumps({"placeholder": True}, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                p.write_text("", encoding="utf-8")
    return packet_dir
