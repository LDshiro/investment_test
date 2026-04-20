# Weekly And Deployment Checklist

## Weekly Review

1. Generate or inspect the latest weekly_summary.csv and weekly_status_evaluated.csv.
2. Review compounded shadow return, hit rate, tradable names, alert density, and triggered gate days.
3. Compare legacy and canonical replay stories before making any promotion recommendation.
4. Record whether the current state remains GO, WARN, STOP, HOLD_SHADOW, or BLOCKED.

## Deployment Review

1. Confirm baseline verification, data contract validation, and replay validation remain green.
2. Check that no unreviewed runtime, risk, simulator, or broker changes are pending.
3. Require explicit human approval before any live_dryrun or tiny-live change.
4. Confirm kill-switch ownership, rollback plan, and artifact retention are documented.

## Promotion Review

1. Treat READY_FOR_SMALL_LIVE as permission to review, not permission to deploy automatically.
2. Verify no blocking incidents remain open across P0 or P1 categories.
3. Confirm weekly gate evidence is stable across both legacy and canonical review sources.
4. Prefer HOLD_SHADOW when evidence is incomplete or sample quality is weak.
