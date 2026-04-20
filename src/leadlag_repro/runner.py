
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ReproConfig
from .factors import load_japan_ff3_and_mom
from .metrics import compare_with_table2_targets, cumulative_returns, summarize_bundle
from .panel import (
    basic_stats_in_window,
    counts_in_window,
    infer_majority_eval_window,
)
from .regression import carhart4_regression, ff3_regression, result_to_row
from .strategy import run_backtests
from .synthetic import generate_synthetic_dataset
from .tickers import TABLE1_TARGET_COUNTS, US_TICKERS, JP_TICKERS
from .yahoo_csv import available_date_bounds, load_yahoo_universe

MAJORITY_TICKERS = [t for t in (US_TICKERS + JP_TICKERS) if t not in {"XLC", "XLRE"}]

def _json_default(obj: Any):
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return str(obj)

def _save_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=True)

def _table1_counts_report(counts: pd.Series) -> pd.DataFrame:
    target = pd.Series(TABLE1_TARGET_COUNTS, name="target")
    actual = counts.rename("actual")
    out = pd.concat([actual, target], axis=1)
    out["gap"] = out["actual"] - out["target"]
    out.index.name = "Ticker"
    return out.reset_index()

def _regression_tables(
    bundle,
    ff3: pd.DataFrame,
    mom: pd.DataFrame,
    config: ReproConfig,
    out_dir: Path,
) -> dict[str, Path]:
    annualization_base = config.annualization_base_main
    outputs = {
        "MOM": bundle.mom.returns,
        "PCA_PLAIN": bundle.pca_plain.returns,
        "PCA_SUB": bundle.pca_sub.returns,
        "DOUBLE": bundle.double.returns,
    }
    ff3_paths = {}
    car_paths = {}
    for lag in config.nw_lag_grid:
        ff_rows = []
        car_rows = []
        for name, ret in outputs.items():
            ff_res = ff3_regression(
                ret,
                ff3,
                annualization_base=annualization_base,
                nw_lag=lag,
                subtract_rf=config.subtract_rf_in_regression,
            )
            ff_rows.append(result_to_row(name, ff_res))

            car_res = carhart4_regression(
                ret,
                ff3,
                mom,
                annualization_base=annualization_base,
                nw_lag=lag,
                subtract_rf=config.subtract_rf_in_regression,
            )
            car_rows.append(result_to_row(name, car_res))

        ff_df = pd.DataFrame(ff_rows)
        car_df = pd.DataFrame(car_rows)
        ff_path = out_dir / f"table3_ff3_nw{lag}.csv"
        car_path = out_dir / f"table4_carhart4_nw{lag}.csv"
        ff_df.to_csv(ff_path, index=False)
        car_df.to_csv(car_path, index=False)
        ff3_paths[f"ff3_nw{lag}"] = ff_path
        car_paths[f"carhart4_nw{lag}"] = car_path
    return {**ff3_paths, **car_paths}

def _cumulative_wealth_table(bundle) -> pd.DataFrame:
    series = {
        "MOM": cumulative_returns(bundle.mom.returns),
        "PCA_PLAIN": cumulative_returns(bundle.pca_plain.returns),
        "PCA_SUB": cumulative_returns(bundle.pca_sub.returns),
        "DOUBLE": cumulative_returns(bundle.double.returns),
    }
    return pd.concat(series, axis=1)

def _status_payload(config: ReproConfig, note: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "config": asdict(config),
        "note": note,
    }
    if extras:
        payload.update(extras)
    return payload

def run_synthetic(output_root: Path | str) -> dict[str, Path]:
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = ReproConfig(output_root=out_dir, cfull_method="post_inception_only", alignment_mode="paper", eval_end="2019-12-31", majority_target_count=900)
    data, ff3, mom, config = generate_synthetic_dataset(config)

    date_bounds = available_date_bounds(data)
    date_bounds.to_csv(out_dir / "date_bounds.csv", index=False)

    window = infer_majority_eval_window(
        data,
        majority_tickers=MAJORITY_TICKERS,
        field="ret_cc_adj",
        target_count=config.majority_target_count,
        end=config.eval_end,
    )
    local_cfg = replace(
        config,
        eval_start=str(window.start.date()),
        eval_end=str(window.end.date()),
    )

    counts = counts_in_window(data, "ret_cc_adj", window.start, window.end)
    table1_counts = _table1_counts_report(counts)
    table1_counts.to_csv(out_dir / "table1_counts.csv", index=False)

    table1_stats = basic_stats_in_window(
        data,
        field="ret_cc_adj",
        start=window.start,
        end=window.end,
        annualization_base=local_cfg.annualization_base_main,
    )
    table1_stats.to_csv(out_dir / "table1_stats.csv", index=False)

    bundle = run_backtests(data, local_cfg)

    table2_main = summarize_bundle(bundle, local_cfg, annualization_mode="main", mdd_mode=local_cfg.mdd_mode_main)
    table2_main.to_csv(out_dir / "table2_main.csv", index=False)
    table2_paper = summarize_bundle(bundle, local_cfg, annualization_mode="paper", mdd_mode=local_cfg.mdd_mode_paper)
    table2_paper.to_csv(out_dir / "table2_paper_formula.csv", index=False)
    compare_with_table2_targets(table2_main).to_csv(out_dir / "table2_vs_paper_targets.csv", index=False)

    wealth = _cumulative_wealth_table(bundle)
    wealth.to_csv(out_dir / "cumulative_returns.csv")

    reg_paths = _regression_tables(bundle, ff3, mom, local_cfg, out_dir)

    status = _status_payload(
        local_cfg,
        note="Synthetic end-to-end validation completed.",
        extras={
            "eval_window_start": window.start,
            "eval_window_end": window.end,
            "files": {**{p.stem: str(p) for p in out_dir.glob('*.csv')}, **{k: str(v) for k, v in reg_paths.items()}},
        },
    )
    (out_dir / "status.json").write_text(json.dumps(status, indent=2, default=_json_default), encoding="utf-8")

    summary_lines = [
        "# Synthetic validation report",
        "",
        "This run validates the implementation end-to-end on a synthetic market.",
        "",
        f"- Evaluation window: {window.start.date()} to {window.end.date()}",
        f"- Alignment mode: {local_cfg.alignment_mode}",
        f"- C_full window: {local_cfg.cfull_start} to {local_cfg.cfull_end}",
        f"- Number of majority dates: {len(window.majority_dates)}",
        "",
        "## Table 2 (main annualization)",
        "",
        table2_main.to_markdown(index=False),
        "",
        "## Regression outputs",
        "",
        "Saved FF3 and Carhart4 tables for each Newey-West lag in the configured grid.",
        "",
        "## Notes",
        "",
        "- Synthetic data are designed so that the lead-lag mechanism exists by construction.",
        "- The purpose of this report is implementation validation, not economic evidence.",
    ]
    (out_dir / "report.md").write_text("\n".join(summary_lines), encoding="utf-8")
    return {p.name: p for p in sorted(out_dir.iterdir()) if p.is_file()}

