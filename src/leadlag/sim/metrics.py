from __future__ import annotations

import numpy as np
import pandas as pd


def annualized_return(series: pd.Series, annualization_days: int = 252) -> float:
    return float(series.mean() * annualization_days)


def annualized_risk(series: pd.Series, annualization_days: int = 252) -> float:
    return float(series.std(ddof=1) * np.sqrt(annualization_days))


def max_drawdown(series: pd.Series) -> float:
    wealth = (1 + series.fillna(0)).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1.0
    return float(dd.min())
