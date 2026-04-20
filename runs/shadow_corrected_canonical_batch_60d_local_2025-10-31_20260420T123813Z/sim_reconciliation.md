# Simulation Reconciliation

- trade_date: `2025-10-31`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0034318574`
- canonical_net_return: `-0.0034352892`
- net_return_diff_bps: `-0.034319`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014965662073496`
- canonical_cost_return: `-0.0014980628`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0194 bps; cost return diff: -0.0150 bps.
