from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from leadlag.reporting.weekly_review import generate_weekly_review



def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')



def test_generate_weekly_review_outputs(tmp_path: Path) -> None:
    packets = []
    for idx, trade_date in enumerate(['2025-11-20', '2025-11-21', '2025-11-25']):
        packet_dir = tmp_path / f'packet_{idx}'
        packet_dir.mkdir()
        _write_json(
            packet_dir / 'run.json',
            {
                'expected_cost_bps': 15.0 + idx,
                'trade_date': trade_date,
            },
        )
        _write_json(
            packet_dir / 'risk_report.json',
            {
                'gross_exposure': 0.75,
                'net_exposure': 0.75,
                'max_name_abs': 0.15,
                'gate_results': {
                    'missing_price': {'triggered': idx == 2, 'severity': 'warning' if idx == 2 else 'ok'},
                },
            },
        )
        _write_json(
            packet_dir / 'alerts.json',
            {
                'alerts': [] if idx != 1 else [
                    {'severity': 'warning', 'code': 'scaled_for_single_name_cap', 'message': 'scaled'}
                ]
            },
        )
        packets.append(packet_dir)

    batch_summary = pd.DataFrame(
        [
            {
                'trade_date': '2025-11-20',
                'result': 'completed',
                'status': 'GO',
                'packet_dir': str(packets[0]),
                'shadow_net_return': 0.0100,
                'paper_counterfactual_return': 0.0050,
                'tradable_names': 17,
                'selected_names': 5,
            },
            {
                'trade_date': '2025-11-21',
                'result': 'completed',
                'status': 'GO',
                'packet_dir': str(packets[1]),
                'shadow_net_return': -0.0200,
                'paper_counterfactual_return': -0.0100,
                'tradable_names': 17,
                'selected_names': 5,
            },
            {
                'trade_date': '2025-11-25',
                'result': 'completed',
                'status': 'WARN',
                'packet_dir': str(packets[2]),
                'shadow_net_return': 0.0300,
                'paper_counterfactual_return': 0.0100,
                'tradable_names': 17,
                'selected_names': 5,
            },
        ]
    )
    batch_path = tmp_path / 'batch_summary.csv'
    batch_summary.to_csv(batch_path, index=False)

    out_dir, status = generate_weekly_review(batch_summary_path=batch_path, output_dir=tmp_path / 'weekly_review')
    assert out_dir.exists()
    assert status['daily_rows'] == 3
    assert status['weekly_rows'] == 2

    weekly = pd.read_csv(out_dir / 'weekly_summary.csv')
    assert list(weekly['week_label']) == ['2025-W47', '2025-W48']

    first_week_shadow = (1.01 * 0.98) - 1.0
    assert abs(float(weekly.loc[0, 'shadow_return_compounded']) - first_week_shadow) < 1e-12
    assert int(weekly.loc[1, 'warn_days']) == 1
    assert int(weekly.loc[0, 'warning_alert_days']) == 1

    md_text = (out_dir / 'weekly_summary.md').read_text(encoding='utf-8')
    assert 'Weekly shadow review' in md_text
    assert '2025-W48' in md_text
