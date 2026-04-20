from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from leadlag import __version__
from leadlag.config.models import AppConfig
from leadlag.portfolio.costs import close_side_cost_bps, expected_roundtrip_cost_bps, open_side_cost_bps
from leadlag.portfolio.risk_gates import evaluate_hard_gates
from leadlag.portfolio.weights import long_short_equal_weight, scale_weights_to_limits
from leadlag.reporting.daily import build_daily_summary
from leadlag.runtime.meta import hash_config, hash_data_root, hash_tree, make_run_id, patch_version
from leadlag.runtime.packets import ensure_packet_layout
from leadlag_repro.config import ReproConfig
from leadlag_repro.corrected_bundle import (
    build_prior_expand26to28,
    find_table1_sample_filter,
    load_corrected_bundle as legacy_load_corrected_bundle,
    run_backtests_fast,
)
from leadlag_repro.metrics import cumulative_returns
from leadlag_repro.tickers import JP_TICKERS


STRATEGY_MAP = {
    "pca_sub": "PCA_SUB",
    "pca_plain": "PCA_PLAIN",
    "mom": "MOM",
    "double": "DOUBLE",
}


def _app_to_repro_config(cfg: AppConfig, data_root: Path) -> ReproConfig:
    return ReproConfig(
        data_root=data_root,
        factor_root=data_root,
        output_root=Path(cfg.run.runs_root),
        lookback=cfg.strategy.lookback_L,
        n_components=cfg.strategy.n_components_K,
        prior_dim=cfg.strategy.prior_dim_K0,
        lambda_reg=cfg.strategy.lambda_reg,
        q=cfg.strategy.quantile_q,
        cfull_start=str(cfg.sample.cfull_window_start),
        cfull_end=str(cfg.sample.cfull_window_end),
        eval_start="2015-01-01",
        eval_end="2025-12-31",
        alignment_mode="paper",
        cfull_method="post_inception_only",
        annualization_base_main=cfg.strategy.annualization_days or 252,
    )


def _select_sample_dates(cfg: AppConfig, loaded: dict[str, Any]):
    sample = find_table1_sample_filter(loaded["cc"], loaded["core_dates"])
    return sample, sample.dates


def _strategy_output(backtests, strategy_name: str):
    key = STRATEGY_MAP.get(strategy_name.lower(), strategy_name.upper())
    if key == "PCA_SUB":
        return backtests.pca_sub
    if key == "PCA_PLAIN":
        return backtests.pca_plain
    if key == "MOM":
        return backtests.mom
    if key == "DOUBLE":
        return backtests.double
    raise ValueError(f"Unsupported strategy for corrected shadow run: {strategy_name}")


def _latest_valid_trade_date(strategy_output) -> pd.Timestamp:
    valid = strategy_output.returns.dropna().index
    if len(valid) == 0:
        raise RuntimeError("No valid trade dates available for shadow run.")
    return pd.Timestamp(valid[-1])


def _resolve_trade_date(strategy_output, trade_date_override: str | None, cfg: AppConfig) -> pd.Timestamp:
    if trade_date_override:
        trade_date = pd.Timestamp(trade_date_override)
    elif cfg.run.historical_trade_date is not None:
        trade_date = pd.Timestamp(cfg.run.historical_trade_date)
    else:
        trade_date = _latest_valid_trade_date(strategy_output)

    if trade_date not in strategy_output.signals.index:
        available = strategy_output.signals.index
        raise RuntimeError(
            f"trade date {trade_date.date()} not available. valid range: {available.min().date()} -> {available.max().date()}"
        )
    return trade_date


def _price_frame(loaded: dict[str, Any], trade_date: pd.Timestamp) -> pd.DataFrame:
    open_px = loaded["open_adj"].loc[trade_date, JP_TICKERS].astype(float)
    close_px = loaded["close_adj"].loc[trade_date, JP_TICKERS].astype(float)
    return pd.DataFrame({"open_adj": open_px, "close_adj": close_px})


