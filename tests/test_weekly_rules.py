from __future__ import annotations

from pathlib import Path

import pandas as pd

from leadlag.reporting.weekly_rules import (
    assess_promotion,
    evaluate_weekly_status,
    generate_weekly_gates,
    load_rules_config,
)


def _sample_weekly_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_label": ["2025-W45", "2025-W46", "2025-W47", "2025-W48"],
            "week_start": pd.to_datetime(["2025-11-03", "2025-11-10", "2025-11-17", "2025-11-24"]),
            "week_end": pd.to_datetime(["2025-11-07", "2025-11-14", "2025-11-21", "2025-11-28"]),
            "trade_days": [4, 5, 5, 3],
            "completed_days": [4, 5, 5, 3],
            "go_days": [4, 5, 5, 3],
            "warn_days": [0, 0, 0, 0],
            "stop_days": [0, 0, 0, 0],
            "failed_days": [0, 0, 0, 0],
            "shadow_return_compounded": [-0.0023, 0.0036, -0.0105, -0.0012],
            "paper_return_compounded": [-0.0057, -0.0133, 0.0184, -0.0081],
            "active_return_diff_compounded": [0.0034, 0.0169, -0.0289, 0.0069],
            "shadow_return_mean": [-0.0005, 0.0007, -0.0021, -0.0004],
            "shadow_return_std": [0.0070, 0.0067, 0.0058, 0.0103],
            "shadow_hit_rate": [0.25, 0.60, 0.20, 0.6667],
            "avg_tradable_names": [17.0, 17.0, 17.0, 17.0],
            "avg_selected_names": [5.0, 5.0, 5.0, 5.0],
            "avg_expected_cost_bps": [15.0, 15.0, 15.0, 15.0],
            "avg_gross_exposure": [0.75, 0.75, 0.75, 0.75],
            "avg_alert_count": [1.0, 1.0, 1.0, 1.0],
            "warning_alert_days": [4, 5, 5, 3],
            "critical_alert_days": [0, 0, 0, 0],
            "triggered_gate_days": [0, 0, 0, 0],
            "shadow_nav_index": [0.9977, 1.0013, 0.9908, 0.9896],
            "paper_nav_index": [0.9943, 0.9810, 0.9990, 0.9910],
        }
    )


def test_weekly_status_and_promotion_default_rules(tmp_path: Path) -> None:
    rules = load_rules_config(Path('configs/review/weekly_rules_shadow_default.yaml'))
    status_df = evaluate_weekly_status(_sample_weekly_df(), rules)
    assert status_df['weekly_status'].tolist() == ['GO', 'GO', 'WARN', 'GO']
    promotion = assess_promotion(status_df, rules)
    assert promotion['promotion_status'] == 'HOLD_SHADOW'
    assert 'non_negative_shadow_return' in promotion['failed_checks']


def test_generate_weekly_gates_writes_outputs(tmp_path: Path) -> None:
    weekly_path = tmp_path / 'weekly_summary.csv'
    _sample_weekly_df().to_csv(weekly_path, index=False)
    out_dir, status = generate_weekly_gates(
        weekly_summary_path=weekly_path,
        rules_config_path=Path('configs/review/weekly_rules_shadow_default.yaml'),
        output_dir=tmp_path / 'gates',
    )
    assert out_dir.exists()
    assert status['promotion_status'] == 'HOLD_SHADOW'
    assert (out_dir / 'weekly_status_evaluated.csv').exists()
    assert (out_dir / 'promotion_assessment.json').exists()
    assert (out_dir / 'promotion_assessment.md').exists()
