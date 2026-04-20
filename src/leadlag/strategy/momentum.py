from __future__ import annotations

import pandas as pd


def momentum_signal(returns_cc_jp: pd.DataFrame, lookback: int) -> pd.Series:
    return returns_cc_jp.tail(lookback).mean(axis=0)
