from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from leadlag.config.models import AppConfig


@dataclass(slots=True)
class SignalOutput:
    date: pd.Timestamp
    signal: pd.Series
    metadata: Dict[str, object]


def pca_sub_signal(cfg: AppConfig, returns_cc: pd.DataFrame, asof_date: pd.Timestamp) -> SignalOutput:
    """Scaffold only.

    Production version should:
    1. build Ct on the rolling window W_t = {t-L, ..., t-1}
    2. construct C0 from prior basis and C_full policy
    3. form C_reg = (1-lambda) Ct + lambda C0
    4. eigen-decompose and produce JP signal for t+1
    """
    jp_names = cfg.universe.jp
    signal = pd.Series(0.0, index=jp_names, name="signal_raw")
    return SignalOutput(
        date=asof_date,
        signal=signal,
        metadata={
            "strategy": cfg.strategy.name,
            "L": cfg.strategy.lookback_L,
            "K": cfg.strategy.n_components_K,
            "lambda": cfg.strategy.lambda_reg,
        },
    )