def _check_patch_approved(bundle_root: Path) -> tuple[bool, str | None]:
    patch_path = bundle_root / "patch_table.csv"
    if not patch_path.exists():
        return True, None
    patch = pd.read_csv(patch_path)
    if "approved" not in patch.columns:
        return True, "patch_table_present_without_approved_column"
    approved = bool(patch["approved"].fillna(False).astype(bool).all())
    return approved, None if approved else "unapproved_patch_rows_present"


def _factor_missing(loaded: dict[str, Any], trade_date: pd.Timestamp) -> bool:
    for key in ("ff3", "mom", "carhart4"):
        df = loaded.get(key)
        if df is None:
            return True
        if trade_date not in df.index:
            return True
    return False


def _build_tradable_weights(signal: pd.Series, cfg: AppConfig) -> tuple[pd.Series, list[dict]]:
    raw_weights = long_short_equal_weight(signal, cfg.strategy.quantile_q, allow_short=cfg.risk.allow_short)
    return scale_weights_to_limits(raw_weights, cfg.risk.max_gross, cfg.risk.max_single_name_abs)


def _previous_trade_date(strategy_output, trade_date: pd.Timestamp) -> pd.Timestamp | None:
    idx = strategy_output.signals.index
    pos = idx.get_indexer([trade_date])[0]
    if pos <= 0:
        return None
    return pd.Timestamp(idx[pos - 1])


