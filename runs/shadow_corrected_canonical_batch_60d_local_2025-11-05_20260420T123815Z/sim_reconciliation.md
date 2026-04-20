# Simulation Reconciliation

- trade_date: `2025-11-05`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0064943746`
- canonical_net_return: `-0.0065008689`
- net_return_diff_bps: `-0.064944`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014935006245749`
- canonical_cost_return: `-0.0014949941`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0500 bps; cost return diff: -0.0149 bps.
