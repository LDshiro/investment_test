from __future__ import annotations

from typing import List

from leadlag.config.models import AppConfig


def build_trade_universe(cfg: AppConfig) -> List[str]:
    return list(cfg.universe.jp)
