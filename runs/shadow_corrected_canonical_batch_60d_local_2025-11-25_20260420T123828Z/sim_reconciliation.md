# Simulation Reconciliation

- trade_date: `2025-11-25`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0114582266`
- canonical_net_return: `-0.0114696848`
- net_return_diff_bps: `-0.114582`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014885318037099`
- canonical_cost_return: `-0.0014900203`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0997 bps; cost return diff: -0.0149 bps.
