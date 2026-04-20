# Simulation Reconciliation

- trade_date: `2025-10-02`
- status: `PASS`
- within_tolerance: `True`
- tolerance_net_return_bps: `1.0`

## Summary

- legacy_net_return: `-0.0142074366`
- canonical_net_return: `-0.0142216440`
- net_return_diff_bps: `-0.142074`
- legacy_gross_exposure: `0.750000`
- canonical_gross_exposure: `0.750000`
- legacy_cost_return: `-0.0014857798417501`
- canonical_cost_return: `-0.0014872656`

## Notes

- Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.
- Gross return diff: -0.1272 bps; cost return diff: -0.0149 bps.
