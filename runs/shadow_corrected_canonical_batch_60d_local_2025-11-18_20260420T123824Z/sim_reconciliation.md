# Simulation Reconciliation

- trade_date: `2025-11-18`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0090194310`
- canonical_net_return: `-0.0090284504`
- net_return_diff_bps: `-0.090194`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014909730405604`
- canonical_cost_return: `-0.0014924640`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0753 bps; cost return diff: -0.0149 bps.
