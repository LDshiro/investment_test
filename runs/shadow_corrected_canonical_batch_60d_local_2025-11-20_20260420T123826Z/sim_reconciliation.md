# Simulation Reconciliation

- trade_date: `2025-11-20`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0056703295`
- canonical_net_return: `-0.0056759999`
- net_return_diff_bps: `-0.056703`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014943254944697`
- canonical_cost_return: `-0.0014958198`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0418 bps; cost return diff: -0.0149 bps.
