# Shadow Ops Runbook v1

## 1. Scope and non-goals

This runbook covers shadow and pre-live operations for the lead-lag stack. It is an
operations guide, not a trading-logic guide. It does not change PCA logic, sample
filtering, corrected bundle values, simulator economics, daily hard gates, weekly
rules, promotion thresholds, or broker interfaces.

In the current repo phase, default operation remains shadow only.

## 2. Operating modes

- `backtest`: research and reproduction mode
- `historical shadow`: one-day or replay packet generation against known historical data
- `continuous shadow`: repeated operational monitoring over consecutive trade dates
- `broker dry-run`: future phase for connectivity and operational rehearsal
- `tiny live`: future phase with minimal capital and explicit human approval
- `full live`: future phase and out of scope for this runbook

## 3. Daily operating cycle

### US close / data update

- confirm the corrected bundle update completed
- confirm the intended trade date is present and sample-filter compatible
- verify no unresolved data-contract or baseline failures exist

### JP pre-open review

- read `summary.md`, `run.json`, `risk_report.json`, and `alerts.json`
- confirm packet status and required files
- review canonical sidecars when enabled
- record GO / WARN / STOP action for the day

### JP close / post-close review

- inspect `fills_shadow.csv`, `positions.csv`, and `pnl.csv`
- note whether actual behavior still matches the expected packet narrative
- preserve links to the packet and any review notes

## 4. Daily packet checklist

Required packet files:

- `summary.md`
- `run.json`
- `signals.csv`
- `orders_shadow.csv`
- `fills_shadow.csv`
- `positions.csv`
- `pnl.csv`
- `risk_report.json`
- `alerts.json`

Canonical sidecars when enabled:

- `canonical_orders.csv`
- `canonical_fills.csv`
- `canonical_positions.csv`
- `canonical_pnl.csv`
- `canonical_simulation_result.json`
- `sim_reconciliation.csv`
- `sim_reconciliation.json`
- `sim_reconciliation.md`

## 5. GO / WARN / STOP actions

- `GO`: continue normal shadow monitoring and log the packet review
- `WARN`: continue shadow, but review alerts, drift, and recent weekly context before the next cycle
- `STOP`: treat as an operational/safety incident; preserve artifacts and escalate immediately

`STOP` is for safety or operational abnormality. Poor but non-catastrophic performance
should usually become `WARN` or `HOLD_SHADOW`, not `STOP`.

## 6. Weekly review procedure

- read `weekly_summary.csv`, `weekly_status_evaluated.csv`, and promotion artifacts
- compare legacy and canonical replay outcomes before any interpretation change
- review compounded return, hit rate, tradable breadth, expected cost, and alert density
- document the latest state and any unresolved issues

## 7. Weekly gates and promotion assessment interpretation

- weekly status answers whether recent operation was orderly and safe enough to continue shadow
- promotion status answers whether there is enough evidence to consider a separate pre-live review
- `READY_FOR_SMALL_LIVE` is not permission to start live automatically. It only permits a separate human-reviewed small-live step.
- `HOLD_SHADOW` is acceptable and often desirable while evidence is still building
- `BLOCKED` means a disqualifying issue must be resolved before promotion can even be reconsidered

## 8. Manual override policy

Manual overrides must be human-authored, explicitly documented, and time-bounded.
They may guide handling around a packet or incident, but they do not authorize bypassing
deterministic hard gates or silently loosening promotion requirements.

## 9. Kill switch policy

A designated human operator must retain immediate authority to halt shadow/pre-live
progression whenever safety, data integrity, or operational control is in doubt.
Kill-switch authority overrides AI suggestions and routine review cadence.

## 10. Deployment and change review checklist

- confirm baseline verification and data-contract validation still pass
- confirm replay validation and weekly review are current
- confirm any runtime, risk, simulator, or broker-related code changes were separately reviewed
- confirm rollback and ownership are documented before any live-facing phase change

## 11. AI-assisted review procedure

AI review can summarize packets, compare artifacts, and draft incident notes, but it is
advisory only. AI review is advisory. Deterministic gates and human kill-switch authority
take precedence.

## 12. Escalation matrix

- P0 or P1: immediate human escalation
- repeated P2: escalate within the same review cycle
- P3: log and resolve in normal maintenance

See `incident_response_v1.md` for the formal level definitions.

## 13. What not to do

- do not treat `READY_FOR_SMALL_LIVE` as auto-deployment permission
- do not bypass deterministic gates because AI or a human narrative looks optimistic
- do not ignore missing required packet files
- do not store secrets or credentials in repo artifacts
- do not loosen promotion standards just to pass the current sample
- do not start live or broker-connected behavior from this runbook step
