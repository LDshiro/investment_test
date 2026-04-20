# Simulation Reconciliation

- trade_date: `2025-08-28`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `0.0092092984`
- canonical_net_return: `0.0092185077`
- net_return_diff_bps: `0.092093`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0015092200168717`
- canonical_cost_return: `-0.0015107292`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: 0.1072 bps; cost return diff: -0.0151 bps.
