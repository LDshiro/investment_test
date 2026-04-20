# Weekly gates and promotion review

Source weekly summary: `artifacts\shadow_replay_validation\step05_legacy_60d\weekly_review\weekly_summary.csv`
Rules config: `weekly_rules_shadow_pre_live_v1`

## Latest weekly decisions

| week_label   | week_start          | week_end            | weekly_status   |   shadow_return_compounded |   shadow_hit_rate |   avg_tradable_names |   avg_expected_cost_bps | stop_reasons   | warn_reasons                                                        |
|:-------------|:--------------------|:--------------------|:----------------|---------------------------:|------------------:|---------------------:|------------------------:|:---------------|:--------------------------------------------------------------------|
| 2025-W44     | 2025-10-27 00:00:00 | 2025-10-31 00:00:00 | WARN            |                -0.00652782 |          0.4      |                   17 |                      15 |                | active_underperformance_watch                                       |
| 2025-W45     | 2025-11-03 00:00:00 | 2025-11-07 00:00:00 | GO              |                -0.00225295 |          0.25     |                   17 |                      15 |                | nan                                                                 |
| 2025-W46     | 2025-11-10 00:00:00 | 2025-11-14 00:00:00 | GO              |                 0.00364859 |          0.6      |                   17 |                      15 |                | nan                                                                 |
| 2025-W47     | 2025-11-17 00:00:00 | 2025-11-21 00:00:00 | WARN            |                -0.0104558  |          0.2      |                   17 |                      15 |                | weekly_drawdown_watch; active_underperformance_watch; hit_rate_soft |
| 2025-W48     | 2025-11-24 00:00:00 | 2025-11-28 00:00:00 | GO              |                -0.00124213 |          0.666667 |                   17 |                      15 |                | nan                                                                 |

## Promotion assessment

Promotion status: **HOLD_SHADOW**

Reason: promotion requirements not yet met

### Promotion metrics

- window_weeks: 8
- latest_week_label: 2025-W48
- latest_week_status: GO
- go_weeks: 4
- warn_weeks: 4
- stop_weeks: 0
- total_trade_days: 35
- total_shadow_return_compounded: -0.028247632153910907
- total_active_return_diff_compounded: -0.08957157227020307
- weighted_shadow_hit_rate: 0.37142857142857144
- weighted_avg_expected_cost_bps: 15.0
- weighted_avg_tradable_names: 17.0
- total_critical_alert_days: 0
- total_triggered_gate_days: 0

### Failed requirements
- non_negative_shadow_return
- sufficient_go_weeks
- limited_warn_weeks
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
