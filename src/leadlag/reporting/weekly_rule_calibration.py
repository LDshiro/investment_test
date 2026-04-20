from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .weekly_rules import (
    assess_promotion,
    evaluate_weekly_status,
    load_rules_config,
    load_weekly_summary,
)


class WeeklyRuleCalibrationError(RuntimeError):
    pass


def _resolve_review_dir(review_dir: str | Path) -> Path:
    path = Path(review_dir).resolve()
    weekly_summary = path / "weekly_summary.csv"
    if not weekly_summary.exists():
        raise WeeklyRuleCalibrationError(f"weekly_summary.csv not found under review dir: {path}")
    return path


def _source_name(review_dir: Path) -> str:
    if review_dir.name == "weekly_review" and review_dir.parent.name:
        return review_dir.parent.name
    return review_dir.name


def _string_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def _collect_weekly_rows(source_name: str, ruleset_name: str, status_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in status_df.iterrows():
        rows.append(
            {
                "source_name": source_name,
                "ruleset_name": ruleset_name,
                "week_label": str(row["week_label"]),
                "weekly_status": str(row["weekly_status"]),
                "stop_reasons": _string_or_none(row.get("stop_reasons")),
                "warn_reasons": _string_or_none(row.get("warn_reasons")),
                "shadow_return_compounded": row.get("shadow_return_compounded"),
                "shadow_hit_rate": row.get("shadow_hit_rate"),
                "avg_tradable_names": row.get("avg_tradable_names"),
                "avg_expected_cost_bps": row.get("avg_expected_cost_bps"),
            }
        )
    return rows


def _collect_promotion_row(source_name: str, ruleset_name: str, promotion: dict[str, Any]) -> dict[str, Any]:
    metrics = promotion.get("metrics", {})
    failed = [*promotion.get("blocked_checks", []), *promotion.get("failed_checks", [])]
    return {
        "source_name": source_name,
        "ruleset_name": ruleset_name,
        "promotion_status": promotion.get("promotion_status"),
        "reason": promotion.get("reason"),
        "latest_week_status": metrics.get("latest_week_status"),
        "go_weeks": metrics.get("go_weeks"),
        "warn_weeks": metrics.get("warn_weeks"),
        "stop_weeks": metrics.get("stop_weeks"),
        "total_trade_days": metrics.get("total_trade_days"),
        "total_shadow_return_compounded": metrics.get("total_shadow_return_compounded"),
        "weighted_shadow_hit_rate": metrics.get("weighted_shadow_hit_rate"),
        "weighted_avg_expected_cost_bps": metrics.get("weighted_avg_expected_cost_bps"),
        "weighted_avg_tradable_names": metrics.get("weighted_avg_tradable_names"),
        "failed_requirements": "; ".join(str(item) for item in failed) if failed else None,
    }


def _determine_recommended_decision(promotion_df: pd.DataFrame) -> dict[str, str]:
    if promotion_df.empty:
        return {
            "decision": "HOLD_SHADOW",
            "reason": "No promotion rows were available for calibration.",
        }

    pre_live = promotion_df[promotion_df["ruleset_name"] == "weekly_rules_shadow_pre_live_v1"].copy()
    if pre_live.empty:
        return {
            "decision": "HOLD_SHADOW",
            "reason": "The pre-live ruleset was not included in the calibration set.",
        }

    if (pre_live["promotion_status"] == "BLOCKED").any():
        blocked_rows = pre_live[pre_live["promotion_status"] == "BLOCKED"]
        details = "; ".join(
            f"{row.source_name}: {row.failed_requirements or row.reason}"
            for row in blocked_rows.itertuples(index=False)
        )
        return {
            "decision": "BLOCKED",
            "reason": f"Blocking conditions are still present under the pre-live ruleset: {details}",
        }

    if (pre_live["promotion_status"] == "READY_FOR_PRE_LIVE_DRYRUN").all():
        return {
            "decision": "READY_FOR_PRE_LIVE_DRYRUN",
            "reason": "Both legacy and canonical review sources satisfy the stricter pre-live ruleset.",
        }

    details = "; ".join(
        f"{row.source_name}: {row.failed_requirements or row.reason}"
        for row in pre_live.itertuples(index=False)
    )
    return {
        "decision": "HOLD_SHADOW",
        "reason": f"Pre-live promotion requirements are not yet met: {details}",
    }


def _build_markdown(
    weekly_df: pd.DataFrame,
    promotion_df: pd.DataFrame,
    review_dirs: list[Path],
    rulesets: list[dict[str, str]],
    recommendation: dict[str, str],
) -> str:
    lines: list[str] = []
    lines.append("# Weekly rule calibration")
    lines.append("")
    lines.append("This report compares multiple weekly rulesets across the legacy and canonical Step 05 weekly reviews.")
    lines.append("")
    lines.append("## Review sources")
    lines.append("")
    for review_dir in review_dirs:
        lines.append(f"- `{_source_name(review_dir)}`: `{review_dir}`")
    lines.append("")
    lines.append("## Rulesets")
    lines.append("")
    for item in rulesets:
        lines.append(f"- `{item['ruleset_name']}`: `{item['path']}`")
    lines.append("")
    lines.append("## Promotion comparison")
    lines.append("")
    if promotion_df.empty:
        lines.append("No promotion rows were generated.")
    else:
        view = promotion_df[
            [
                "source_name",
                "ruleset_name",
                "promotion_status",
                "latest_week_status",
                "reason",
                "failed_requirements",
            ]
        ].copy()
        lines.append(view.fillna("").to_markdown(index=False))
    lines.append("")
    lines.append("## Recommended decision")
    lines.append("")
    lines.append(f"Current recommendation: **{recommendation['decision']}**")
    lines.append("")
    lines.append(recommendation["reason"])
    lines.append("")
    if not promotion_df.empty:
        lines.append("## Status comparison notes")
        lines.append("")
        latest_by_ruleset = (
            weekly_df.sort_values(["source_name", "ruleset_name", "week_label"])
            .groupby(["source_name", "ruleset_name"], as_index=False)
            .tail(1)
        )
        lines.append(
            latest_by_ruleset[
                ["source_name", "ruleset_name", "week_label", "weekly_status", "stop_reasons", "warn_reasons"]
            ]
            .fillna("")
            .to_markdown(index=False)
        )
    lines.append("")
    lines.append("A HOLD_SHADOW result is acceptable at this stage. Step 06 is a calibration step, not a readiness-forcing step.")
    lines.append("")
    return "\n".join(lines)


def calibrate_weekly_rules(
    weekly_review_dirs: list[str | Path],
    rules_config_paths: list[str | Path],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    if not weekly_review_dirs:
        raise WeeklyRuleCalibrationError("At least one weekly review directory is required.")
    if not rules_config_paths:
        raise WeeklyRuleCalibrationError("At least one rules config path is required.")

    resolved_review_dirs = [_resolve_review_dir(path) for path in weekly_review_dirs]
    resolved_rules = [Path(path).resolve() for path in rules_config_paths]
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    weekly_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    ruleset_manifest: list[dict[str, str]] = []

    for rules_path in resolved_rules:
        rules = load_rules_config(rules_path)
        ruleset_name = str(rules.get("name", rules_path.stem))
        ruleset_manifest.append({"ruleset_name": ruleset_name, "path": str(rules_path)})

        for review_dir in resolved_review_dirs:
            source_name = _source_name(review_dir)
            weekly_summary = load_weekly_summary(review_dir=review_dir)
            status_df = evaluate_weekly_status(weekly_summary, rules)
            promotion = assess_promotion(status_df, rules)
            weekly_rows.extend(_collect_weekly_rows(source_name, ruleset_name, status_df))
            promotion_rows.append(_collect_promotion_row(source_name, ruleset_name, promotion))

    weekly_df = pd.DataFrame(weekly_rows)
    promotion_df = pd.DataFrame(promotion_rows)
    recommendation = _determine_recommended_decision(promotion_df)

    weekly_csv = out_dir / "ruleset_weekly_status_comparison.csv"
    promotion_csv = out_dir / "promotion_comparison.csv"
    report_md = out_dir / "calibration_report.md"
    manifest_json = out_dir / "calibration_manifest.json"

    weekly_df.to_csv(weekly_csv, index=False)
    promotion_df.to_csv(promotion_csv, index=False)
    report_md.write_text(
        _build_markdown(weekly_df, promotion_df, resolved_review_dirs, ruleset_manifest, recommendation),
        encoding="utf-8",
    )
    manifest_json.write_text(
        json.dumps(
            {
                "review_sources": [
                    {"source_name": _source_name(review_dir), "review_dir": str(review_dir)} for review_dir in resolved_review_dirs
                ],
                "rulesets": ruleset_manifest,
                "recommended_decision": recommendation,
                "generated_files": {
                    "ruleset_weekly_status_comparison_csv": str(weekly_csv),
                    "promotion_comparison_csv": str(promotion_csv),
                    "calibration_report_md": str(report_md),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    status = {
        "output_dir": str(out_dir),
        "review_source_count": len(resolved_review_dirs),
        "ruleset_count": len(resolved_rules),
        "comparison_rows": int(weekly_df.shape[0]),
        "promotion_rows": int(promotion_df.shape[0]),
        "recommended_decision": recommendation["decision"],
    }
    return out_dir, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare multiple weekly rulesets across weekly review directories.")
    parser.add_argument(
        "--weekly-review-dir",
        dest="weekly_review_dirs",
        action="append",
        required=True,
        help="Directory that contains weekly_summary.csv. Repeat for multiple sources.",
    )
    parser.add_argument(
        "--rules-config",
        dest="rules_configs",
        action="append",
        required=True,
        help="Weekly rules config YAML. Repeat for multiple rulesets.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for calibration outputs.")
    args = parser.parse_args(argv)

    out_dir, status = calibrate_weekly_rules(
        weekly_review_dirs=args.weekly_review_dirs,
        rules_config_paths=args.rules_configs,
        output_dir=args.output_dir,
    )
    print(f"weekly rule calibration completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
