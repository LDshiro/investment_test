# Simulation Reconciliation

- trade_date: `2025-10-21`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0076642288`
- canonical_net_return: `-0.0076718930`
- net_return_diff_bps: `-0.076642`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014923295993427`
- canonical_cost_return: `-0.0014938219`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0617 bps; cost return diff: -0.0149 bps.
