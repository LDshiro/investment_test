# Simulation Reconciliation

- trade_date: `2025-10-15`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `0.0063679811`
- canonical_net_return: `0.0063743491`
- net_return_diff_bps: `0.063680`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0015063758554528`
- canonical_cost_return: `-0.0015078822`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.0787 bps; cost return diff: -0.0151 bps.
