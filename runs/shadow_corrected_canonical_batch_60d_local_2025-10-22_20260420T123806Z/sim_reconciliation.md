# Simulation Reconciliation

- trade_date: `2025-10-22`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0018256892`
- canonical_net_return: `-0.0018275149`
- net_return_diff_bps: `-0.018257`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.001498173983261`
- canonical_cost_return: `-0.0014996722`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0033 bps; cost return diff: -0.0150 bps.
