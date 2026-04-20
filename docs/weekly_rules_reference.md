# Weekly rules reference

`weekly-review` produces a `weekly_summary.csv`. The weekly rules layer reads that file and emits:

- `weekly_status_evaluated.csv`
- `weekly_status_evaluated.json`
- `promotion_assessment.json`
- `promotion_assessment.md`

The rules YAML has two blocks.

## `weekly_status`

Per-week GO/WARN/STOP classification.

- `stop`: any hit forces `STOP`
- `warn`: used only if no stop rule fires
- `default_status`: usually `GO`

Each rule supports:

- `metric`
- `op`: `gt`, `gte`, `lt`, `lte`, `eq`, `neq`, `in`, `not_in`
- `value`
- `code`
- `message`

## `promotion`

Rolling lookback decision for small-live promotion.

- `lookback_weeks`
- `min_weeks_required`
- `require_latest_week_status_in`
- `require_all_week_status_in`
- `disqualifiers`: any hit -> `BLOCKED`
- `requirements`: unmet requirement -> `HOLD_SHADOW`
- `recommended_live_overrides`: emitted only as guidance

`promotion_status` is one of:

- `READY_FOR_SMALL_LIVE`
- `HOLD_SHADOW`
- `BLOCKED`