def _orders_and_fills(
    trade_date: pd.Timestamp,
    weights: pd.Series,
    prices: pd.DataFrame,
    nav_jpy: float,
    cfg: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    pos_rows: list[dict[str, Any]] = []

    open_cost = open_side_cost_bps(cfg)
    close_cost = close_side_cost_bps(cfg)
    borrow_daily_bps = cfg.costs.borrow_fee_bps_annual / float(cfg.strategy.annualization_days or 252)

    gross_pnl_total = 0.0
    net_pnl_total = 0.0
    borrow_pnl_total = 0.0

    for ticker, weight in weights[weights != 0.0].items():
        open_mid = float(prices.at[ticker, "open_adj"])
        close_mid = float(prices.at[ticker, "close_adj"])
        open_sign = 1.0 if weight > 0 else -1.0
        close_sign = -1.0 if weight > 0 else 1.0
        open_exec = open_mid * (1.0 + open_sign * open_cost / 10000.0)
        close_exec = close_mid * (1.0 + close_sign * close_cost / 10000.0)
        target_notional = nav_jpy * abs(float(weight))
        qty_abs = target_notional / open_exec if open_exec > 0 else 0.0
        qty = qty_abs if weight > 0 else -qty_abs
        gross_pnl = qty * (close_mid - open_mid)
        net_pnl_pre_borrow = qty * (close_exec - open_exec)
        borrow_pnl = -(target_notional * borrow_daily_bps / 10000.0) if qty < 0 else 0.0
        net_pnl = net_pnl_pre_borrow + borrow_pnl

        gross_pnl_total += gross_pnl
        net_pnl_total += net_pnl
        borrow_pnl_total += borrow_pnl

        entry_side = "BUY" if qty > 0 else "SELL_SHORT"
        exit_side = "SELL" if qty > 0 else "BUY_TO_COVER"
        order_rows.append(
            {
                "date": trade_date.date().isoformat(),
                "ticker": ticker,
                "side": entry_side,
                "target_weight": float(weight),
                "intended_open_qty": float(abs(qty)),
                "intended_close_qty": float(abs(qty)),
                "open_price_adj": open_mid,
                "close_price_adj": close_mid,
                "target_notional_jpy": target_notional,
                "close_side": exit_side,
            }
        )
        fill_rows.extend(
            [
                {
                    "date": trade_date.date().isoformat(),
                    "ticker": ticker,
                    "fill_type": "open",
                    "side": entry_side,
                    "qty": float(abs(qty)),
                    "mid_price": open_mid,
                    "assumed_price": open_exec,
                    "cost_bps": open_cost,
                },
                {
                    "date": trade_date.date().isoformat(),
                    "ticker": ticker,
                    "fill_type": "close",
                    "side": exit_side,
                    "qty": float(abs(qty)),
                    "mid_price": close_mid,
                    "assumed_price": close_exec,
                    "cost_bps": close_cost,
                },
            ]
        )
        pos_rows.append(
            {
                "date": trade_date.date().isoformat(),
                "ticker": ticker,
                "weight": float(weight),
                "position_qty": float(qty),
                "open_price_adj": open_mid,
                "close_price_adj": close_mid,
                "gross_pnl_jpy": gross_pnl,
                "net_pnl_jpy": net_pnl,
                "borrow_pnl_jpy": borrow_pnl,
                "gross_return": gross_pnl / nav_jpy,
                "net_return": net_pnl / nav_jpy,
            }
        )

    pnl_df = pd.DataFrame(
        [
            {
                "date": trade_date.date().isoformat(),
                "gross_return": gross_pnl_total / nav_jpy,
                "net_return": net_pnl_total / nav_jpy,
                "cost_return": (net_pnl_total - gross_pnl_total) / nav_jpy,
                "gross_pnl_jpy": gross_pnl_total,
                "net_pnl_jpy": net_pnl_total,
                "cost_pnl_jpy": net_pnl_total - gross_pnl_total,
                "borrow_pnl_jpy": borrow_pnl_total,
                "cumulative_return": 1.0 + net_pnl_total / nav_jpy,
            }
        ]
    )
    return (
        pd.DataFrame(order_rows),
        pd.DataFrame(fill_rows),
        pd.DataFrame(pos_rows),
        pnl_df,
    )


def _write_signals_csv(
    path: Path,
    trade_date: pd.Timestamp,
    signal_raw: pd.Series,
    price_ready: pd.Series,
    paper_weights: pd.Series,
    tradable_weights: pd.Series,
) -> pd.DataFrame:
    rank = signal_raw.rank(ascending=False, method="first")
    df = pd.DataFrame(
        {
            "date": trade_date.date().isoformat(),
            "ticker": signal_raw.index,
            "signal_raw": signal_raw.values,
            "signal_rank": rank.reindex(signal_raw.index).values,
            "tradable_flag": price_ready.reindex(signal_raw.index).fillna(False).astype(bool).values,
            "paper_weight_raw": paper_weights.reindex(signal_raw.index).fillna(0.0).values,
            "target_weight": tradable_weights.reindex(signal_raw.index).fillna(0.0).values,
        }
    )
    df.to_csv(path, index=False)
    return df


def _top_names(signal: pd.Series, k: int = 5) -> list[tuple[str, float]]:
    s = signal.dropna().sort_values(ascending=False)
    return [(str(idx), float(val)) for idx, val in s.head(k).items()]


def _bottom_names(signal: pd.Series, k: int = 5) -> list[tuple[str, float]]:
    s = signal.dropna().sort_values(ascending=True)
    return [(str(idx), float(val)) for idx, val in s.head(k).items()]


def _signal_spread(signal: pd.Series) -> float:
    s = signal.dropna()
    if s.empty:
        return float("nan")
    return float(s.max() - s.min())


def _render_signal_chart(path: Path, signal: pd.Series, tradable_weights: pd.Series) -> None:
    s = signal.dropna().sort_values(ascending=False)
    plt.figure(figsize=(10, 4.5))
    plt.bar(s.index.astype(str), s.values)
    plt.xticks(rotation=60, ha="right")
    plt.title("PCA SUB signal snapshot")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _render_equity_curve(path: Path, returns: pd.Series, trade_date: pd.Timestamp) -> None:
    wealth = cumulative_returns(returns.loc[:trade_date])
    if wealth.empty:
        return
    plt.figure(figsize=(9, 4.5))
    plt.plot(wealth.index, wealth.values)
    plt.axvline(trade_date, linestyle="--")
    plt.title("Historical cumulative return up to shadow trade date")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def prepare_corrected_shadow_context(cfg: AppConfig) -> dict[str, Any]:
    bundle_root = Path(cfg.data.root)
    loaded = legacy_load_corrected_bundle(bundle_root)
    sample, sample_dates = _select_sample_dates(cfg, loaded)
    prior = build_prior_expand26to28(loaded["cc"], loaded["core_dates"], pre_start="2010-01-01", pre_end="2014-12-31")
    repro_cfg = _app_to_repro_config(cfg, bundle_root)
    backtests = run_backtests_fast(loaded["cc"], loaded["oc_jp"], sample_dates, prior, repro_cfg)
    strategy_output = _strategy_output(backtests, cfg.strategy.name)
    return {
        "bundle_root": bundle_root,
        "loaded": loaded,
        "sample": sample,
        "sample_dates": sample_dates,
        "prior": prior,
        "repro_cfg": repro_cfg,
        "backtests": backtests,
        "strategy_output": strategy_output,
    }


def build_corrected_shadow_day_preview(
    cfg: AppConfig,
    prepared: dict[str, Any],
    trade_date_override: str | None = None,
) -> dict[str, Any]:
    bundle_root = prepared["bundle_root"]
    loaded = prepared["loaded"]
    sample = prepared["sample"]
    sample_dates = prepared["sample_dates"]
    strategy_output = prepared["strategy_output"]
    trade_date = _resolve_trade_date(strategy_output, trade_date_override, cfg)

    meta_row = strategy_output.meta.loc[strategy_output.meta["trade_date"] == trade_date].iloc[0]
    us_date = pd.Timestamp(meta_row["us_date"])
    signal_raw = strategy_output.signals.loc[trade_date, JP_TICKERS].astype(float)
    prices = _price_frame(loaded, trade_date)
    price_ready = prices.notna().all(axis=1).reindex(signal_raw.index).fillna(False)
    signal_tradeable = signal_raw.where(price_ready).dropna()
    paper_weights = strategy_output.weights.get(trade_date, pd.Series(dtype=float)).reindex(signal_raw.index).fillna(0.0)
    tradable_weights, adjustments = _build_tradable_weights(signal_tradeable, cfg)
    tradable_weights = tradable_weights.reindex(signal_raw.index).fillna(0.0)

    gross_exposure = float(tradable_weights.abs().sum())
    short_exposure = float((-tradable_weights.clip(upper=0.0)).sum())
    expected_cost_bps = expected_roundtrip_cost_bps(cfg, gross_exposure=gross_exposure, short_exposure=short_exposure)
    patch_ok, patch_note = _check_patch_approved(bundle_root)
    missing_factor = _factor_missing(loaded, trade_date)
    missing_price = bool((signal_raw.notna() & ~price_ready).any())

    gate_result = evaluate_hard_gates(
        cfg,
        signal_tradeable,
        tradable_weights,
        expected_cost_bps,
        missing_price=missing_price,
        missing_factor=missing_factor,
        patch_approved=patch_ok,
        no_common_dates=trade_date not in sample_dates,
        universe_expected=len(cfg.universe.jp),
    )
    alerts = list(gate_result["alerts"]) + adjustments
    if patch_note:
        alerts.append({"severity": "warning", "code": "patch_note", "message": patch_note})

    prev_date = _previous_trade_date(strategy_output, trade_date)
    prev_signal_spread = None
    changed_names = None
    if prev_date is not None:
        prev_signal = strategy_output.signals.loc[prev_date, JP_TICKERS].astype(float)
        prev_prices = _price_frame(loaded, prev_date)
        prev_ready = prev_prices.notna().all(axis=1).reindex(prev_signal.index).fillna(False)
        prev_weights, _ = _build_tradable_weights(prev_signal.where(prev_ready).dropna(), cfg)
        prev_signal_spread = _signal_spread(prev_signal.where(prev_ready))
        changed_names = int(
            len(set(prev_weights[prev_weights != 0.0].index) ^ set(tradable_weights[tradable_weights != 0.0].index))
        )

    paper_counterfactual = float(strategy_output.returns.loc[trade_date]) if pd.notna(strategy_output.returns.loc[trade_date]) else None
    return {
        "bundle_root": bundle_root,
        "sample": sample,
        "sample_dates": sample_dates,
        "strategy_output": strategy_output,
        "trade_date": trade_date,
        "us_date": us_date,
        "signal_raw": signal_raw,
        "prices": prices,
        "price_ready": price_ready,
        "signal_tradeable": signal_tradeable,
        "paper_weights": paper_weights,
        "tradable_weights": tradable_weights,
        "expected_cost_bps": expected_cost_bps,
        "missing_factor": missing_factor,
        "missing_price": missing_price,
        "gate_result": gate_result,
        "alerts": alerts,
        "prev_date": prev_date,
        "prev_signal_spread": prev_signal_spread,
        "changed_names": changed_names,
        "paper_counterfactual_return": paper_counterfactual,
    }


def run_corrected_shadow_prepared(
    cfg: AppConfig,
    prepared: dict[str, Any],
    trade_date_override: str | None = None,
) -> tuple[Path, dict[str, object]]:
    started_at = datetime.now(timezone.utc)
    preview = build_corrected_shadow_day_preview(cfg, prepared, trade_date_override=trade_date_override)
    bundle_root = preview["bundle_root"]
    sample = preview["sample"]
    strategy_output = preview["strategy_output"]
    trade_date = preview["trade_date"]
    run_id = make_run_id(cfg.run.name, trade_date.date().isoformat())
    packet_dir = ensure_packet_layout(cfg, packet_name=run_id)

    us_date = preview["us_date"]
    signal_raw = preview["signal_raw"]
    prices = preview["prices"]
    price_ready = preview["price_ready"]
    signal_tradeable = preview["signal_tradeable"]
    paper_weights = preview["paper_weights"]
    tradable_weights = preview["tradable_weights"]
    expected_cost_bps = preview["expected_cost_bps"]
    gate_result = preview["gate_result"]
    alerts = preview["alerts"]

    if gate_result["status"] == "STOP":
        orders_df = pd.DataFrame(columns=["date", "ticker", "side", "target_weight", "intended_open_qty", "intended_close_qty"])
        fills_df = pd.DataFrame(columns=["date", "ticker", "fill_type", "side", "qty", "mid_price", "assumed_price", "cost_bps"])
        positions_df = pd.DataFrame(columns=["date", "ticker", "weight", "position_qty"])
        pnl_df = pd.DataFrame(
            [
                {
                    "date": trade_date.date().isoformat(),
                    "gross_return": 0.0,
                    "net_return": 0.0,
                    "cost_return": 0.0,
                    "gross_pnl_jpy": 0.0,
                    "net_pnl_jpy": 0.0,
                    "cost_pnl_jpy": 0.0,
                    "borrow_pnl_jpy": 0.0,
                    "cumulative_return": 1.0,
                }
            ]
        )
    else:
        orders_df, fills_df, positions_df, pnl_df = _orders_and_fills(trade_date, tradable_weights, prices, cfg.run.shadow_nav_jpy, cfg)

    signals_df = _write_signals_csv(packet_dir / "signals.csv", trade_date, signal_raw, price_ready, paper_weights, tradable_weights)
    orders_df.to_csv(packet_dir / "orders_shadow.csv", index=False)
    fills_df.to_csv(packet_dir / "fills_shadow.csv", index=False)
    positions_df.to_csv(packet_dir / "positions.csv", index=False)
    pnl_df.to_csv(packet_dir / "pnl.csv", index=False)

    prev_date = preview["prev_date"]
    prev_signal_spread = preview["prev_signal_spread"]
    changed_names = preview["changed_names"]

    if cfg.packet.include_charts:
        _render_signal_chart(packet_dir / "figure_signals.png", signal_tradeable, tradable_weights)
        _render_equity_curve(packet_dir / "figure_equity_curve.png", strategy_output.returns, trade_date)

    repo_root = Path(__file__).resolve().parents[3]
    finished_at = datetime.now(timezone.utc)
    paper_counterfactual = preview["paper_counterfactual_return"]
    run_json = {
        "run_id": run_id,
        "mode": cfg.run.mode,
        "code_version": f"leadlag-stack/{__version__}:{hash_tree(repo_root)}",
        "config_hash": hash_config(cfg),
        "data_version": hash_data_root(bundle_root, cfg.data.files),
        "patch_version": patch_version(bundle_root, cfg.data.files),
        "data_status": "STOP" if preview["missing_price"] or preview["missing_factor"] else "GO",
        "model_status": "GO" if int(signal_tradeable.shape[0]) > 0 else "STOP",
        "run_status": gate_result["status"],
        "strategy": STRATEGY_MAP.get(cfg.strategy.name.lower(), cfg.strategy.name),
        "bundle_root": str(bundle_root.resolve()),
        "sample_filter_start": str(sample.start.date()),
        "sample_filter_end": str(sample.end.date()),
        "sample_filter_exact": bool(sample.exact_match),
        "asof_us_date": str(us_date.date()),
        "trade_date": str(trade_date.date()),
        "shadow_nav_jpy": cfg.run.shadow_nav_jpy,
        "paper_counterfactual_return": paper_counterfactual,
        "shadow_net_return": float(pnl_df.iloc[0]["net_return"]),
        "shadow_gross_return": float(pnl_df.iloc[0]["gross_return"]),
        "expected_cost_bps": float(expected_cost_bps),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }
    (packet_dir / "run.json").write_text(json.dumps(run_json, ensure_ascii=False, indent=2), encoding="utf-8")

    risk_report = {
        "status": gate_result["status"],
        "gate_results": gate_result["gate_results"],
        "expected_cost_bps": expected_cost_bps,
        "gross_exposure": gate_result["gross_exposure"],
        "net_exposure": gate_result["net_exposure"],
        "max_name_abs": gate_result["max_name_abs"],
        "tradable_names": gate_result["tradable_names"],
        "selected_names": gate_result["selected_names"],
        "paper_gross_exposure": float(paper_weights.abs().sum()),
        "paper_net_exposure": float(paper_weights.sum()),
    }
    (packet_dir / "risk_report.json").write_text(json.dumps(risk_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (packet_dir / "alerts.json").write_text(json.dumps({"alerts": alerts}, ensure_ascii=False, indent=2), encoding="utf-8")

    top_longs = _top_names(signal_tradeable)
    top_shorts = _bottom_names(signal_tradeable)
    summary = build_daily_summary(
        gate_result["status"],
        alerts,
        expected_cost_bps,
        run_name=cfg.run.name,
        strategy=STRATEGY_MAP.get(cfg.strategy.name.lower(), cfg.strategy.name),
        trade_date=trade_date,
        us_date=us_date,
        tradable_names=int(gate_result["tradable_names"]),
        selected_names=int(gate_result["selected_names"]),
        gross_exposure=float(gate_result["gross_exposure"]),
        net_exposure=float(gate_result["net_exposure"]),
        shadow_nav_jpy=float(cfg.run.shadow_nav_jpy),
        realized_gross_return=float(pnl_df.iloc[0]["gross_return"]),
        realized_net_return=float(pnl_df.iloc[0]["net_return"]),
        paper_counterfactual_return=paper_counterfactual,
        prev_trade_date=prev_date,
        changed_names=changed_names,
        signal_spread=_signal_spread(signal_tradeable),
        prev_signal_spread=prev_signal_spread,
        top_longs=top_longs,
        top_shorts=top_shorts,
    )
    (packet_dir / "summary.md").write_text(summary, encoding="utf-8")

    status = {
        "run_id": run_id,
        "packet_dir": str(packet_dir),
        "trade_date": str(trade_date.date()),
        "asof_us_date": str(us_date.date()),
        "status": gate_result["status"],
        "tradable_names": int(gate_result["tradable_names"]),
        "selected_names": int(gate_result["selected_names"]),
        "shadow_net_return": float(pnl_df.iloc[0]["net_return"]),
        "paper_counterfactual_return": paper_counterfactual,
    }
    return packet_dir, status


def run_corrected_shadow(cfg: AppConfig, trade_date_override: str | None = None) -> tuple[Path, dict[str, object]]:
    prepared = prepare_corrected_shadow_context(cfg)
    return run_corrected_shadow_prepared(cfg, prepared, trade_date_override=trade_date_override)
