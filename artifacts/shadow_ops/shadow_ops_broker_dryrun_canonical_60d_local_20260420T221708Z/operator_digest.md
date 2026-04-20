# Shadow Ops Operator Digest

- ops run id: `shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z`
- generated_at: `2026-04-20T22:17:08.290618+00:00`
- profile used: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\ops\shadow_ops_broker_dryrun_canonical_60d_local.yaml`
- mode: `shadow_only`
- variant: `canonical`
- overall_status: `SUCCESS`

## Stage Status

- `validate_data_contract`: `SUCCESS`
- `run_batch`: `SUCCESS`
- `validate_shadow_replay`: `SUCCESS`
- `weekly_review`: `SUCCESS`
- `weekly_gates`: `SUCCESS`
- `render_runbook`: `SUCCESS`
- `broker_dryrun`: `SUCCESS`

## Batch Summary

- total_days: `60`
- completed_days: `60`
- failed_days: `0`
- GO/WARN/STOP counts: `{'GO': 60}`

## Weekly And Promotion

- latest weekly status: `GO`
- promotion status: `HOLD_SHADOW`
- main promotion failed checks: `['non_negative_shadow_return', 'sufficient_go_weeks', 'limited_warn_weeks', 'adequate_universe_width', 'acceptable_hit_rate']`

## Canonical Reconciliation

- max_abs_net_return_diff_bps: `0.14207436593098935`
- max_abs_gross_return_diff_bps: `0.12721656751299437`
- max_abs_cost_return_diff_bps: `0.015095336523000998`

## Broker Dry-Run

- runtime_safety_status: `WARN`
- total_days: `60`
- completed_days: `60`
- failed_days: `0`
- intent_count_total: `300`
- ack_count_total: `300`
- reject_count_total: `0`

## Artifact Paths

- ops_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z`
- logs_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\logs`
- data_contract_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\data_contract`
- batch_stage_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\batch`
- batch_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\runs\shadow_corrected_canonical_batch_60d_local_batch_2025-08-27_2025-11-28_20260420T221715Z`
- replay_validation_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\replay_validation`
- weekly_review_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\weekly_review`
- weekly_gates_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\weekly_gates`
- runbook_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\runbook`
- broker_dryrun_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\broker_dryrun`

- human action required: `no`
- recommended next action: Continue shadow-only monitoring and gather more evidence before any promotion review.
