# Simulation Reconciliation

- trade_date: `2025-09-30`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0050916725`
- canonical_net_return: `-0.0050967642`
- net_return_diff_bps: `-0.050917`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014949047306958`
- canonical_cost_return: `-0.0014963996`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0360 bps; cost return diff: -0.0149 bps.
