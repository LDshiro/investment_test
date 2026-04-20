# Simulation Reconciliation

- trade_date: `2025-09-26`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0007940367`
- canonical_net_return: `-0.0007948307`
- net_return_diff_bps: `-0.007940`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014992066684591`
- canonical_cost_return: `-0.0015007059`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.0071 bps; cost return diff: -0.0150 bps.