def run_local_with_yahoo_csvs(config: ReproConfig) -> dict[str, Path]:
    out_dir = Path(config.output_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load_yahoo_universe(config.data_root)
    available_date_bounds(data).to_csv(out_dir / "date_bounds.csv", index=False)

    window = infer_majority_eval_window(
        data,
        majority_tickers=MAJORITY_TICKERS,
        field="ret_cc_adj" if config.use_adjusted_ohlc else "ret_cc_raw",
        target_count=config.majority_target_count,
        end=config.eval_end,
    )
    local_cfg = replace(config, eval_start=str(window.start.date()), eval_end=str(window.end.date()))

    counts = counts_in_window(
        data,
        "ret_cc_adj" if config.use_adjusted_ohlc else "ret_cc_raw",
        window.start,
        window.end,
    )
    _table1_counts_report(counts).to_csv(out_dir / "table1_counts.csv", index=False)

    basic_stats_in_window(
        data,
        field="ret_cc_adj" if config.use_adjusted_ohlc else "ret_cc_raw",
        start=window.start,
        end=window.end,
        annualization_base=config.annualization_base_main,
    ).to_csv(out_dir / "table1_stats.csv", index=False)

    bundle = run_backtests(data, local_cfg)
    summarize_bundle(bundle, local_cfg, annualization_mode="main", mdd_mode=local_cfg.mdd_mode_main).to_csv(
        out_dir / "table2_main.csv", index=False
    )
    summarize_bundle(bundle, local_cfg, annualization_mode="paper", mdd_mode=local_cfg.mdd_mode_paper).to_csv(
        out_dir / "table2_paper_formula.csv", index=False
    )

    try:
        ff3, mom = load_japan_ff3_and_mom(config.factor_root)
        _regression_tables(bundle, ff3, mom, local_cfg, out_dir)
        factor_note = "Factor regressions completed."
    except Exception as e:
        factor_note = f"Factor regressions skipped: {e}"

    status = _status_payload(
        local_cfg,
        note="Local Yahoo CSV reproduction run completed.",
        extras={
            "eval_window_start": window.start,
            "eval_window_end": window.end,
            "factor_note": factor_note,
        },
    )
    (out_dir / "status.json").write_text(json.dumps(status, indent=2, default=_json_default), encoding="utf-8")
    return {p.name: p for p in sorted(out_dir.iterdir()) if p.is_file()}

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lead-lag sector reproduction runner")
    sub = p.add_subparsers(dest="mode", required=True)

    p_syn = sub.add_parser("synthetic", help="Run full synthetic smoke validation")
    p_syn.add_argument("--output-root", default="artifacts/synthetic", type=str)

    p_loc = sub.add_parser("local", help="Run on local Yahoo Finance CSV exports")
    p_loc.add_argument("--data-root", default="data/raw/yahoo", type=str)
    p_loc.add_argument("--factor-root", default="data/raw/factors", type=str)
    p_loc.add_argument("--output-root", default="artifacts/local", type=str)
    p_loc.add_argument("--alignment-mode", default="paper", choices=["paper", "robust"])
    p_loc.add_argument("--cfull-method", default="post_inception_only", choices=["post_inception_only", "proxy_backfill"])
    p_loc.add_argument("--eval-end", default="2025-12-31", type=str)
    return p

def main(argv: list[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.mode == "synthetic":
        run_synthetic(args.output_root)
        return

    if args.mode == "local":
        cfg = ReproConfig(
            data_root=Path(args.data_root),
            factor_root=Path(args.factor_root),
            output_root=Path(args.output_root),
            alignment_mode=args.alignment_mode,
            cfull_method=args.cfull_method,
            eval_end=args.eval_end,
        )
        run_local_with_yahoo_csvs(cfg)
        return

if __name__ == "__main__":
    main()
