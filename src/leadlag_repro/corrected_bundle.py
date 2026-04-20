from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import ReproConfig
from .metrics import compare_with_table2_targets, cumulative_returns, summarize_bundle
from .paper_math import build_prior_basis, standardized_correlation
from .regression import carhart4_regression, ff3_regression, result_to_row
from .strategy import BacktestBundle, PriorPack, StrategyOutput
from .tickers import ALL_TICKERS, JP_TICKERS, TABLE1_TARGET_COUNTS, US_TICKERS


@dataclass(slots=True)
class SampleFilterResult:
    start: pd.Timestamp
    end: pd.Timestamp
    dates: pd.DatetimeIndex
    exact_match: bool
    score: int
    table1_counts: pd.DataFrame


def _ensure_index(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()


def load_corrected_bundle(bundle_root: Path | str) -> dict[str, Any]:
    bundle_root = Path(bundle_root)
    cc = _ensure_index(bundle_root / "returns_cc.csv").reindex(columns=ALL_TICKERS)
    oc_jp = _ensure_index(bundle_root / "returns_oc_jp.csv").reindex(columns=JP_TICKERS)
    open_adj = _ensure_index(bundle_root / "open_prices_adj.csv").reindex(columns=ALL_TICKERS)
    close_adj = _ensure_index(bundle_root / "close_prices_adj.csv").reindex(columns=ALL_TICKERS)
    core_dates = pd.DatetimeIndex(pd.read_csv(bundle_root / "common_dates_core.csv", parse_dates=["date"])["date"])
    full_dates = pd.DatetimeIndex(pd.read_csv(bundle_root / "common_dates_full.csv", parse_dates=["date"])["date"])

    ff3 = pd.read_csv(bundle_root / "ff3_japan_daily.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    mom = pd.read_csv(bundle_root / "mom_japan_daily.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    if "WML" in mom.columns:
        mom = mom.rename(columns={"WML": "Mom"})
    carhart4 = pd.read_csv(bundle_root / "carhart4_japan_daily.csv", parse_dates=["Date"]).set_index("Date").sort_index()

    data: dict[str, pd.DataFrame] = {}
    for ticker in ALL_TICKERS:
        df = pd.DataFrame(index=cc.index)
        df["ret_cc_adj"] = cc[ticker]
        df["ret_cc_raw"] = cc[ticker]
        if ticker in JP_TICKERS:
            df["ret_oc_adj"] = oc_jp[ticker]
            df["ret_oc_raw"] = oc_jp[ticker]
        else:
            df["ret_oc_adj"] = np.nan
            df["ret_oc_raw"] = np.nan
        df["adj_open"] = open_adj[ticker]
        df["adj_close"] = close_adj[ticker]
        data[ticker] = df

    return {
        "data": data,
        "cc": cc,
        "oc_jp": oc_jp,
        "open_adj": open_adj,
        "close_adj": close_adj,
        "core_dates": core_dates,
        "full_dates": full_dates,
        "ff3": ff3,
        "mom": mom[["Mom"]],
        "carhart4": carhart4,
    }


def table1_counts_report(counts: pd.Series) -> pd.DataFrame:
    target = pd.Series(TABLE1_TARGET_COUNTS, name="target")
    actual = counts.rename("actual")
    out = pd.concat([actual, target], axis=1)
    out["gap"] = out["actual"] - out["target"]
    out.index.name = "Ticker"
    return out.reset_index()


def find_table1_sample_filter(cc: pd.DataFrame, common_dates_core: pd.DatetimeIndex) -> SampleFilterResult:
    majority_count = max(TABLE1_TARGET_COUNTS.values())
    best_score: int | None = None
    best_dates: pd.DatetimeIndex | None = None
    best_counts: pd.Series | None = None
    exact = False

    for start_idx in range(0, len(common_dates_core) - majority_count + 1):
        dates = common_dates_core[start_idx:start_idx + majority_count]
        counts = cc.loc[dates].notna().sum(axis=0)
        score = int(sum(abs(int(counts.get(t, 0)) - int(TABLE1_TARGET_COUNTS[t])) for t in TABLE1_TARGET_COUNTS))
        if best_score is None or score < best_score:
            best_score = score
            best_dates = dates
            best_counts = counts
        if score == 0:
            exact = True
            best_score = 0
            best_dates = dates
            best_counts = counts
            break

    if best_dates is None or best_counts is None or best_score is None:
        raise RuntimeError("Failed to infer Table 1 sample filter.")

    return SampleFilterResult(
        start=pd.Timestamp(best_dates[0]),
        end=pd.Timestamp(best_dates[-1]),
        dates=pd.DatetimeIndex(best_dates),
        exact_match=exact,
        score=best_score,
        table1_counts=table1_counts_report(best_counts),
    )


def basic_stats_in_dates(panel: pd.DataFrame, dates: pd.DatetimeIndex, annualization_base: int = 252) -> pd.DataFrame:
    rows = []
    x = panel.loc[dates]
    for ticker in x.columns:
        s = x[ticker].dropna()
        vol = float(s.std(ddof=1))
        rows.append(
            {
                "Ticker": ticker,
                "Ret (%)": float(s.mean() * annualization_base * 100.0),
                "Vol (%)": float(vol * np.sqrt(annualization_base) * 100.0),
                "Ret/Vol": float((s.mean() * annualization_base) / (vol * np.sqrt(annualization_base))) if vol > 0 else np.nan,
                "Skew": float(s.skew()),
                "Kurtosis": float(s.kurt() + 3.0),
                "N": int(s.shape[0]),
            }
        )
    return pd.DataFrame(rows).sort_values("Ticker").reset_index(drop=True)


def build_prior_expand26to28(cc: pd.DataFrame, common_dates_core: pd.DatetimeIndex, pre_start: str, pre_end: str) -> PriorPack:
    dates = common_dates_core[(common_dates_core >= pd.Timestamp(pre_start)) & (common_dates_core <= pd.Timestamp(pre_end))]
    panel = cc.loc[dates, ALL_TICKERS]
    complete_cols = list(panel.columns[panel.notna().all()])
    if len(complete_cols) < 3:
        raise ValueError("Not enough complete assets in pre-sample to estimate prior.")

    v0_subset = build_prior_basis(complete_cols)
    cfull_subset = standardized_correlation(panel[complete_cols])
    d0 = np.diag(v0_subset.T @ cfull_subset @ v0_subset)

    v0_all = build_prior_basis(ALL_TICKERS)
    c0_raw = v0_all @ np.diag(d0) @ v0_all.T
    delta = np.diag(c0_raw).copy()
    if np.any(delta <= 0):
        raise ValueError("Prior construction produced non-positive diagonal elements.")
    scale = np.diag(1.0 / np.sqrt(delta))
    c0_corr = scale @ c0_raw @ scale
    c0_corr = 0.5 * (c0_corr + c0_corr.T)
    np.fill_diagonal(c0_corr, 1.0)
    return PriorPack(tickers=list(ALL_TICKERS), c0_corr=c0_corr)


def _quantile_weights(signal: np.ndarray, q: float) -> np.ndarray:
    n = signal.shape[0]
    k = max(1, int(np.floor(q * n)))
    order = np.argsort(signal)
    w = np.zeros(n, dtype=float)
    short_idx = order[:k]
    long_idx = order[-k:]
    w[long_idx] = 1.0 / len(long_idx)
    w[short_idx] = -1.0 / len(short_idx)
    return w


def _binary_sets(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(signal)
    n = signal.shape[0]
    half = n // 2
    low = order[:half]
    high = order[-half:]
    if n % 2 == 1 and half == 0:
        high = order
    return high, low


def _top_eigenspace(corr: np.ndarray, k: int) -> np.ndarray:
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1]
    return vecs[:, order[:k]]


def _standardized_corr(window_mat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = window_mat.mean(axis=0)
    sigma = window_mat.std(axis=0, ddof=0)
    sigma = np.where(sigma == 0.0, np.nan, sigma)
    z = (window_mat - mu) / sigma
    corr = (z.T @ z) / window_mat.shape[0]
    corr = 0.5 * (corr + corr.T)
    np.fill_diagonal(corr, 1.0)
    return corr, mu, sigma


def _subset_c0(prior: PriorPack, idx: np.ndarray) -> np.ndarray:
    return prior.c0_corr[np.ix_(idx, idx)]


def run_backtests_fast(
    cc: pd.DataFrame,
    oc_jp: pd.DataFrame,
    sample_dates: pd.DatetimeIndex,
    prior: PriorPack,
    cfg: ReproConfig,
) -> BacktestBundle:
    cc_sample = cc.loc[sample_dates, ALL_TICKERS].to_numpy(dtype=float)
    oc_sample = oc_jp.loc[sample_dates, JP_TICKERS].to_numpy(dtype=float)
    n_dates = len(sample_dates)
    n_us = len(US_TICKERS)
    n_jp = len(JP_TICKERS)
    lookback = cfg.lookback
    q = cfg.q
    k = cfg.n_components

    # Availability masks on the sample date grid.
    notna_cc = ~np.isnan(cc_sample)
    us_notna = notna_cc[:, :n_us]
    jp_notna = notna_cc[:, n_us:]
    oc_notna = ~np.isnan(oc_sample)

    us_roll = np.zeros_like(us_notna, dtype=np.int32)
    jp_roll = np.zeros_like(jp_notna, dtype=np.int32)
    if lookback > 0:
        us_cum = np.vstack([np.zeros((1, n_us), dtype=np.int32), np.cumsum(us_notna.astype(np.int32), axis=0)])
        jp_cum = np.vstack([np.zeros((1, n_jp), dtype=np.int32), np.cumsum(jp_notna.astype(np.int32), axis=0)])
        for i in range(lookback, n_dates):
            us_roll[i] = us_cum[i] - us_cum[i - lookback]
            jp_roll[i] = jp_cum[i] - jp_cum[i - lookback]

    mom_returns: list[float] = []
    plain_returns: list[float] = []
    sub_returns: list[float] = []
    trade_dates: list[pd.Timestamp] = []
    mom_signals: list[np.ndarray] = []
    plain_signals: list[np.ndarray] = []
    sub_signals: list[np.ndarray] = []
    mom_weights: dict[pd.Timestamp, pd.Series] = {}
    plain_weights: dict[pd.Timestamp, pd.Series] = {}
    sub_weights: dict[pd.Timestamp, pd.Series] = {}
    meta_rows: list[dict[str, Any]] = []

    us_subset_cache: dict[tuple[int, ...], tuple[np.ndarray, np.ndarray]] = {}

    for i in range(lookback, n_dates - 1):
        trade_date = sample_dates[i + 1]
        us_date = sample_dates[i]
        trade_dates.append(trade_date)

        us_avail = (us_roll[i] == lookback) & us_notna[i]
        jp_avail = (jp_roll[i] == lookback) & oc_notna[i + 1]
        us_idx = np.flatnonzero(us_avail)
        jp_idx_local = np.flatnonzero(jp_avail)

        # MOM on available JP assets.
        mom_sig_vec = np.full(n_jp, np.nan, dtype=float)
        if jp_idx_local.size > 0:
            window_jp = cc_sample[i - lookback:i, n_us + jp_idx_local]
            sig = window_jp.mean(axis=0)
            mom_sig_vec[jp_idx_local] = sig
            w_local = _quantile_weights(sig, q)
            realized = oc_sample[i + 1, jp_idx_local]
            mom_returns.append(float(np.dot(w_local, realized)))
            mom_weights[trade_date] = pd.Series(w_local, index=[JP_TICKERS[j] for j in jp_idx_local])
        else:
            mom_returns.append(np.nan)
        mom_signals.append(mom_sig_vec)

        # PCA signals if there are enough assets.
        plain_sig_vec = np.full(n_jp, np.nan, dtype=float)
        sub_sig_vec = np.full(n_jp, np.nan, dtype=float)
        plain_ret = np.nan
        sub_ret = np.nan
        plain_w_series = pd.Series(dtype=float)
        sub_w_series = pd.Series(dtype=float)

        if us_idx.size >= 1 and jp_idx_local.size >= 1:
            subset_idx = np.concatenate([us_idx, n_us + jp_idx_local])
            window_mat = cc_sample[i - lookback:i][:, subset_idx]
            ct, mu, sigma = _standardized_corr(window_mat)
            current_u = cc_sample[i, us_idx]
            z_u = (current_u - mu[:us_idx.size]) / sigma[:us_idx.size]

            if np.all(np.isfinite(z_u)):
                # Plain PCA
                vecs_plain = _top_eigenspace(ct, k)
                vu_plain = vecs_plain[:us_idx.size, :]
                vj_plain = vecs_plain[us_idx.size:, :]
                f_plain = vu_plain.T @ z_u
                sig_plain = vj_plain @ f_plain
                plain_sig_vec[jp_idx_local] = sig_plain
                w_plain = _quantile_weights(sig_plain, q)
                plain_ret = float(np.dot(w_plain, oc_sample[i + 1, jp_idx_local]))
                plain_w_series = pd.Series(w_plain, index=[JP_TICKERS[j] for j in jp_idx_local])

                # Regularized PCA
                key = tuple(int(x) for x in subset_idx)
                if key in us_subset_cache:
                    c0_sub, _ = us_subset_cache[key]
                else:
                    c0_sub = _subset_c0(prior, subset_idx)
                    us_subset_cache[key] = (c0_sub, np.array(key, dtype=int))
                c_reg = (1.0 - cfg.lambda_reg) * ct + cfg.lambda_reg * c0_sub
                c_reg = 0.5 * (c_reg + c_reg.T)
                np.fill_diagonal(c_reg, 1.0)
                vecs_sub = _top_eigenspace(c_reg, k)
                vu_sub = vecs_sub[:us_idx.size, :]
                vj_sub = vecs_sub[us_idx.size:, :]
                f_sub = vu_sub.T @ z_u
                sig_sub = vj_sub @ f_sub
                sub_sig_vec[jp_idx_local] = sig_sub
                w_sub = _quantile_weights(sig_sub, q)
                sub_ret = float(np.dot(w_sub, oc_sample[i + 1, jp_idx_local]))
                sub_w_series = pd.Series(w_sub, index=[JP_TICKERS[j] for j in jp_idx_local])

        plain_returns.append(plain_ret)
        sub_returns.append(sub_ret)
        plain_signals.append(plain_sig_vec)
        sub_signals.append(sub_sig_vec)
        if not plain_w_series.empty:
            plain_weights[trade_date] = plain_w_series
        if not sub_w_series.empty:
            sub_weights[trade_date] = sub_w_series
        meta_rows.append({
            "trade_date": trade_date,
            "us_date": us_date,
            "n_us": int(us_idx.size),
            "n_jp": int(jp_idx_local.size),
            "has_xlre": bool(1 in us_idx) or bool(np.any(us_idx == US_TICKERS.index("XLRE"))) if hasattr(US_TICKERS, 'index') else False,
        })

    trade_index = pd.DatetimeIndex(trade_dates)
    mom_returns_s = pd.Series(mom_returns, index=trade_index, name="MOM")
    plain_returns_s = pd.Series(plain_returns, index=trade_index, name="PCA_PLAIN")
    sub_returns_s = pd.Series(sub_returns, index=trade_index, name="PCA_SUB")
    mom_signal_df = pd.DataFrame(mom_signals, index=trade_index, columns=JP_TICKERS)
    plain_signal_df = pd.DataFrame(plain_signals, index=trade_index, columns=JP_TICKERS)
    sub_signal_df = pd.DataFrame(sub_signals, index=trade_index, columns=JP_TICKERS)
    meta_df = pd.DataFrame(meta_rows)

    # DOUBLE from MOM and PCA_SUB signals.
    double_returns: list[float] = []
    double_signals: list[np.ndarray] = []
    double_weights: dict[pd.Timestamp, pd.Series] = {}
    for dt, ms, ss in zip(trade_index, mom_signal_df.to_numpy(dtype=float), sub_signal_df.to_numpy(dtype=float)):
        valid = np.isfinite(ms) & np.isfinite(ss)
        comp = np.full(n_jp, np.nan, dtype=float)
        if valid.sum() == 0:
            double_returns.append(np.nan)
            double_signals.append(comp)
            continue
        m = ms[valid]
        s = ss[valid]
        high_m, low_m = _binary_sets(m)
        high_s, low_s = _binary_sets(s)
        long_local = np.intersect1d(high_m, high_s)
        short_local = np.intersect1d(low_m, low_s)
        w = np.zeros(valid.sum(), dtype=float)
        if long_local.size > 0:
            w[long_local] = 1.0 / long_local.size
        if short_local.size > 0:
            w[short_local] = -1.0 / short_local.size
        realized = oc_jp.loc[dt, JP_TICKERS].to_numpy(dtype=float)[valid]
        double_returns.append(float(np.dot(w, realized)))
        comp[valid] = 0.5 * (m + s)
        double_signals.append(comp)
        double_weights[dt] = pd.Series(w, index=[JP_TICKERS[j] for j in np.flatnonzero(valid)])

    double_returns_s = pd.Series(double_returns, index=trade_index, name="DOUBLE")
    double_signal_df = pd.DataFrame(double_signals, index=trade_index, columns=JP_TICKERS)

    mom_out = StrategyOutput("MOM", mom_returns_s, mom_signal_df, mom_weights, meta_df)
    plain_out = StrategyOutput("PCA_PLAIN", plain_returns_s, plain_signal_df, plain_weights, meta_df)
    sub_out = StrategyOutput("PCA_SUB", sub_returns_s, sub_signal_df, sub_weights, meta_df)
    double_out = StrategyOutput("DOUBLE", double_returns_s, double_signal_df, double_weights, meta_df)
    return BacktestBundle(mom_out, plain_out, sub_out, double_out)


def _regression_tables(bundle: BacktestBundle, ff3: pd.DataFrame, mom: pd.DataFrame, cfg: ReproConfig, out_dir: Path) -> None:
    outputs = {
        "MOM": bundle.mom.returns,
        "PCA_PLAIN": bundle.pca_plain.returns,
        "PCA_SUB": bundle.pca_sub.returns,
        "DOUBLE": bundle.double.returns,
    }
    for lag in cfg.nw_lag_grid:
        ff_rows = []
        car_rows = []
        for name, ret in outputs.items():
            ff_rows.append(result_to_row(name, ff3_regression(ret, ff3, annualization_base=cfg.annualization_base_main, nw_lag=lag)))
            car_rows.append(result_to_row(name, carhart4_regression(ret, ff3, mom, annualization_base=cfg.annualization_base_main, nw_lag=lag)))
        pd.DataFrame(ff_rows).to_csv(out_dir / f"table3_ff3_nw{lag}.csv", index=False)
        pd.DataFrame(car_rows).to_csv(out_dir / f"table4_carhart4_nw{lag}.csv", index=False)


def _plot_cumulative(bundle: BacktestBundle, out_path: Path) -> pd.DataFrame:
    wealth = pd.concat(
        {
            "MOM": cumulative_returns(bundle.mom.returns),
            "PCA_PLAIN": cumulative_returns(bundle.pca_plain.returns),
            "PCA_SUB": cumulative_returns(bundle.pca_sub.returns),
            "DOUBLE": cumulative_returns(bundle.double.returns),
        },
        axis=1,
    )
    wealth.to_csv(out_path.with_suffix('.csv'))
    plt.figure(figsize=(9, 5))
    for col in wealth.columns:
        plt.plot(wealth.index, wealth[col], label=col)
    plt.legend()
    plt.xlabel('Date')
    plt.ylabel('Cumulative wealth')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return wealth


def run_corrected_bundle_reproduction(bundle_root: Path | str, output_root: Path | str) -> dict[str, Any]:
    bundle_root = Path(bundle_root)
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    loaded = load_corrected_bundle(bundle_root)
    sample = find_table1_sample_filter(loaded["cc"], loaded["core_dates"])
    sample.table1_counts.to_csv(out_dir / "table1_counts_exact_filter.csv", index=False)
    table1_stats = basic_stats_in_dates(loaded["cc"], sample.dates, annualization_base=252)
    table1_stats.to_csv(out_dir / "table1_stats_exact_filter.csv", index=False)

    prior = build_prior_expand26to28(loaded["cc"], loaded["core_dates"], pre_start="2010-01-01", pre_end="2014-12-31")
    cfg = ReproConfig(
        data_root=bundle_root,
        factor_root=bundle_root,
        output_root=out_dir,
        eval_start=str(sample.start.date()),
        eval_end=str(sample.end.date()),
        alignment_mode="paper",
        require_strict_complete_cases=False,
        cfull_method="post_inception_only",
    )
    backtests = run_backtests_fast(loaded["cc"], loaded["oc_jp"], sample.dates, prior, cfg)

    table2_main = summarize_bundle(backtests, cfg, annualization_mode="main", mdd_mode=cfg.mdd_mode_main)
    table2_main.to_csv(out_dir / "table2_main.csv", index=False)
    table2_paper = summarize_bundle(backtests, cfg, annualization_mode="paper", mdd_mode=cfg.mdd_mode_paper)
    table2_paper.to_csv(out_dir / "table2_paper_formula.csv", index=False)
    table2_vs_paper = compare_with_table2_targets(table2_main)
    table2_vs_paper.to_csv(out_dir / "table2_vs_paper.csv", index=False)

    _regression_tables(backtests, loaded["ff3"], loaded["mom"], cfg, out_dir)
    wealth = _plot_cumulative(backtests, out_dir / "figure2_cumulative_returns.png")
    backtests.mom.meta.to_csv(out_dir / "backtest_meta.csv", index=False)

    note_lines = [
        "# Corrected bundle reproduction run",
        "",
        f"- Table 1 exact filter found: {sample.exact_match}",
        f"- Table 1 filter score: {sample.score}",
        f"- Table 1 filter window: {sample.start.date()} to {sample.end.date()}",
        "- Filter source: contiguous 2590-date block from common_dates_core.",
        "- Prior method: estimate D0 on 2010-2014 core26 pre-sample, then expand to 28 tickers via the 3-dimensional prior basis.",
        "- Strategy run mode: paper alignment, dynamic assets allowed.",
        "",
        "## Table 2 (main annualization)",
        "",
        table2_main.to_markdown(index=False),
    ]
    (out_dir / "report.md").write_text("\n".join(note_lines), encoding="utf-8")
    status = {
        "sample_filter_start": str(sample.start.date()),
        "sample_filter_end": str(sample.end.date()),
        "sample_filter_exact": sample.exact_match,
        "sample_filter_score": sample.score,
        "table1_counts_gap_sum": int(sample.table1_counts["gap"].abs().sum()),
        "prior_method": "expand26to28_from_2010_2014_core26",
        "alignment_mode": "paper",
        "dynamic_assets": True,
        "n_strategy_obs": {k: int(v.dropna().shape[0]) for k, v in {
            "MOM": backtests.mom.returns,
            "PCA_PLAIN": backtests.pca_plain.returns,
            "PCA_SUB": backtests.pca_sub.returns,
            "DOUBLE": backtests.double.returns,
        }.items()},
    }
    import json
    (out_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
