# Runbook Summary

- runbook_id: `shadow_ops_runbook_v1`
- version: `1`
- scope: `shadow_pre_live`

## Operating modes

- `backtest`: Research and historical reproduction only.
- `historical_shadow`: Single-day or replay packet generation on historical corrected-bundle data.
- `continuous_shadow`: Repeated operational shadow monitoring over consecutive trade dates.
- `broker_dry_run`: Future phase for connectivity and operational rehearsal only.
- `tiny_live`: Future phase with explicit human approval and minimal capital.
- `full_live`: Future phase and out of scope for this runbook version.

## Operating stance

- Default operation remains shadow only in the current repo phase.
- `READY_FOR_SMALL_LIVE` is not permission to start live automatically.
- AI review is advisory; deterministic gates and human kill-switch authority take precedence.

## Status actions

| status               | summary                                                                          | required_action                                                                                    | shadow_continues   | escalation                                                                     |
|:---------------------|:---------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------|:-------------------|:-------------------------------------------------------------------------------|
| GO                   | Daily or weekly status is inside the current operating envelope.                 | Proceed with normal shadow monitoring and record the packet review.                                | True               | No special escalation beyond the standard daily review.                        |
| WARN                 | Operation is still within the safety envelope, but review attention is required. | Review packet details, alerts, and recent weekly context before the next cycle.                    | True               | Escalate to the designated reviewer if WARN repeats or clusters.               |
| STOP                 | A safety-relevant or operationally abnormal condition has occurred.              | Stop relying on the packet for deployment decisions and open an incident review.                   | False              | Immediate escalation to the human operator with kill-switch authority.         |
| HOLD_SHADOW          | Promotion requirements are not yet satisfied, so the system remains in shadow.   | Continue shadow observation, preserve artifacts, and reassess after more evidence accumulates.     | True               | Weekly review owner documents the unmet requirements and next evidence needed. |
| READY_FOR_SMALL_LIVE | The ruleset permits a separate human-reviewed small-live evaluation step.        | Start a formal human review before any live_dryrun or tiny-live change is approved.                | True               | Promotion committee or designated human reviewer must sign off explicitly.     |
| BLOCKED              | A blocking condition prevents promotion until resolved.                          | Resolve the blocking issue and rerun the relevant review artifacts before reconsidering promotion. | True               | Escalate according to the incident severity that caused the block.             |

## Manual override policy

Manual overrides are exceptional, must be human-authored, time-bounded, and linked to a reviewed incident or maintenance record. Overrides may document operational handling, but they do not authorize bypassing deterministic hard gates or silently changing promotion standards.

## Kill switch policy

A designated human operator must retain immediate authority to halt shadow/pre-live progression whenever safety, data integrity, or broker-control confidence is in doubt. Kill-switch use takes precedence over AI suggestions and routine review cadence.

## AI review policy

AI-assisted review may summarize packets, flag anomalies, and draft incident notes, but it is advisory only. Deterministic gates, runbook procedures, and human judgment remain authoritative.
