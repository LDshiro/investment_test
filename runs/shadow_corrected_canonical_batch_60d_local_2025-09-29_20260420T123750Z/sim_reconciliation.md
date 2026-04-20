# Simulation Reconciliation

- trade_date: `2025-09-29`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0114590183`
- canonical_net_return: `-0.0114704773`
- net_return_diff_bps: `-0.114590`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014885310112161`
- canonical_cost_return: `-0.0014900195`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0997 bps; cost return diff: -0.0149 bps.
