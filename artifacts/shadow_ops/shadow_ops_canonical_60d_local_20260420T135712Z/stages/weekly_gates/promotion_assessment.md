# Weekly gates and promotion review

Source weekly summary: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T135712Z\stages\weekly_review\weekly_summary.csv`
Rules config: `weekly_rules_shadow_pre_live_v1`

## Latest weekly decisions

| week_label   | week_start          | week_end            | weekly_status   |   shadow_return_compounded |   shadow_hit_rate |   avg_tradable_names |   avg_expected_cost_bps | stop_reasons    | warn_reasons   |
|:-------------|:--------------------|:--------------------|:----------------|---------------------------:|------------------:|---------------------:|------------------------:|:----------------|:---------------|
| 2025-W44     | 2025-10-27 00:00:00 | 2025-10-31 00:00:00 | STOP            |                        nan |               nan |                  nan |                      15 | incomplete_week |                |
| 2025-W45     | 2025-11-03 00:00:00 | 2025-11-07 00:00:00 | STOP            |                        nan |               nan |                  nan |                      15 | incomplete_week |                |
| 2025-W46     | 2025-11-10 00:00:00 | 2025-11-14 00:00:00 | STOP            |                        nan |               nan |                  nan |                      15 | incomplete_week |                |
| 2025-W47     | 2025-11-17 00:00:00 | 2025-11-21 00:00:00 | STOP            |                        nan |               nan |                  nan |                      15 | incomplete_week |                |
| 2025-W48     | 2025-11-24 00:00:00 | 2025-11-28 00:00:00 | STOP            |                        nan |               nan |                  nan |                      15 | incomplete_week |                |

## Promotion assessment

Promotion status: **BLOCKED**

Reason: one or more blocking disqualifiers fired

### Promotion metrics

- window_weeks: 8
- latest_week_label: 2025-W48
- latest_week_status: STOP
- go_weeks: 0
- warn_weeks: 0
- stop_weeks: 8
- total_trade_days: 35
- total_shadow_return_compounded: None
- total_active_return_diff_compounded: None
- weighted_shadow_hit_rate: None
- weighted_avg_expected_cost_bps: 15.0
- weighted_avg_tradable_names: None
- total_critical_alert_days: 0
- total_triggered_gate_days: 0

### Blocking checks
- forbidden_weekly_status_present
- stop_weeks_present

### Failed requirements
- latest_week_status_gate
- non_negative_shadow_return
- sufficient_go_weeks
- adequate_universe_width
- acceptable_hit_rate

### Recommended small-live overrides
```yaml
run:
  mode: live_dryrun
risk:
  allow_short: false
  max_gross: 0.25
  max_single_name_abs: 0.05
deployment:
  max_live_names: 1
  fixed_ticket_notional_jpy: 25000
  expected_objective: Measure live-vs-shadow execution friction only; not PnL maximization.
```
