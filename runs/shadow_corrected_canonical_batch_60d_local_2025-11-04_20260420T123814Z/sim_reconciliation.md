# Simulation Reconciliation

- trade_date: `2025-11-04`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0017145956`
- canonical_net_return: `-0.0017163102`
- net_return_diff_bps: `-0.017146`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014982851881258`
- canonical_cost_return: `-0.0014997835`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0022 bps; cost return diff: -0.0150 bps.
