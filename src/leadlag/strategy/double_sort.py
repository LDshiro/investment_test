from __future__ import annotations

import pandas as pd


def double_sort_signal(signal_a: pd.Series, signal_b: pd.Series) -> pd.Series:
    # placeholder: intersection-high minus intersection-low ranking
    return (signal_a.rank(pct=True) + signal_b.rank(pct=True)) / 2.0
