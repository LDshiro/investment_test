from __future__ import annotations

from pathlib import Path
import argparse
import json
import math
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


NUMERIC_COLS = [
    "shadow_net_return",
    "paper_counterfactual_return",
    "tradable_names",
    "selected_names",
    "expected_cost_bps",
    "gross_exposure",
    "net_exposure",
    "max_name_abs",
    "alert_count",
    "warning_alert_count",
    "critical_alert_count",
    "info_alert_count",
    "triggered_gate_count",
    "critical_gate_count",
]


def _compound_return(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float((1.0 + s).prod() - 1.0)



def _mean_or_none(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.mean())



def _std_or_none(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.shape[0] <= 1:
        return None
    return float(s.std(ddof=1))



def _share_positive(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float((s > 0).mean())



def _fmt_pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return f"{x * 100.0:.2f}%"



def _resolve_batch_summary_path(batch_summary_path: str | Path | None, batch_dir: str | Path | None) -> Path:
    if batch_summary_path is None and batch_dir is None:
        raise ValueError("Provide either batch_summary_path or batch_dir.")
    if batch_summary_path is not None:
        path = Path(batch_summary_path)
    else:
        path = Path(batch_dir) / "batch_summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"Batch summary not found: {path}")
    return path



def load_batch_summary(batch_summary_path: str | Path | None = None, batch_dir: str | Path | None = None) -> pd.DataFrame:
    path = _resolve_batch_summary_path(batch_summary_path, batch_dir)
    df = pd.read_csv(path)
    if "trade_date" not in df.columns:
        raise ValueError(f"trade_date column not found in {path}")
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    if "asof_us_date" in df.columns:
        df["asof_us_date"] = pd.to_datetime(df["asof_us_date"], errors="coerce")
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("trade_date").reset_index(drop=True)
    return df



def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))



def _packet_extras(packet_dir: str | Path | None) -> dict[str, Any]:
    base = {
        "expected_cost_bps": None,
        "gross_exposure": None,
        "net_exposure": None,
        "max_name_abs": None,
        "alert_count": 0,
        "warning_alert_count": 0,
        "critical_alert_count": 0,
        "info_alert_count": 0,
        "triggered_gate_count": 0,
        "critical_gate_count": 0,
        "alert_codes": None,
    }
    if packet_dir is None or (isinstance(packet_dir, float) and math.isnan(packet_dir)):
        return base
    packet_path = Path(str(packet_dir))
    if not packet_path.exists():
        return base

    run_meta = _read_json(packet_path / "run.json") or {}
    risk = _read_json(packet_path / "risk_report.json") or {}
    alerts_doc = _read_json(packet_path / "alerts.json") or {}
    alerts = alerts_doc.get("alerts", []) if isinstance(alerts_doc, dict) else []
    gate_results = risk.get("gate_results", {}) if isinstance(risk, dict) else {}

    warning_alerts = [a for a in alerts if a.get("severity") == "warning"]
    critical_alerts = [a for a in alerts if a.get("severity") == "critical"]
    info_alerts = [a for a in alerts if a.get("severity") not in {"warning", "critical"}]
    triggered_gates = [g for g in gate_results.values() if g.get("triggered")]
    critical_gates = [g for g in triggered_gates if g.get("severity") == "critical"]

    base.update(
        {
            "expected_cost_bps": run_meta.get("expected_cost_bps", risk.get("expected_cost_bps")),
            "gross_exposure": risk.get("gross_exposure"),
            "net_exposure": risk.get("net_exposure"),
            "max_name_abs": risk.get("max_name_abs"),
            "alert_count": len(alerts),
            "warning_alert_count": len(warning_alerts),
            "critical_alert_count": len(critical_alerts),
            "info_alert_count": len(info_alerts),
            "triggered_gate_count": len(triggered_gates),
            "critical_gate_count": len(critical_gates),
            "alert_codes": ",".join(sorted({str(a.get('code')) for a in alerts if a.get('code')})) or None,
        }
    )
    return base



def enrich_batch_summary(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "packet_dir" in out.columns:
        extras_records = []
        for packet_dir in out["packet_dir"].fillna(""):
            extras_records.append(_packet_extras(packet_dir if packet_dir else None))
        extras = pd.DataFrame(extras_records)
        out = pd.concat([out.reset_index(drop=True), extras.reset_index(drop=True)], axis=1)

    out["week_start"] = out["trade_date"] - pd.to_timedelta(out["trade_date"].dt.weekday, unit="D")
    out["iso_year"] = out["trade_date"].dt.isocalendar().year.astype("Int64")
    out["iso_week"] = out["trade_date"].dt.isocalendar().week.astype("Int64")
    out["week_label"] = out["iso_year"].astype(str) + "-W" + out["iso_week"].astype(str).str.zfill(2)
    out["active_return_diff"] = pd.to_numeric(out.get("shadow_net_return"), errors="coerce") - pd.to_numeric(
        out.get("paper_counterfactual_return"), errors="coerce"
    )
    out["completed_flag"] = out.get("result", "") == "completed"
    out["go_flag"] = out.get("status", "") == "GO"
    out["warn_flag"] = out.get("status", "") == "WARN"
    out["stop_flag"] = out.get("status", "") == "STOP"
    out["error_flag"] = out.get("status", "") == "ERROR"
    for col in NUMERIC_COLS + ["active_return_diff"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_values("trade_date").reset_index(drop=True)



def aggregate_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame(
            columns=[
                "week_label",
                "week_start",
                "week_end",
                "trade_days",
                "completed_days",
                "go_days",
                "warn_days",
                "stop_days",
                "failed_days",
                "shadow_return_compounded",
                "paper_return_compounded",
                "active_return_diff_compounded",
                "shadow_return_mean",
                "shadow_return_std",
                "shadow_hit_rate",
                "avg_tradable_names",
                "avg_selected_names",
                "avg_expected_cost_bps",
                "avg_gross_exposure",
                "avg_alert_count",
                "warning_alert_days",
                "critical_alert_days",
                "triggered_gate_days",
            ]
        )

    rows: list[dict[str, Any]] = []
    for week_start, grp in daily_df.groupby("week_start", sort=True):
        shadow_comp = _compound_return(grp["shadow_net_return"]) if "shadow_net_return" in grp else None
        paper_comp = _compound_return(grp["paper_counterfactual_return"]) if "paper_counterfactual_return" in grp else None
        row = {
            "week_label": grp["week_label"].iloc[0],
            "week_start": pd.Timestamp(week_start),
            "week_end": pd.Timestamp(grp["trade_date"].max()),
            "trade_days": int(grp.shape[0]),
            "completed_days": int((grp.get("result") == "completed").sum()) if "result" in grp else int(grp.shape[0]),
            "go_days": int((grp.get("status") == "GO").sum()) if "status" in grp else 0,
            "warn_days": int((grp.get("status") == "WARN").sum()) if "status" in grp else 0,
            "stop_days": int((grp.get("status") == "STOP").sum()) if "status" in grp else 0,
            "failed_days": int((grp.get("result") == "failed").sum()) if "result" in grp else 0,
            "shadow_return_compounded": shadow_comp,
            "paper_return_compounded": paper_comp,
            "active_return_diff_compounded": None if shadow_comp is None or paper_comp is None else float(shadow_comp - paper_comp),
            "shadow_return_mean": _mean_or_none(grp["shadow_net_return"]) if "shadow_net_return" in grp else None,
            "shadow_return_std": _std_or_none(grp["shadow_net_return"]) if "shadow_net_return" in grp else None,
            "shadow_hit_rate": _share_positive(grp["shadow_net_return"]) if "shadow_net_return" in grp else None,
            "avg_tradable_names": _mean_or_none(grp["tradable_names"]) if "tradable_names" in grp else None,
            "avg_selected_names": _mean_or_none(grp["selected_names"]) if "selected_names" in grp else None,
            "avg_expected_cost_bps": _mean_or_none(grp["expected_cost_bps"]) if "expected_cost_bps" in grp else None,
            "avg_gross_exposure": _mean_or_none(grp["gross_exposure"]) if "gross_exposure" in grp else None,
            "avg_alert_count": _mean_or_none(grp["alert_count"]) if "alert_count" in grp else None,
            "warning_alert_days": int((pd.to_numeric(grp.get("warning_alert_count"), errors="coerce").fillna(0) > 0).sum()) if "warning_alert_count" in grp else 0,
            "critical_alert_days": int((pd.to_numeric(grp.get("critical_alert_count"), errors="coerce").fillna(0) > 0).sum()) if "critical_alert_count" in grp else 0,
            "triggered_gate_days": int((pd.to_numeric(grp.get("triggered_gate_count"), errors="coerce").fillna(0) > 0).sum()) if "triggered_gate_count" in grp else 0,
        }
        rows.append(row)

    weekly = pd.DataFrame(rows).sort_values("week_start").reset_index(drop=True)
    if not weekly.empty:
        weekly["shadow_nav_index"] = (1.0 + weekly["shadow_return_compounded"].fillna(0.0)).cumprod()
        weekly["paper_nav_index"] = (1.0 + weekly["paper_return_compounded"].fillna(0.0)).cumprod()
    return weekly



def _plot_weekly_nav(weekly_df: pd.DataFrame, output_path: Path) -> None:
    if weekly_df.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(weekly_df["week_end"], weekly_df["shadow_nav_index"], marker="o", label="shadow")
    if "paper_nav_index" in weekly_df.columns:
        ax.plot(weekly_df["week_end"], weekly_df["paper_nav_index"], marker="o", label="paper")
    ax.set_title("Weekly compounded return index")
    ax.set_xlabel("week_end")
    ax.set_ylabel("index")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)



def _plot_weekly_status(weekly_df: pd.DataFrame, output_path: Path) -> None:
    if weekly_df.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(weekly_df))
    width = 0.25
    ax.bar(x - width, weekly_df["go_days"], width, label="GO")
    ax.bar(x, weekly_df["warn_days"], width, label="WARN")
    ax.bar(x + width, weekly_df["stop_days"], width, label="STOP")
    ax.set_xticks(x)
    ax.set_xticklabels(weekly_df["week_label"], rotation=45, ha="right")
    ax.set_ylabel("days")
    ax.set_title("Weekly run statuses")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)



