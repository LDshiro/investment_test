# Simulation Reconciliation

- trade_date: `2025-08-29`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0018999961`
- canonical_net_return: `-0.0019018961`
- net_return_diff_bps: `-0.019000`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014980996019612`
- canonical_cost_return: `-0.0014995977`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0040 bps; cost return diff: -0.0150 bps.
