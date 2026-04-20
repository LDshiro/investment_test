
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from .config import ReproConfig
from .paper_math import build_prior_target, regularize_corr, standardized_correlation, top_eigenspace
from .panel import common_calendar_for_paper_mode, robust_pair_table, stack_field
from .tickers import US_TICKERS, JP_TICKERS, ALL_TICKERS

StrategyName = Literal["MOM", "PCA_PLAIN", "PCA_SUB", "DOUBLE"]

@dataclass(slots=True)
class PriorPack:
    tickers: list[str]
    c0_corr: np.ndarray

@dataclass(slots=True)
class StrategyOutput:
    name: str
    returns: pd.Series
    signals: pd.DataFrame
    weights: dict[pd.Timestamp, pd.Series]
    meta: pd.DataFrame

@dataclass(slots=True)
class BacktestBundle:
    mom: StrategyOutput
    pca_plain: StrategyOutput
    pca_sub: StrategyOutput
    double: StrategyOutput

def _cc_field(config: ReproConfig) -> str:
    return "ret_cc_adj" if config.use_adjusted_ohlc else "ret_cc_raw"

def _oc_field(config: ReproConfig) -> str:
    return "ret_oc_adj" if config.use_adjusted_ohlc else "ret_oc_raw"

def build_cfull_prior(data: dict[str, pd.DataFrame], config: ReproConfig) -> PriorPack:
    cc_field = _cc_field(config)
    start = pd.Timestamp(config.cfull_start)
    end = pd.Timestamp(config.cfull_end)

    panel = stack_field(data, cc_field, ALL_TICKERS).loc[start:end].copy()

    if config.cfull_method == "proxy_backfill":
        if not config.proxy_map:
            raise ValueError("cfull_method='proxy_backfill' requires config.proxy_map.")
        for target, proxy in config.proxy_map.items():
            if target not in panel.columns:
                continue
            if proxy not in panel.columns:
                if proxy not in data:
                    raise KeyError(f"Proxy ticker {proxy} not present in data.")
                panel[proxy] = stack_field(data, cc_field, [proxy])[proxy]
            panel[target] = panel[target].combine_first(panel[proxy])

    panel = panel.dropna(how="any")
    if panel.empty:
        raise ValueError(
            "C_full sample is empty after missing-value handling. "
            "Use proxy_backfill or adjust cfull window."
        )
    prior_target = build_prior_target(panel)
    return PriorPack(tickers=prior_target.tickers, c0_corr=prior_target.c0_corr)

def _subset_c0(prior_pack: PriorPack, subset_tickers: list[str]) -> np.ndarray:
    pos = {t: i for i, t in enumerate(prior_pack.tickers)}
    idx = [pos[t] for t in subset_tickers]
    return prior_pack.c0_corr[np.ix_(idx, idx)]

def _quantile_portfolio(signal: pd.Series, q: float) -> pd.Series:
    x = signal.dropna().sort_values()
    n = len(x)
    if n == 0:
        return pd.Series(dtype=float)
    k = max(1, int(np.floor(q * n)))
    short_names = x.index[:k]
    long_names = x.index[-k:]
    w = pd.Series(0.0, index=x.index)
    w.loc[long_names] = 1.0 / len(long_names)
    w.loc[short_names] = -1.0 / len(short_names)
    return w

def _binary_split(signal: pd.Series) -> tuple[set[str], set[str]]:
    x = signal.dropna().sort_values()
    n = len(x)
    if n == 0:
        return set(), set()
    half = n // 2
    low = set(x.index[:half])
    high = set(x.index[-half:])
    if n % 2 == 1 and half == 0:
        high = set(x.index)
    return high, low

def _double_sort_weights(mom_signal: pd.Series, pca_signal: pd.Series) -> pd.Series:
    common = mom_signal.dropna().index.intersection(pca_signal.dropna().index)
    if len(common) == 0:
        return pd.Series(dtype=float)
    mom_signal = mom_signal.loc[common]
    pca_signal = pca_signal.loc[common]
    mom_high, mom_low = _binary_split(mom_signal)
    pca_high, pca_low = _binary_split(pca_signal)
    long_names = sorted(mom_high.intersection(pca_high))
    short_names = sorted(mom_low.intersection(pca_low))
    all_names = sorted(set(common))
    w = pd.Series(0.0, index=all_names)
    if len(long_names) > 0:
        w.loc[long_names] = 1.0 / len(long_names)
    if len(short_names) > 0:
        w.loc[short_names] = -1.0 / len(short_names)
    return w

