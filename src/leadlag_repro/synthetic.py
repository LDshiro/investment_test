
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .config import ReproConfig
from .paper_math import build_prior_basis
from .tickers import ALL_TICKERS, US_TICKERS, JP_TICKERS
from .utils import gram_schmidt_columns

def _clip_returns(x: np.ndarray, lo: float = -0.18, hi: float = 0.18) -> np.ndarray:
    return np.clip(x, lo, hi)

def _make_price_frame(
    dates: pd.DatetimeIndex,
    cc_ret: np.ndarray,
    oc_ret: np.ndarray,
    start_price: float,
    rng: np.random.Generator,
    ticker: str,
) -> pd.DataFrame:
    n = len(dates)
    cc_ret = _clip_returns(cc_ret)
    oc_ret = _clip_returns(oc_ret)

    open_px = np.zeros(n, dtype=float)
    high_px = np.zeros(n, dtype=float)
    low_px = np.zeros(n, dtype=float)
    close_px = np.zeros(n, dtype=float)
    volume = rng.integers(50_000, 2_000_000, size=n)

    prev_close = float(start_price)
    for i in range(n):
        denom = 1.0 + oc_ret[i]
        if denom <= 0.0:
            denom = 1e-6
        overnight = (1.0 + cc_ret[i]) / denom - 1.0
        overnight = float(np.clip(overnight, -0.18, 0.18))
        o = prev_close * (1.0 + overnight)
        c = o * (1.0 + oc_ret[i])
        wiggle_hi = abs(rng.normal(0.004, 0.003))
        wiggle_lo = abs(rng.normal(0.004, 0.003))
        h = max(o, c) * (1.0 + wiggle_hi)
        l = min(o, c) * max(1e-6, 1.0 - wiggle_lo)

        open_px[i] = max(o, 0.1)
        high_px[i] = max(h, open_px[i], c)
        low_px[i] = max(min(l, open_px[i], c), 0.05)
        close_px[i] = max(c, 0.1)
        prev_close = close_px[i]

    df = pd.DataFrame(
        {
            "ticker": ticker,
            "raw_open": open_px,
            "raw_high": high_px,
            "raw_low": low_px,
            "raw_close": close_px,
            "adj_close": close_px,
            "volume": volume.astype(float),
            "adj_factor": 1.0,
            "adj_open": open_px,
            "adj_high": high_px,
            "adj_low": low_px,
        },
        index=dates,
    )
    df["ret_cc_raw"] = df["raw_close"].pct_change()
    df["ret_cc_adj"] = df["adj_close"].pct_change()
    df["ret_oc_raw"] = df["raw_close"] / df["raw_open"] - 1.0
    df["ret_oc_adj"] = df["adj_close"] / df["adj_open"] - 1.0
    return df

def generate_synthetic_dataset(
    config: ReproConfig,
    alignment_mode: str | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, ReproConfig]:
    '''
    Generate a synthetic market in which:
    - same-day JP close-to-close returns share a low-rank structure with U.S. close-to-close returns
    - next-day JP open-to-close returns are driven by the previous U.S. factor shock
    - JP-specific persistent components create some momentum exposure
    This lets the full pipeline (Table 1 -> Table 4 style) run without external downloads.
    '''
    rng = np.random.default_rng(config.synthetic_seed)
    dates = pd.bdate_range(config.cfull_start, config.eval_end)
    n = len(dates)
    nu = len(US_TICKERS)
    nj = len(JP_TICKERS)

    prior_basis = build_prior_basis(ALL_TICKERS)
    true_basis = gram_schmidt_columns(prior_basis + rng.normal(0.0, 0.10, size=prior_basis.shape))
    vu_true = true_basis[:nu, :]
    vj_true = true_basis[nu:, :]

    # Common latent shocks. Factor 1 is strongest, factor 3 weakest.
    g = np.column_stack(
        [
            rng.normal(0.0, 0.010, size=n),
            rng.normal(0.0, 0.007, size=n),
            rng.normal(0.0, 0.005, size=n),
        ]
    )

    # Persistent Japan-specific components induce some momentum.
    jp_persist = np.zeros((n, nj), dtype=float)
    jp_innov = rng.normal(0.0, 0.0035, size=(n, nj))
    for t in range(1, n):
        jp_persist[t] = 0.90 * jp_persist[t - 1] + jp_innov[t]

    us_cc = g @ vu_true.T + rng.normal(0.0, 0.0065, size=(n, nu))

    # Same-day JP cc shares structure with U.S. cc, plus persistent JP components.
    jp_cc = 0.60 * (g @ vj_true.T) + 0.55 * jp_persist + rng.normal(0.0, 0.0065, size=(n, nj))

    # Next-day JP intraday returns are led by the previous U.S. factor shock.
    jp_oc = np.zeros((n, nj), dtype=float)
    for t in range(1, n):
        jp_oc[t] = (
            0.95 * (g[t - 1] @ vj_true.T)
            + 0.18 * jp_persist[t - 1]
            + rng.normal(0.0, 0.0055, size=nj)
        )

    # U.S. intraday returns are not used by the strategy, but create plausible OHLC data.
    us_oc = 0.65 * us_cc + rng.normal(0.0, 0.0040, size=(n, nu))

    data: dict[str, pd.DataFrame] = {}
    for j, ticker in enumerate(US_TICKERS):
        start_price = 40.0 + 5.0 * j
        data[ticker] = _make_price_frame(
            dates, us_cc[:, j], us_oc[:, j], start_price, rng, ticker
        )
    for j, ticker in enumerate(JP_TICKERS):
        start_price = 900.0 + 120.0 * j
        data[ticker] = _make_price_frame(
            dates, jp_cc[:, j], jp_oc[:, j], start_price, rng, ticker
        )

    # Synthetic factor sets for regression smoke tests.
    ff3 = pd.DataFrame(
        {
            "Mkt-RF": 0.30 * g[:, 0] + rng.normal(0.0, 0.0060, size=n),
            "SMB": rng.normal(0.0, 0.0040, size=n),
            "HML": rng.normal(0.0, 0.0045, size=n),
            "RF": np.full(n, 0.00002),
        },
        index=dates,
    )
    mom_factor = pd.DataFrame(
        {
            "Mom": 0.45 * jp_persist.mean(axis=1) + rng.normal(0.0, 0.0030, size=n),
        },
        index=dates,
    )

    cfg = config
    if alignment_mode is not None:
        cfg = replace(cfg, alignment_mode=alignment_mode)
    return data, ff3, mom_factor, cfg
