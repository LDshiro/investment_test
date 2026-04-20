from __future__ import annotations

from pathlib import Path
import argparse
import json
from copy import deepcopy
from typing import Any

import pandas as pd
import yaml


OPS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


class WeeklyRulesError(RuntimeError):
    pass


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise WeeklyRulesError(f"rules config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_rules_config(path: str | Path) -> dict[str, Any]:
    path = Path(path).resolve()
    data = _load_yaml(path)
    merged: dict[str, Any] = {}
    for rel in data.get("extends", []) or []:
        parent = (path.parent / rel).resolve()
        merged = _deep_merge(merged, load_rules_config(parent))
    merged = _deep_merge(merged, data)
    return merged


def _resolve_weekly_summary_path(weekly_summary_path: str | Path | None = None, review_dir: str | Path | None = None) -> Path:
    if weekly_summary_path is None and review_dir is None:
        raise WeeklyRulesError("Provide either weekly_summary_path or review_dir.")
    if weekly_summary_path is not None:
        path = Path(weekly_summary_path)
    else:
        path = Path(review_dir) / "weekly_summary.csv"
    if not path.exists():
        raise WeeklyRulesError(f"weekly_summary.csv not found: {path}")
    return path


def load_weekly_summary(weekly_summary_path: str | Path | None = None, review_dir: str | Path | None = None) -> pd.DataFrame:
    path = _resolve_weekly_summary_path(weekly_summary_path, review_dir)
    df = pd.read_csv(path)
    if df.empty:
        return df
    for col in ["week_start", "week_end"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    numeric_like = [
        c for c in df.columns if c not in {"week_label", "week_start", "week_end"}
    ]
    for col in numeric_like:
        try:
            df[col] = pd.to_numeric(df[col])
        except (TypeError, ValueError):
            pass
    df = df.sort_values("week_start").reset_index(drop=True)
    return df


def _safe_div(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return float(a) / float(b)


def derive_weekly_metrics(weekly_df: pd.DataFrame) -> pd.DataFrame:
    out = weekly_df.copy()
    if out.empty:
        return out
    out["completed_ratio"] = out.apply(lambda r: _safe_div(r.get("completed_days"), r.get("trade_days")), axis=1)
    out["go_ratio"] = out.apply(lambda r: _safe_div(r.get("go_days"), r.get("trade_days")), axis=1)
    out["warn_ratio"] = out.apply(lambda r: _safe_div(r.get("warn_days"), r.get("trade_days")), axis=1)
    out["stop_ratio"] = out.apply(lambda r: _safe_div(r.get("stop_days"), r.get("trade_days")), axis=1)
    out["alert_day_ratio"] = out.apply(lambda r: _safe_div(r.get("warning_alert_days", 0) + r.get("critical_alert_days", 0), r.get("trade_days")), axis=1)
    out["gate_day_ratio"] = out.apply(lambda r: _safe_div(r.get("triggered_gate_days", 0), r.get("trade_days")), axis=1)
    return out


def _coerce_rule_value(value: Any) -> Any:
    if isinstance(value, list):
        return value
    return value


def _evaluate_rule(metric_value: Any, op: str, target_value: Any) -> bool:
    if op not in OPS:
        raise WeeklyRulesError(f"Unsupported op: {op}")
    if metric_value is None or pd.isna(metric_value):
        return False
    return bool(OPS[op](metric_value, _coerce_rule_value(target_value)))


def _apply_rule_set(row: pd.Series, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for rule in rules or []:
        metric = rule["metric"]
        op = rule["op"]
        value = rule["value"]
        metric_value = row.get(metric)
        if _evaluate_rule(metric_value, op, value):
            hits.append({
                "code": rule.get("code", metric),
                "metric": metric,
                "op": op,
                "threshold": value,
                "actual": None if pd.isna(metric_value) else metric_value,
                "message": rule.get("message", ""),
            })
    return hits


def evaluate_weekly_status(weekly_df: pd.DataFrame, rules_config: dict[str, Any]) -> pd.DataFrame:
    out = derive_weekly_metrics(weekly_df)
    if out.empty:
        out["weekly_status"] = []
        out["stop_reasons"] = []
        out["warn_reasons"] = []
        return out

    weekly_rules = rules_config.get("weekly_status", {})
    default_status = weekly_rules.get("default_status", "GO")
    stop_rules = weekly_rules.get("stop", [])
    warn_rules = weekly_rules.get("warn", [])

    statuses: list[str] = []
    stop_reasons_col: list[str | None] = []
    warn_reasons_col: list[str | None] = []
    decision_notes: list[str] = []

    for _, row in out.iterrows():
        stop_hits = _apply_rule_set(row, stop_rules)
        warn_hits = _apply_rule_set(row, warn_rules)
        if stop_hits:
            status = "STOP"
            note = "stop rules triggered"
        elif warn_hits:
            status = "WARN"
            note = "warn rules triggered"
        else:
            status = default_status
            note = "all rules passed"
        statuses.append(status)
        stop_reasons_col.append("; ".join(h["code"] for h in stop_hits) if stop_hits else None)
        warn_reasons_col.append("; ".join(h["code"] for h in warn_hits) if warn_hits else None)
        decision_notes.append(note)

    out["weekly_status"] = statuses
    out["stop_reasons"] = stop_reasons_col
    out["warn_reasons"] = warn_reasons_col
    out["decision_note"] = decision_notes
    return out


def _compound_from_weekly(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float((1.0 + s).prod() - 1.0)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce")
    mask = (~v.isna()) & (~w.isna()) & (w > 0)
    if not mask.any():
        return None
    return float((v[mask] * w[mask]).sum() / w[mask].sum())


def build_promotion_metrics(status_df: pd.DataFrame, rules_config: dict[str, Any]) -> dict[str, Any]:
    promo = rules_config.get("promotion", {})
    lookback = int(promo.get("lookback_weeks", 4))
    window = status_df.tail(lookback).copy()
    metrics: dict[str, Any] = {
        "window_weeks": int(window.shape[0]),
        "lookback_weeks": lookback,
        "latest_week_label": None if window.empty else str(window.iloc[-1]["week_label"]),
        "latest_week_status": None if window.empty else str(window.iloc[-1]["weekly_status"]),
    }
    if window.empty:
        return metrics

    weights = pd.to_numeric(window["trade_days"], errors="coerce").fillna(0)
    metrics.update({
        "go_weeks": int((window["weekly_status"] == "GO").sum()),
        "warn_weeks": int((window["weekly_status"] == "WARN").sum()),
        "stop_weeks": int((window["weekly_status"] == "STOP").sum()),
        "total_trade_days": int(pd.to_numeric(window["trade_days"], errors="coerce").fillna(0).sum()),
        "total_completed_days": int(pd.to_numeric(window["completed_days"], errors="coerce").fillna(0).sum()),
        "total_failed_days": int(pd.to_numeric(window["failed_days"], errors="coerce").fillna(0).sum()),
        "total_stop_days": int(pd.to_numeric(window["stop_days"], errors="coerce").fillna(0).sum()),
        "total_warn_days": int(pd.to_numeric(window["warn_days"], errors="coerce").fillna(0).sum()),
        "total_critical_alert_days": int(pd.to_numeric(window.get("critical_alert_days"), errors="coerce").fillna(0).sum()),
        "total_triggered_gate_days": int(pd.to_numeric(window.get("triggered_gate_days"), errors="coerce").fillna(0).sum()),
        "total_shadow_return_compounded": _compound_from_weekly(window["shadow_return_compounded"]),
        "total_paper_return_compounded": _compound_from_weekly(window["paper_return_compounded"]),
        "weighted_shadow_hit_rate": _weighted_mean(window["shadow_hit_rate"], weights),
        "weighted_avg_expected_cost_bps": _weighted_mean(window["avg_expected_cost_bps"], weights),
        "weighted_avg_tradable_names": _weighted_mean(window["avg_tradable_names"], weights),
        "weighted_avg_selected_names": _weighted_mean(window["avg_selected_names"], weights),
        "weighted_avg_gross_exposure": _weighted_mean(window["avg_gross_exposure"], weights),
        "weighted_avg_alert_count": _weighted_mean(window["avg_alert_count"], weights),
    })
    sret = metrics.get("total_shadow_return_compounded")
    pret = metrics.get("total_paper_return_compounded")
    metrics["total_active_return_diff_compounded"] = None if sret is None or pret is None else float(sret - pret)
    return metrics


def assess_promotion(status_df: pd.DataFrame, rules_config: dict[str, Any]) -> dict[str, Any]:
    promo = rules_config.get("promotion", {})
    metrics = build_promotion_metrics(status_df, rules_config)
    lookback = int(promo.get("lookback_weeks", 4))
    min_weeks = int(promo.get("min_weeks_required", lookback))
    ready_label = promo.get("label_ready", "READY_FOR_SMALL_LIVE")
    hold_label = promo.get("label_hold", "HOLD_SHADOW")
    blocked_label = promo.get("label_blocked", "BLOCKED")
    latest_allowed = set(promo.get("require_latest_week_status_in", ["GO"]))
    all_allowed = set(promo.get("require_all_week_status_in", ["GO", "WARN"]))

    if metrics.get("window_weeks", 0) < min_weeks:
        return {
            "promotion_status": hold_label,
            "reason": f"need at least {min_weeks} weekly observations",
            "metrics": metrics,
            "failed_checks": ["insufficient_history"],
            "recommended_live_overrides": None,
        }

    window = status_df.tail(lookback).copy()
    failed_checks: list[str] = []
    blocked_checks: list[str] = []

    latest_status = metrics.get("latest_week_status")
    if latest_status not in latest_allowed:
        failed_checks.append("latest_week_status_gate")
    if not set(window["weekly_status"].unique()).issubset(all_allowed):
        blocked_checks.append("forbidden_weekly_status_present")

    for rule in promo.get("disqualifiers", []) or []:
        if _evaluate_rule(metrics.get(rule["metric"]), rule["op"], rule["value"]):
            blocked_checks.append(rule.get("code", rule["metric"]))

    for rule in promo.get("requirements", []) or []:
        if not _evaluate_rule(metrics.get(rule["metric"]), rule["op"], rule["value"]):
            failed_checks.append(rule.get("code", rule["metric"]))

    if blocked_checks:
        status = blocked_label
        reason = "one or more blocking disqualifiers fired"
    elif failed_checks:
        status = hold_label
        reason = "promotion requirements not yet met"
    else:
        status = ready_label
        reason = "promotion requirements met"

    return {
        "promotion_status": status,
        "reason": reason,
        "metrics": metrics,
        "failed_checks": failed_checks,
        "blocked_checks": blocked_checks,
        "recommended_live_overrides": promo.get("recommended_live_overrides"),
    }


def build_markdown(status_df: pd.DataFrame, promotion: dict[str, Any], rules_config: dict[str, Any], source_path: Path) -> str:
    lines = []
    lines.append(f"# Weekly gates and promotion review")
    lines.append("")
    lines.append(f"Source weekly summary: `{source_path}`")
    lines.append(f"Rules config: `{rules_config.get('name', 'unnamed_rules')}`")
    lines.append("")
    lines.append("## Latest weekly decisions")
    lines.append("")
    if status_df.empty:
        lines.append("No weekly rows found.")
    else:
        latest = status_df.tail(5).copy()
        show_cols = [
            "week_label",
            "week_start",
            "week_end",
            "weekly_status",
            "shadow_return_compounded",
            "shadow_hit_rate",
            "avg_tradable_names",
            "avg_expected_cost_bps",
            "stop_reasons",
            "warn_reasons",
        ]
        lines.append(latest[show_cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Promotion assessment")
    lines.append("")
    lines.append(f"Promotion status: **{promotion['promotion_status']}**")
    lines.append("")
    lines.append(f"Reason: {promotion['reason']}")
    lines.append("")
    lines.append("### Promotion metrics")
    lines.append("")
    metrics = promotion.get("metrics", {})
    for key in [
        "window_weeks",
        "latest_week_label",
        "latest_week_status",
        "go_weeks",
        "warn_weeks",
        "stop_weeks",
        "total_trade_days",
        "total_shadow_return_compounded",
        "total_active_return_diff_compounded",
        "weighted_shadow_hit_rate",
        "weighted_avg_expected_cost_bps",
        "weighted_avg_tradable_names",
        "total_critical_alert_days",
        "total_triggered_gate_days",
    ]:
        if key in metrics:
            lines.append(f"- {key}: {metrics[key]}")
    if promotion.get("blocked_checks"):
        lines.append("")
        lines.append("### Blocking checks")
        lines.extend([f"- {item}" for item in promotion["blocked_checks"]])
    if promotion.get("failed_checks"):
        lines.append("")
        lines.append("### Failed requirements")
        lines.extend([f"- {item}" for item in promotion["failed_checks"]])
    if promotion.get("recommended_live_overrides"):
        lines.append("")
        lines.append("### Recommended small-live overrides")
        lines.append("```yaml")
        lines.append(yaml.safe_dump(promotion["recommended_live_overrides"], sort_keys=False, allow_unicode=True).rstrip())
        lines.append("```")
    lines.append("")
    return "\n".join(lines)

def write_outputs(status_df: pd.DataFrame, promotion: dict[str, Any], output_dir: str | Path, source_path: Path, rules_config: dict[str, Any]) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    status_csv = out / "weekly_status_evaluated.csv"
    status_json = out / "weekly_status_evaluated.json"
    promo_json = out / "promotion_assessment.json"
    promo_md = out / "promotion_assessment.md"
    status_df.to_csv(status_csv, index=False)
    status_json.write_text(status_df.to_json(orient="records", indent=2, force_ascii=False, date_format="iso"), encoding="utf-8")
    promo_json.write_text(json.dumps(promotion, ensure_ascii=False, indent=2), encoding="utf-8")
    promo_md.write_text(build_markdown(status_df, promotion, rules_config, source_path), encoding="utf-8")
    return {
        "weekly_status_csv": str(status_csv),
        "weekly_status_json": str(status_json),
        "promotion_assessment_json": str(promo_json),
        "promotion_assessment_md": str(promo_md),
    }


def generate_weekly_gates(
    weekly_summary_path: str | Path | None = None,
    review_dir: str | Path | None = None,
    rules_config_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    source_path = _resolve_weekly_summary_path(weekly_summary_path, review_dir)
    if rules_config_path is None:
        raise WeeklyRulesError("rules_config_path is required")
    rules = load_rules_config(rules_config_path)
    weekly_df = load_weekly_summary(weekly_summary_path=source_path)
    status_df = evaluate_weekly_status(weekly_df, rules)
    promotion = assess_promotion(status_df, rules)
    if output_dir is None:
        output_dir = source_path.parent / "weekly_gates"
    outputs = write_outputs(status_df, promotion, output_dir, source_path, rules)
    status = {
        "output_dir": str(Path(output_dir)),
        "weekly_rows": int(status_df.shape[0]),
        "latest_week": None if status_df.empty else str(status_df.iloc[-1]["week_label"]),
        "latest_week_status": None if status_df.empty else str(status_df.iloc[-1]["weekly_status"]),
        "promotion_status": promotion["promotion_status"],
        **outputs,
    }
    return Path(output_dir), status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate weekly GO/WARN/STOP and small-live promotion rules.")
    parser.add_argument("--weekly-summary", dest="weekly_summary", help="Path to weekly_summary.csv")
    parser.add_argument("--review-dir", dest="review_dir", help="Directory that contains weekly_summary.csv")
    parser.add_argument("--rules-config", dest="rules_config", required=True, help="Rules YAML")
    parser.add_argument("--output-dir", dest="output_dir", help="Directory to write evaluation outputs")
    args = parser.parse_args(argv)
    out_dir, status = generate_weekly_gates(
        weekly_summary_path=args.weekly_summary,
        review_dir=args.review_dir,
        rules_config_path=args.rules_config,
        output_dir=args.output_dir,
    )
    print(f"weekly gates completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