def _standardize_current(window_df: pd.DataFrame, current: pd.Series) -> pd.Series:
    mu = window_df.mean(axis=0)
    sigma = window_df.std(axis=0, ddof=0)
    sigma = sigma.replace(0.0, np.nan)
    z = (current - mu) / sigma
    return z

def _prepare_panels(data: dict[str, pd.DataFrame], config: ReproConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    cc = stack_field(data, _cc_field(config), ALL_TICKERS).sort_index()
    oc = stack_field(data, _oc_field(config), JP_TICKERS).sort_index()
    return cc, oc

def _paper_eval_dates(data: dict[str, pd.DataFrame], config: ReproConfig) -> pd.DatetimeIndex:
    return common_calendar_for_paper_mode(
        data,
        field=_cc_field(config),
        start=config.eval_start,
        end=config.eval_end,
        dynamic_assets=True,
    )

def _robust_pairs(data: dict[str, pd.DataFrame], config: ReproConfig) -> pd.DataFrame:
    return robust_pair_table(
        data,
        field=_cc_field(config),
        start=config.eval_start,
        end=config.eval_end,
    )

def _loop_steps_paper(cc: pd.DataFrame, oc: pd.DataFrame, config: ReproConfig):
    dates = cc.index.intersection(_paper_eval_dates_from_cc(cc, config))
    # Keep only dates with any U.S. and any Japan return.
    for idx in range(config.lookback, len(dates) - 1):
        us_date = dates[idx]
        trade_date = dates[idx + 1]
        window_dates = dates[idx - config.lookback:idx]
        yield us_date, trade_date, window_dates

def _paper_eval_dates_from_cc(cc: pd.DataFrame, config: ReproConfig) -> pd.DatetimeIndex:
    cc = cc.loc[pd.Timestamp(config.eval_start):pd.Timestamp(config.eval_end)]
    us_any = cc[US_TICKERS].notna().any(axis=1)
    jp_any = cc[JP_TICKERS].notna().any(axis=1)
    return cc.index[us_any & jp_any]

def _loop_steps_robust(cc: pd.DataFrame, config: ReproConfig):
    pairs = _robust_pairs_from_cc(cc, config)
    us_dates = pd.DatetimeIndex(pairs["us_date"])
    trade_dates = pd.DatetimeIndex(pairs["jp_next_date"])
    for idx in range(config.lookback, len(us_dates)):
        window_us = us_dates[idx - config.lookback:idx]
        window_jp = trade_dates[idx - config.lookback:idx]
        yield us_dates[idx], trade_dates[idx], window_us, window_jp

def _robust_pairs_from_cc(cc: pd.DataFrame, config: ReproConfig) -> pd.DataFrame:
    cc = cc.loc[pd.Timestamp(config.eval_start):pd.Timestamp(config.eval_end)]
    us_dates = cc.index[cc[US_TICKERS].notna().any(axis=1)]
    jp_dates = cc.index[cc[JP_TICKERS].notna().any(axis=1)]
    jp_arr = np.array(jp_dates)
    pos = np.searchsorted(jp_arr, np.array(us_dates), side="right")
    mapped = []
    for i, p in enumerate(pos):
        if p < len(jp_arr):
            mapped.append((us_dates[i], pd.Timestamp(jp_arr[p])))
    return pd.DataFrame(mapped, columns=["us_date", "jp_next_date"])

def _available_assets_for_paper(
    cc: pd.DataFrame,
    oc: pd.DataFrame,
    us_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    window_dates: pd.DatetimeIndex,
) -> tuple[list[str], list[str]]:
    us_avail = []
    jp_avail = []
    for t in US_TICKERS:
        vals = cc.loc[window_dates, t]
        if vals.notna().all() and pd.notna(cc.at[us_date, t]):
            us_avail.append(t)
    for t in JP_TICKERS:
        vals = cc.loc[window_dates, t]
        if vals.notna().all() and trade_date in oc.index and pd.notna(oc.at[trade_date, t]):
            jp_avail.append(t)
    return us_avail, jp_avail

def _available_assets_for_robust(
    cc: pd.DataFrame,
    oc: pd.DataFrame,
    us_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    window_us: pd.DatetimeIndex,
    window_jp: pd.DatetimeIndex,
) -> tuple[list[str], list[str]]:
    us_avail = []
    jp_avail = []
    for t in US_TICKERS:
        vals = cc.loc[window_us, t]
        if vals.notna().all() and pd.notna(cc.at[us_date, t]):
            us_avail.append(t)
    for t in JP_TICKERS:
        vals = cc.loc[window_jp, t]
        if vals.notna().all() and trade_date in oc.index and pd.notna(oc.at[trade_date, t]):
            jp_avail.append(t)
    return us_avail, jp_avail

def _pca_signal_paper_for_date(
    cc: pd.DataFrame,
    oc: pd.DataFrame,
    prior: PriorPack,
    config: ReproConfig,
    us_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    window_dates: pd.DatetimeIndex,
    regularized: bool,
) -> tuple[pd.Series, pd.Series, dict[str, int | str]]:
    us_avail, jp_avail = _available_assets_for_paper(cc, oc, us_date, trade_date, window_dates)
    if config.require_strict_complete_cases and (len(us_avail) < len(US_TICKERS) or len(jp_avail) < len(JP_TICKERS)):
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_strict"}
    if len(us_avail) == 0 or len(jp_avail) == 0:
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_empty"}

    subset = us_avail + jp_avail
    window_mat = cc.loc[window_dates, subset]
    ct = standardized_correlation(window_mat)
    c_reg = ct
    if regularized:
        c0_sub = _subset_c0(prior, subset)
        c_reg = regularize_corr(ct, c0_sub, config.lambda_reg)

    _, vecs = top_eigenspace(c_reg, config.n_components)
    n_us = len(us_avail)
    vu = vecs[:n_us, :]
    vj = vecs[n_us:, :]

    z_u = _standardize_current(window_mat[us_avail], cc.loc[us_date, us_avail]).dropna()
    if len(z_u) != n_us:
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_zu"}

    f_t = vu.T @ z_u.to_numpy(dtype=float)
    sig = pd.Series(vj @ f_t, index=jp_avail, dtype=float)
    w = _quantile_portfolio(sig, config.q)
    meta = {"status": "ok", "n_us": n_us, "n_jp": len(jp_avail)}
    return sig, w, meta

def _pca_signal_robust_for_date(
    cc: pd.DataFrame,
    oc: pd.DataFrame,
    prior: PriorPack,
    config: ReproConfig,
    us_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    window_us: pd.DatetimeIndex,
    window_jp: pd.DatetimeIndex,
    regularized: bool,
) -> tuple[pd.Series, pd.Series, dict[str, int | str]]:
    us_avail, jp_avail = _available_assets_for_robust(cc, oc, us_date, trade_date, window_us, window_jp)
    if config.require_strict_complete_cases and (len(us_avail) < len(US_TICKERS) or len(jp_avail) < len(JP_TICKERS)):
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_strict"}
    if len(us_avail) == 0 or len(jp_avail) == 0:
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_empty"}

    subset = us_avail + jp_avail
    window_mat = pd.concat(
        [cc.loc[window_us, us_avail].reset_index(drop=True), cc.loc[window_jp, jp_avail].reset_index(drop=True)],
        axis=1,
    )
    window_mat.columns = subset
    ct = standardized_correlation(window_mat)
    c_reg = ct
    if regularized:
        c0_sub = _subset_c0(prior, subset)
        c_reg = regularize_corr(ct, c0_sub, config.lambda_reg)

    _, vecs = top_eigenspace(c_reg, config.n_components)
    n_us = len(us_avail)
    vu = vecs[:n_us, :]
    vj = vecs[n_us:, :]

    z_u = _standardize_current(cc.loc[window_us, us_avail], cc.loc[us_date, us_avail]).dropna()
    if len(z_u) != n_us:
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_zu"}

    f_t = vu.T @ z_u.to_numpy(dtype=float)
    sig = pd.Series(vj @ f_t, index=jp_avail, dtype=float)
    w = _quantile_portfolio(sig, config.q)
    meta = {"status": "ok", "n_us": n_us, "n_jp": len(jp_avail)}
    return sig, w, meta

def _mom_signal_paper_for_date(
    cc: pd.DataFrame,
    oc: pd.DataFrame,
    config: ReproConfig,
    us_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    window_dates: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series, dict[str, int | str]]:
    jp_avail = []
    for t in JP_TICKERS:
        vals = cc.loc[window_dates, t]
        if vals.notna().all() and trade_date in oc.index and pd.notna(oc.at[trade_date, t]):
            jp_avail.append(t)
    if config.require_strict_complete_cases and len(jp_avail) < len(JP_TICKERS):
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_strict"}
    if len(jp_avail) == 0:
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_empty"}

    sig = cc.loc[window_dates, jp_avail].mean(axis=0)
    w = _quantile_portfolio(sig, config.q)
    return sig.astype(float), w, {"status": "ok", "n_jp": len(jp_avail)}

def _mom_signal_robust_for_date(
    cc: pd.DataFrame,
    oc: pd.DataFrame,
    config: ReproConfig,
    us_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    window_jp: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series, dict[str, int | str]]:
    jp_avail = []
    for t in JP_TICKERS:
        vals = cc.loc[window_jp, t]
        if vals.notna().all() and trade_date in oc.index and pd.notna(oc.at[trade_date, t]):
            jp_avail.append(t)
    if config.require_strict_complete_cases and len(jp_avail) < len(JP_TICKERS):
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_strict"}
    if len(jp_avail) == 0:
        return pd.Series(dtype=float), pd.Series(dtype=float), {"status": "skip_empty"}

    sig = cc.loc[window_jp, jp_avail].mean(axis=0)
    w = _quantile_portfolio(sig, config.q)
    return sig.astype(float), w, {"status": "ok", "n_jp": len(jp_avail)}

def _realized_return(weights: pd.Series, realized_oc: pd.Series) -> float:
    if weights.empty:
        return np.nan
    common = weights.index.intersection(realized_oc.dropna().index)
    if len(common) == 0:
        return np.nan
    return float((weights.loc[common] * realized_oc.loc[common]).sum())

def run_backtests(data: dict[str, pd.DataFrame], config: ReproConfig) -> BacktestBundle:
    cc, oc = _prepare_panels(data, config)
    prior = build_cfull_prior(data, config)

    mom_ret: dict[pd.Timestamp, float] = {}
    plain_ret: dict[pd.Timestamp, float] = {}
    sub_ret: dict[pd.Timestamp, float] = {}
    mom_sig_rows: dict[pd.Timestamp, pd.Series] = {}
    plain_sig_rows: dict[pd.Timestamp, pd.Series] = {}
    sub_sig_rows: dict[pd.Timestamp, pd.Series] = {}
    mom_w: dict[pd.Timestamp, pd.Series] = {}
    plain_w: dict[pd.Timestamp, pd.Series] = {}
    sub_w: dict[pd.Timestamp, pd.Series] = {}
    meta_rows: list[dict[str, object]] = []

    if config.alignment_mode == "paper":
        for us_date, trade_date, window_dates in _loop_steps_paper(cc, oc, config):
            realized = oc.loc[trade_date] if trade_date in oc.index else pd.Series(dtype=float)

            mom_sig, mw, mmeta = _mom_signal_paper_for_date(cc, oc, config, us_date, trade_date, window_dates)
            p_sig, pw, pmeta = _pca_signal_paper_for_date(cc, oc, prior, config, us_date, trade_date, window_dates, False)
            s_sig, sw, smeta = _pca_signal_paper_for_date(cc, oc, prior, config, us_date, trade_date, window_dates, True)

            if not mom_sig.empty:
                mom_sig_rows[trade_date] = mom_sig
                mom_w[trade_date] = mw
                mom_ret[trade_date] = _realized_return(mw, realized)
            if not p_sig.empty:
                plain_sig_rows[trade_date] = p_sig
                plain_w[trade_date] = pw
                plain_ret[trade_date] = _realized_return(pw, realized)
            if not s_sig.empty:
                sub_sig_rows[trade_date] = s_sig
                sub_w[trade_date] = sw
                sub_ret[trade_date] = _realized_return(sw, realized)

            meta_rows.append(
                {
                    "trade_date": trade_date,
                    "us_date": us_date,
                    "mode": "paper",
                    "mom_status": mmeta.get("status", ""),
                    "plain_status": pmeta.get("status", ""),
                    "sub_status": smeta.get("status", ""),
                    "plain_n_us": pmeta.get("n_us", np.nan),
                    "sub_n_us": smeta.get("n_us", np.nan),
                    "plain_n_jp": pmeta.get("n_jp", np.nan),
                    "sub_n_jp": smeta.get("n_jp", np.nan),
                }
            )
    elif config.alignment_mode == "robust":
        for us_date, trade_date, window_us, window_jp in _loop_steps_robust(cc, config):
            realized = oc.loc[trade_date] if trade_date in oc.index else pd.Series(dtype=float)

            mom_sig, mw, mmeta = _mom_signal_robust_for_date(cc, oc, config, us_date, trade_date, window_jp)
            p_sig, pw, pmeta = _pca_signal_robust_for_date(
                cc, oc, prior, config, us_date, trade_date, window_us, window_jp, False
            )
            s_sig, sw, smeta = _pca_signal_robust_for_date(
                cc, oc, prior, config, us_date, trade_date, window_us, window_jp, True
            )

            if not mom_sig.empty:
                mom_sig_rows[trade_date] = mom_sig
                mom_w[trade_date] = mw
                mom_ret[trade_date] = _realized_return(mw, realized)
            if not p_sig.empty:
                plain_sig_rows[trade_date] = p_sig
                plain_w[trade_date] = pw
                plain_ret[trade_date] = _realized_return(pw, realized)
            if not s_sig.empty:
                sub_sig_rows[trade_date] = s_sig
                sub_w[trade_date] = sw
                sub_ret[trade_date] = _realized_return(sw, realized)

            meta_rows.append(
                {
                    "trade_date": trade_date,
                    "us_date": us_date,
                    "mode": "robust",
                    "mom_status": mmeta.get("status", ""),
                    "plain_status": pmeta.get("status", ""),
                    "sub_status": smeta.get("status", ""),
                    "plain_n_us": pmeta.get("n_us", np.nan),
                    "sub_n_us": smeta.get("n_us", np.nan),
                    "plain_n_jp": pmeta.get("n_jp", np.nan),
                    "sub_n_jp": smeta.get("n_jp", np.nan),
                }
            )
    else:
        raise ValueError(f"Unknown alignment_mode: {config.alignment_mode}")

    def _sig_df(rows: dict[pd.Timestamp, pd.Series]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame(columns=JP_TICKERS)
        return pd.DataFrame(rows).T.reindex(columns=JP_TICKERS).sort_index()

    mom_out = StrategyOutput("MOM", pd.Series(mom_ret).sort_index(), _sig_df(mom_sig_rows), mom_w, pd.DataFrame(meta_rows))
    plain_out = StrategyOutput("PCA_PLAIN", pd.Series(plain_ret).sort_index(), _sig_df(plain_sig_rows), plain_w, pd.DataFrame(meta_rows))
    sub_out = StrategyOutput("PCA_SUB", pd.Series(sub_ret).sort_index(), _sig_df(sub_sig_rows), sub_w, pd.DataFrame(meta_rows))

    # DOUBLE is constructed ex post from MOM + PCA_SUB signals on each trade_date.
    double_ret: dict[pd.Timestamp, float] = {}
    double_sig_rows: dict[pd.Timestamp, pd.Series] = {}
    double_w: dict[pd.Timestamp, pd.Series] = {}
    for dt in sorted(set(mom_out.signals.index).intersection(sub_out.signals.index)):
        ms = mom_out.signals.loc[dt].dropna()
        ss = sub_out.signals.loc[dt].dropna()
        w = _double_sort_weights(ms, ss)
        if w.empty or dt not in oc.index:
            continue
        realized = oc.loc[dt]
        double_ret[dt] = _realized_return(w, realized)
        double_w[dt] = w
        # Store average rank-style composite signal for audit only.
        comp = pd.concat([ms.rename("mom"), ss.rename("pca")], axis=1).mean(axis=1)
        double_sig_rows[dt] = comp

    double_out = StrategyOutput("DOUBLE", pd.Series(double_ret).sort_index(), _sig_df(double_sig_rows), double_w, pd.DataFrame(meta_rows))
    return BacktestBundle(mom_out, plain_out, sub_out, double_out)
