from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.reporting.weekly_rule_calibration import calibrate_weekly_rules
from leadlag.reporting.weekly_rules import assess_promotion, evaluate_weekly_status, load_rules_config


def _weekly_df_for_promotion(*, negative_window: bool = True) -> pd.DataFrame:
    returns = [-0.004, 0.002, 0.001, -0.003, 0.002, 0.001, -0.002, -0.001]
    if not negative_window:
        returns = [0.002, 0.001, 0.003, 0.001, 0.002, 0.002, 0.001, 0.001]
    return pd.DataFrame(
        {
            "week_label": [f"2025-W{41 + idx}" for idx in range(8)],
            "week_start": pd.date_range("2025-10-06", periods=8, freq="7D"),
            "week_end": pd.date_range("2025-10-10", periods=8, freq="7D"),
            "trade_days": [5, 4, 4, 5, 4, 5, 5, 3],
            "completed_days": [5, 4, 4, 5, 4, 5, 5, 3],
            "go_days": [5, 4, 4, 5, 4, 5, 5, 3],
            "warn_days": [0, 0, 0, 0, 0, 0, 0, 0],
            "stop_days": [0, 0, 0, 0, 0, 0, 0, 0],
            "failed_days": [0, 0, 0, 0, 0, 0, 0, 0],
            "shadow_return_compounded": returns,
            "paper_return_compounded": [value + 0.001 for value in returns],
            "active_return_diff_compounded": [-0.001] * 8,
            "shadow_return_mean": [value / 5 for value in returns],
            "shadow_return_std": [0.004] * 8,
            "shadow_hit_rate": [0.45] * 8,
            "avg_tradable_names": [17.0] * 8,
            "avg_selected_names": [5.0] * 8,
            "avg_expected_cost_bps": [15.0] * 8,
            "avg_gross_exposure": [0.75] * 8,
            "avg_alert_count": [1.0] * 8,
            "warning_alert_days": [1] * 8,
            "critical_alert_days": [0] * 8,
            "triggered_gate_days": [0] * 8,
            "shadow_nav_index": [1.0] * 8,
            "paper_nav_index": [1.0] * 8,
        }
    )


def test_pre_live_rules_config_loads() -> None:
    rules = load_rules_config(Path("configs/review/weekly_rules_shadow_pre_live_v1.yaml"))
    assert rules["name"] == "weekly_rules_shadow_pre_live_v1"
    assert rules["promotion"]["lookback_weeks"] == 8
    assert rules["promotion"]["min_weeks_required"] == 8


def test_default_rules_config_still_loads() -> None:
    rules = load_rules_config(Path("configs/review/weekly_rules_shadow_default.yaml"))
    assert rules["name"] == "weekly_rules_shadow_default"
    assert rules["promotion"]["lookback_weeks"] == 4


def test_stop_overrides_warn_and_go() -> None:
    rules = load_rules_config(Path("configs/review/weekly_rules_shadow_default.yaml"))
    weekly_df = _weekly_df_for_promotion(negative_window=False).head(1).copy()
    weekly_df.loc[:, "failed_days"] = 1
    weekly_df.loc[:, "shadow_return_compounded"] = -0.02
    status_df = evaluate_weekly_status(weekly_df, rules)
    assert status_df.iloc[0]["weekly_status"] == "STOP"
    assert "failed_days_present" in str(status_df.iloc[0]["stop_reasons"])


def test_promotion_blocked_when_failed_or_hard_gate_days_exist() -> None:
    rules = load_rules_config(Path("configs/review/weekly_rules_shadow_pre_live_v1.yaml"))
    weekly_df = _weekly_df_for_promotion(negative_window=False).copy()
    weekly_df.loc[0, "failed_days"] = 1
    weekly_df.loc[1, "triggered_gate_days"] = 1
    status_df = evaluate_weekly_status(weekly_df, rules)
    promotion = assess_promotion(status_df, rules)
    assert promotion["promotion_status"] == "BLOCKED"
    assert "failed_days_present" in promotion["blocked_checks"]
    assert "triggered_gate_days_present" in promotion["blocked_checks"]


def test_promotion_hold_when_operational_but_performance_not_met() -> None:
    rules = load_rules_config(Path("configs/review/weekly_rules_shadow_pre_live_v1.yaml"))
    status_df = evaluate_weekly_status(_weekly_df_for_promotion(negative_window=True), rules)
    promotion = assess_promotion(status_df, rules)
    assert promotion["promotion_status"] == "HOLD_SHADOW"
    assert "non_negative_shadow_return" in promotion["failed_checks"]


def test_weekly_rule_calibration_writes_outputs(tmp_path: Path) -> None:
    review_dirs: list[Path] = []
    for source_name in ["step05_legacy_60d", "step05_canonical_60d"]:
        review_dir = tmp_path / source_name / "weekly_review"
        review_dir.mkdir(parents=True)
        _weekly_df_for_promotion(negative_window=True).to_csv(review_dir / "weekly_summary.csv", index=False)
        review_dirs.append(review_dir)

    out_dir, status = calibrate_weekly_rules(
        weekly_review_dirs=review_dirs,
        rules_config_paths=[
            Path("configs/review/weekly_rules_shadow_default.yaml"),
            Path("configs/review/weekly_rules_shadow_small_live_candidate.yaml"),
            Path("configs/review/weekly_rules_shadow_pre_live_v1.yaml"),
        ],
        output_dir=tmp_path / "calibration",
    )

    assert out_dir.exists()
    assert status["recommended_decision"] == "HOLD_SHADOW"
    assert (out_dir / "calibration_report.md").exists()
    assert (out_dir / "ruleset_weekly_status_comparison.csv").exists()
    assert (out_dir / "promotion_comparison.csv").exists()
    assert (out_dir / "calibration_manifest.json").exists()

    promotion_df = pd.read_csv(out_dir / "promotion_comparison.csv")
    assert set(
        [
            "source_name",
            "ruleset_name",
            "promotion_status",
            "reason",
            "latest_week_status",
            "go_weeks",
            "warn_weeks",
            "stop_weeks",
            "total_trade_days",
            "total_shadow_return_compounded",
            "weighted_shadow_hit_rate",
            "weighted_avg_expected_cost_bps",
            "weighted_avg_tradable_names",
            "failed_requirements",
        ]
    ).issubset(promotion_df.columns)

    manifest = json.loads((out_dir / "calibration_manifest.json").read_text(encoding="utf-8"))
    assert manifest["recommended_decision"]["decision"] == "HOLD_SHADOW"
