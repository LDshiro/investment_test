
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .tickers import (
    US_TICKERS, JP_TICKERS,
    US_CYCLICAL, US_DEFENSIVE, JP_CYCLICAL, JP_DEFENSIVE
)
from .utils import gram_schmidt_columns, standardize_with_window

@dataclass(slots=True)
class PriorTarget:
    tickers: list[str]
    v0: np.ndarray
    d0: np.ndarray
    c0_raw: np.ndarray
    c0_corr: np.ndarray

def build_prior_basis(tickers: list[str]) -> np.ndarray:
    n = len(tickers)
    if n < 3:
        raise ValueError("Need at least 3 assets for the 3-dimensional prior subspace.")

    us_mask = np.array([t in US_TICKERS for t in tickers], dtype=float)
    jp_mask = np.array([t in JP_TICKERS for t in tickers], dtype=float)

    v1 = np.ones(n, dtype=float)

    v2 = np.where(us_mask == 1.0, 1.0, -1.0)

    v3 = np.zeros(n, dtype=float)
    for i, ticker in enumerate(tickers):
        if ticker in US_CYCLICAL or ticker in JP_CYCLICAL:
            v3[i] = 1.0
        elif ticker in US_DEFENSIVE or ticker in JP_DEFENSIVE:
            v3[i] = -1.0
        else:
            v3[i] = 0.0

    return gram_schmidt_columns(np.column_stack([v1, v2, v3]))

def standardized_correlation(returns: pd.DataFrame) -> np.ndarray:
    values = returns.to_numpy(dtype=float)
    z, _, _ = standardize_with_window(values)
    if np.isnan(z).any():
        raise ValueError("Cannot build correlation: zero volatility in at least one column.")
    c = (z.T @ z) / values.shape[0]
    c = 0.5 * (c + c.T)
    np.fill_diagonal(c, 1.0)
    return c

def build_prior_target(cfull_returns: pd.DataFrame) -> PriorTarget:
    tickers = list(cfull_returns.columns)
    v0 = build_prior_basis(tickers)
    cfull = standardized_correlation(cfull_returns)
    d0 = np.diag(v0.T @ cfull @ v0)
    c0_raw = v0 @ np.diag(d0) @ v0.T
    delta = np.diag(c0_raw).copy()
    delta = np.where(delta <= 0.0, np.nan, delta)
    scale = np.diag(1.0 / np.sqrt(delta))
    c0_corr = scale @ c0_raw @ scale
    c0_corr = 0.5 * (c0_corr + c0_corr.T)
    np.fill_diagonal(c0_corr, 1.0)
    return PriorTarget(
        tickers=tickers,
        v0=v0,
        d0=d0,
        c0_raw=c0_raw,
        c0_corr=c0_corr,
    )

def regularize_corr(ct: np.ndarray, c0: np.ndarray, lambda_reg: float) -> np.ndarray:
    c = (1.0 - lambda_reg) * ct + lambda_reg * c0
    c = 0.5 * (c + c.T)
    np.fill_diagonal(c, 1.0)
    return c

def top_eigenspace(corr: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    k = min(k, vecs.shape[1])
    return vals[:k], vecs[:, :k]
