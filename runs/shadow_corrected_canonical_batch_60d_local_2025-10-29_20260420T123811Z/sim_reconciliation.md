# Simulation Reconciliation

- trade_date: `2025-10-29`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0025219372`
- canonical_net_return: `-0.0025244591`
- net_return_diff_bps: `-0.025219`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014974770383495`
- canonical_cost_return: `-0.0014989745`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.0102 bps; cost return diff: -0.0150 bps.
