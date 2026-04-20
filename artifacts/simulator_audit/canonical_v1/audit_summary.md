# Canonical Simulator Golden-Day Audit

- Contract: `canonical_simulator_v1`
- Config: `configs/profiles/shadow_corrected_local.yaml`
- Golden days selected: 5
- Deterministic rerun required: True
- Deterministic rerun passed: `True`

## Golden Days

|   selection_rank | trade_date   | selection_reason       | matched_categories                              | status   |   alert_count | is_holiday_edge   |
|-----------------:|:-------------|:-----------------------|:------------------------------------------------|:---------|--------------:|:------------------|
|                1 | 2025-11-28   | latest_valid           | latest_valid;nonzero_alert;scaling_or_cap_alert | GO       |             1 | False             |
|                2 | 2025-11-26   | earlier_go             | earlier_go                                      | GO       |             1 | False             |
|                3 | 2025-11-25   | holiday_edge           | holiday_edge                                    | GO       |             1 | True              |
|                4 | 2025-08-27   | fallback_evenly_spaced | fallback_evenly_spaced                          | GO       |             1 | False             |
|                5 | 2025-09-03   | fallback_evenly_spaced | fallback_evenly_spaced                          | GO       |             1 | False             |

## Audit Summary

|   selection_rank | trade_date   | status   |   selected_names_count |   gross_exposure |   expected_cost_bps |   shadow_net_return |   alert_count |   triggered_gates_count | rerun_match   |
|-----------------:|:-------------|:---------|-----------------------:|-----------------:|--------------------:|--------------------:|--------------:|------------------------:|:--------------|
|                1 | 2025-11-28   | GO       |                      5 |             0.75 |                  15 |          0.00146086 |             1 |                       0 | True          |
|                2 | 2025-11-26   | GO       |                      5 |             0.75 |                  15 |          0.00886071 |             1 |                       0 | True          |
|                3 | 2025-11-25   | GO       |                      5 |             0.75 |                  15 |         -0.0114582  |             1 |                       0 | True          |
|                4 | 2025-08-27   | GO       |                      5 |             0.75 |                  15 |         -0.0027373  |             1 |                       0 | True          |
|                5 | 2025-09-03   | GO       |                      5 |             0.75 |                  15 |         -0.0074692  |             1 |                       0 | True          |

## Human Review Checklist

- `summary.md` が status / top longs / alerts を自然に説明しているかを確認する
- `signals.csv` と `orders_shadow.csv` の selected names / target weights が整合しているかを見る
- `fills_shadow.csv` と `pnl.csv` で same-day open/close two-fill assumption が意図どおり反映されているかを見る
- `alerts.json` と `risk_report.json` の triggered gate / scaling alert が想定どおりかを確認する
