from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

import pandas as pd

from leadlag.config.models import AppConfig
from leadlag.runtime.corrected_shadow import (
    prepare_corrected_shadow_context,
    run_corrected_shadow_prepared,
)


def _available_dates(prepared: dict[str, Any]) -> pd.DatetimeIndex:
    strategy_output = prepared["strategy_output"]
    return pd.DatetimeIndex(strategy_output.signals.index).sort_values().unique()


def _sample_filter_dates(prepared: dict[str, Any]) -> pd.DatetimeIndex:
    sample_dates = prepared["sample_dates"]
    return pd.DatetimeIndex(sample_dates).sort_values().unique()


def resolve_batch_trade_dates(cfg: AppConfig, prepared: dict[str, Any]) -> pd.DatetimeIndex:
    available = _available_dates(prepared)
    if cfg.batch.trade_dates:
        dates = pd.DatetimeIndex(pd.to_datetime([str(d) for d in cfg.batch.trade_dates]))
    elif cfg.batch.date_source == "strategy_index":
        dates = available
    else:
        dates = _sample_filter_dates(prepared)

    if cfg.batch.start_date is not None:
        dates = dates[dates >= pd.Timestamp(cfg.batch.start_date)]
    if cfg.batch.end_date is not None:
        dates = dates[dates <= pd.Timestamp(cfg.batch.end_date)]

    dates = dates.intersection(available).sort_values().unique()

    if cfg.batch.max_days is not None:
        dates = dates[-int(cfg.batch.max_days):]

    return pd.DatetimeIndex(dates)


def _existing_packet_for_date(cfg: AppConfig, trade_date: pd.Timestamp) -> Path | None:
    runs_root = Path(cfg.run.runs_root)
    if not runs_root.exists():
        return None
    prefix = f"{cfg.run.name}_{trade_date.date().isoformat()}_"
    candidates = sorted([p for p in runs_root.iterdir() if p.is_dir() and p.name.startswith(prefix)])
    for p in reversed(candidates):
        if (p / "run.json").exists():
            return p
    return None


def _batch_dir(cfg: AppConfig, trade_dates: pd.DatetimeIndex) -> Path:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label_start = trade_dates.min().date().isoformat() if len(trade_dates) else "empty"
    label_end = trade_dates.max().date().isoformat() if len(trade_dates) else "empty"
    path = Path(cfg.run.runs_root) / f"{cfg.run.name}_batch_{label_start}_{label_end}_{now}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_batch_summary(batch_dir: Path, rows: list[dict[str, Any]]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(batch_dir / "batch_summary.csv", index=False)
    (batch_dir / "batch_summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if df.empty:
        md = "# Historical shadow batch summary\n\nNo dates were selected.\n"
    else:
        total = len(df)
        completed = int((df["result"] == "completed").sum())
        skipped = int((df["result"] == "skipped_existing").sum())
        failed = int((df["result"] == "failed").sum())
        stop_runs = int((df.get("status", pd.Series(dtype=object)) == "STOP").sum())
        warn_text = []
        if failed:
            warn_text.append(f"failed={failed}")
        if stop_runs:
            warn_text.append(f"STOP={stop_runs}")
        warn_line = ", ".join(warn_text) if warn_text else "none"
        md = f"""# Historical shadow batch summary

- total dates: {total}
- completed: {completed}
- skipped_existing: {skipped}
- failed: {failed}
- stop runs: {stop_runs}
- notable issues: {warn_line}

## Date table

| trade_date | result | status | packet_dir | shadow_net_return | paper_counterfactual_return |
|---|---|---|---|---:|---:|
"""
        for _, row in df.iterrows():
            md += f"| {row.get('trade_date','')} | {row.get('result','')} | {row.get('status','')} | {row.get('packet_dir','')} | {row.get('shadow_net_return','')} | {row.get('paper_counterfactual_return','')} |\n"
    (batch_dir / "batch_summary.md").write_text(md, encoding="utf-8")


def run_corrected_shadow_batch(cfg: AppConfig) -> tuple[Path, dict[str, Any]]:
    prepared = prepare_corrected_shadow_context(cfg)
    trade_dates = resolve_batch_trade_dates(cfg, prepared)
    batch_dir = _batch_dir(cfg, trade_dates)

    rows: list[dict[str, Any]] = []
    for trade_date in trade_dates:
        existing = _existing_packet_for_date(cfg, trade_date) if cfg.batch.skip_existing_packets else None
        if existing is not None:
            rows.append({
                "trade_date": trade_date.date().isoformat(),
                "result": "skipped_existing",
                "status": "SKIPPED",
                "packet_dir": str(existing),
                "shadow_net_return": None,
                "paper_counterfactual_return": None,
            })
            continue

        try:
            packet_dir, status = run_corrected_shadow_prepared(cfg, prepared, trade_date_override=trade_date.date().isoformat())
            rows.append({
                "trade_date": trade_date.date().isoformat(),
                "result": "completed",
                **status,
            })
        except Exception as exc:  # pragma: no cover - defensive runtime path
            row = {
                "trade_date": trade_date.date().isoformat(),
                "result": "failed",
                "status": "ERROR",
                "packet_dir": None,
                "shadow_net_return": None,
                "paper_counterfactual_return": None,
                "error": repr(exc),
            }
            rows.append(row)
            if cfg.batch.stop_on_error:
                _write_batch_summary(batch_dir, rows)
                raise

    _write_batch_summary(batch_dir, rows)
    status = {
        "batch_dir": str(batch_dir),
        "dates_requested": int(len(trade_dates)),
        "completed": int(sum(1 for row in rows if row.get("result") == "completed")),
        "skipped_existing": int(sum(1 for row in rows if row.get("result") == "skipped_existing")),
        "failed": int(sum(1 for row in rows if row.get("result") == "failed")),
    }
    return batch_dir, status
