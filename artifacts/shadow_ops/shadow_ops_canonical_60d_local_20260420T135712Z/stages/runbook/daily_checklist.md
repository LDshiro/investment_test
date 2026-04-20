# Daily Checklist

## Pre-Open Checklist

1. Confirm the latest corrected-bundle update completed and the expected trade date is available.
2. Read summary.md, run.json, risk_report.json, and alerts.json before JP pre-open.
3. Verify run_status is GO or WARN before using the packet as a shadow reference.
4. If canonical sidecars are enabled, inspect sim_reconciliation.json for unexpected drift.
5. Record GO/WARN/STOP action and any escalation notes for the day.

## Post-Close Checklist

1. Confirm the packet directory contains the required daily packet files.
2. Check pnl.csv, fills_shadow.csv, and positions.csv for unexpected concentration or missing rows.
3. Compare shadow behavior against any canonical sidecars or replay expectations when enabled.
4. Escalate STOP or unresolved WARN clusters according to the incident policy.
5. Preserve links to the packet directory in the daily log.

## Required Daily Packet Files

- `summary.md`
- `run.json`
- `signals.csv`
- `orders_shadow.csv`
- `fills_shadow.csv`
- `positions.csv`
- `pnl.csv`
- `risk_report.json`
- `alerts.json`

## Canonical Sidecars When Enabled

- `canonical_orders.csv`
- `canonical_fills.csv`
- `canonical_positions.csv`
- `canonical_pnl.csv`
- `canonical_simulation_result.json`
- `sim_reconciliation.csv`
- `sim_reconciliation.json`
- `sim_reconciliation.md`
