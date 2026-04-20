# Simulation Reconciliation

- trade_date: `2025-09-25`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0024783411`
- canonical_net_return: `-0.0024808194`
- net_return_diff_bps: `-0.024783`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014975206780985`
- canonical_cost_return: `-0.0014990182`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0098 bps; cost return diff: -0.0150 bps.
