# Simulation Reconciliation

- trade_date: `2025-11-28`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `0.0014608559`
- canonical_net_return: `0.0014623168`
- net_return_diff_bps: `0.014609`
- legacy_gross_exposure: `0.000000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0015014638182486`
- canonical_cost_return: `-0.0015029653`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.0296 bps; cost return diff: -0.0150 bps.
