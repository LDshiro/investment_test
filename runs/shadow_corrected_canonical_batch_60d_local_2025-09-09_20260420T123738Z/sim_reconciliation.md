# Simulation Reconciliation

- trade_date: `2025-09-09`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0128456746`
- canonical_net_return: `-0.0128585203`
- net_return_diff_bps: `-0.128457`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014871429668665`
- canonical_cost_return: `-0.0014886301`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.1136 bps; cost return diff: -0.0149 bps.
