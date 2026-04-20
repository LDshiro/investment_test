# Shadow Ops Operator Digest

- ops run id: `shadow_ops_canonical_60d_local_20260420T140416Z`
- generated_at: `2026-04-20T14:04:16.420835+00:00`
- profile used: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\ops\shadow_ops_canonical_60d_local.yaml`
- mode: `shadow_only`
- variant: `canonical`
- overall_status: `FAILED`

## Stage Status

- `validate_data_contract`: `SUCCESS`
- `run_batch`: `SUCCESS`
- `validate_shadow_replay`: `SUCCESS`
- `weekly_review`: `FAILED`
- `weekly_gates`: `SKIPPED`
- `render_runbook`: `SKIPPED`

## Batch Summary

- total_days: `60`
- completed_days: `60`
- failed_days: `0`
- GO/WARN/STOP counts: `{'GO': 60}`

## Weekly And Promotion

- latest weekly status: `None`
- promotion status: `None`
- main promotion failed checks: `[]`

## Canonical Reconciliation

- max_abs_net_return_diff_bps: `0.14207436593098935`
- max_abs_gross_return_diff_bps: `0.12721656751299437`
- max_abs_cost_return_diff_bps: `0.015095336523000998`

## Artifact Paths

- ops_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z`
- logs_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z\logs`
- data_contract_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z\stages\data_contract`
- batch_stage_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z\stages\batch`
- batch_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\runs\shadow_corrected_canonical_batch_60d_local_batch_2025-08-27_2025-11-28_20260420T140422Z`
- replay_validation_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z\stages\replay_validation`
- weekly_review_dir: ``
- weekly_gates_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z\stages\weekly_gates`
- runbook_dir: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_canonical_60d_local_20260420T140416Z\stages\runbook`

- human action required: `yes`
- recommended next action: Investigate the failed stage, preserve the artifacts, and rerun shadow-ops after review.
