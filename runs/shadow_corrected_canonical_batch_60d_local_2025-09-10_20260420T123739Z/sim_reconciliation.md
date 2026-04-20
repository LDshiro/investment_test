# Simulation Reconciliation

- trade_date: `2025-09-10`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0010777147`
- canonical_net_return: `-0.0010787924`
- net_return_diff_bps: `-0.010777`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014989227065468`
- canonical_cost_return: `-0.0015004216`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.0042 bps; cost return diff: -0.0150 bps.
