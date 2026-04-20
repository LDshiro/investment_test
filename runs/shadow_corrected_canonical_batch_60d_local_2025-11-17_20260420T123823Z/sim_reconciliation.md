# Simulation Reconciliation

- trade_date: `2025-11-17`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0006623687`
- canonical_net_return: `-0.0006630310`
- net_return_diff_bps: `-0.006624`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014993384683116`
- canonical_cost_return: `-0.0015008378`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.0084 bps; cost return diff: -0.0150 bps.
