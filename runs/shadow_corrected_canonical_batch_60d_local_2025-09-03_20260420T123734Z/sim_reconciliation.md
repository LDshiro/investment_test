# Simulation Reconciliation

- trade_date: `2025-09-03`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0074692021`
- canonical_net_return: `-0.0074766714`
- net_return_diff_bps: `-0.074692`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014925248211741`
- canonical_cost_return: `-0.0014940173`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0598 bps; cost return diff: -0.0149 bps.
