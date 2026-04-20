
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

def sanitize_ticker_for_filename(ticker: str) -> str:
    return ticker.replace("/", "_").replace("=", "_")

def candidate_csv_paths(root: Path, ticker: str) -> list[Path]:
    safe = sanitize_ticker_for_filename(ticker)
    return [
        root / f"{ticker}.csv",
        root / f"{safe}.csv",
        root / f"{ticker.replace('.', '_')}.csv",
        root / f"{safe.replace('.', '_')}.csv",
    ]

def first_existing_path(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None

def annualize_mean(mean_daily: float, base: int) -> float:
    return mean_daily * base

def annualize_vol(std_daily: float, base: int) -> float:
    return std_daily * np.sqrt(base)

def running_mdd(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1.0
    return float(-dd.min()) if len(dd) else np.nan

def paper_formula_mdd(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    if wealth.empty:
        return np.nan
    peak_full = wealth.max()
    dd = wealth / peak_full - 1.0
    dd = np.minimum(dd, 0.0)
    return float(-dd.min())

def raw_kurtosis(x: pd.Series) -> float:
    return float(x.kurt() + 3.0)

def ensure_datetime_index(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    if date_col in df.columns:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame must have a DatetimeIndex.")
    return df.sort_index()

def standardize_with_window(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = values.mean(axis=0)
    # Paper uses denominator 1/L, so ddof=0.
    sigma = values.std(axis=0, ddof=0)
    sigma = np.where(sigma == 0.0, np.nan, sigma)
    z = (values - mu) / sigma
    return z, mu, sigma

def gram_schmidt_columns(mat: np.ndarray, tol: float = 1e-12) -> np.ndarray:
    cols: list[np.ndarray] = []
    for j in range(mat.shape[1]):
        v = mat[:, j].astype(float).copy()
        for q in cols:
            v = v - np.dot(q, v) * q
        n = np.linalg.norm(v)
        if n > tol:
            cols.append(v / n)
    if not cols:
        raise ValueError("No non-zero vectors survived orthogonalization.")
    return np.column_stack(cols)

def nearest_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)
