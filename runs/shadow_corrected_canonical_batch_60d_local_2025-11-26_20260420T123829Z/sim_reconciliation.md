# Simulation Reconciliation

- trade_date: `2025-11-26`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `0.0088607101`
- canonical_net_return: `0.0088695708`
- net_return_diff_bps: `0.088607`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0015088710797004`
- canonical_cost_return: `-0.0015103800`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.1037 bps; cost return diff: -0.0151 bps.
