# Simulation Reconciliation

- trade_date: `2025-09-11`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0033809936`
- canonical_net_return: `-0.0033843746`
- net_return_diff_bps: `-0.033810`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.001496617121998`
- canonical_cost_return: `-0.0014981137`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0188 bps; cost return diff: -0.0150 bps.