def build_weekly_markdown(daily_df: pd.DataFrame, weekly_df: pd.DataFrame, source_path: Path) -> str:
    lines = ["# Weekly shadow review", ""]
    lines.append(f"- source batch summary: `{source_path}`")
    lines.append(f"- total daily rows: {int(daily_df.shape[0])}")
    lines.append(f"- weekly rows: {int(weekly_df.shape[0])}")
    if not daily_df.empty:
        lines.append(f"- date range: {daily_df['trade_date'].min().date()} -> {daily_df['trade_date'].max().date()}")
    lines.append("")

    if weekly_df.empty:
        lines.append("No weekly rows were generated.")
        return "\n".join(lines)

    latest = weekly_df.iloc[-1]
    lines.append("## Latest week")
    lines.append("")
    lines.append(f"- week: **{latest['week_label']}**")
    lines.append(f"- week end: **{pd.Timestamp(latest['week_end']).date()}**")
    lines.append(f"- trade days: {int(latest['trade_days'])}")
    lines.append(f"- compounded shadow return: {_fmt_pct(latest['shadow_return_compounded'])}")
    lines.append(f"- compounded paper return: {_fmt_pct(latest['paper_return_compounded'])}")
    lines.append(f"- active return difference: {_fmt_pct(latest['active_return_diff_compounded'])}")
    lines.append(f"- shadow hit rate: {_fmt_pct(latest['shadow_hit_rate'])}")
    lines.append(f"- avg expected cost: {latest['avg_expected_cost_bps'] if pd.notna(latest['avg_expected_cost_bps']) else 'n/a'}")
    lines.append("")
    lines.append("## Weekly table")
    lines.append("")
    lines.append("| week_label | week_end | trade_days | GO | WARN | STOP | shadow_comp | paper_comp | active_diff | hit_rate | avg_cost_bps |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in weekly_df.iterrows():
        lines.append(
            f"| {row['week_label']} | {pd.Timestamp(row['week_end']).date()} | {int(row['trade_days'])} | {int(row['go_days'])} | {int(row['warn_days'])} | {int(row['stop_days'])} | {_fmt_pct(row['shadow_return_compounded'])} | {_fmt_pct(row['paper_return_compounded'])} | {_fmt_pct(row['active_return_diff_compounded'])} | {_fmt_pct(row['shadow_hit_rate'])} | {row['avg_expected_cost_bps'] if pd.notna(row['avg_expected_cost_bps']) else 'n/a'} |"
        )
    return "\n".join(lines)



def write_weekly_review_outputs(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    output_dir: str | Path,
    source_path: str | Path,
) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    daily_path = out / "daily_enriched.csv"
    weekly_csv = out / "weekly_summary.csv"
    weekly_json = out / "weekly_summary.json"
    weekly_md = out / "weekly_summary.md"
    nav_png = out / "weekly_nav_index.png"
    status_png = out / "weekly_status_counts.png"

    daily_df.to_csv(daily_path, index=False)
    weekly_df.to_csv(weekly_csv, index=False)
    weekly_json.write_text(weekly_df.to_json(orient="records", force_ascii=False, indent=2, date_format="iso"), encoding="utf-8")
    weekly_md.write_text(build_weekly_markdown(daily_df, weekly_df, Path(source_path)), encoding="utf-8")
    _plot_weekly_nav(weekly_df, nav_png)
    _plot_weekly_status(weekly_df, status_png)

    return {
        "daily_enriched_csv": str(daily_path),
        "weekly_summary_csv": str(weekly_csv),
        "weekly_summary_json": str(weekly_json),
        "weekly_summary_md": str(weekly_md),
        "weekly_nav_index_png": str(nav_png),
        "weekly_status_counts_png": str(status_png),
    }



def generate_weekly_review(
    batch_summary_path: str | Path | None = None,
    batch_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    source_path = _resolve_batch_summary_path(batch_summary_path, batch_dir)
    if output_dir is None:
        output_dir = source_path.parent / "weekly_review"
    daily_df = enrich_batch_summary(load_batch_summary(batch_summary_path=source_path))
    weekly_df = aggregate_weekly(daily_df)
    outputs = write_weekly_review_outputs(daily_df, weekly_df, output_dir, source_path)
    status = {
        "output_dir": str(Path(output_dir)),
        "daily_rows": int(daily_df.shape[0]),
        "weekly_rows": int(weekly_df.shape[0]),
        "latest_week": weekly_df.iloc[-1]["week_label"] if not weekly_df.empty else None,
        **outputs,
    }
    return Path(output_dir), status



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build weekly review outputs from a historical shadow batch summary.")
    parser.add_argument("--batch-summary", dest="batch_summary", help="Path to batch_summary.csv")
    parser.add_argument("--batch-dir", dest="batch_dir", help="Directory that contains batch_summary.csv")
    parser.add_argument("--output-dir", dest="output_dir", help="Directory to write weekly review artifacts")
    args = parser.parse_args(argv)
    out_dir, status = generate_weekly_review(
        batch_summary_path=args.batch_summary,
        batch_dir=args.batch_dir,
        output_dir=args.output_dir,
    )
    print(f"weekly review completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
