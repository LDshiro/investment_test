# Runtime Safety Report

- status: `WARN`
- errors: `0`
- warnings: `3`
- infos: `0`

## Configs

- security_config: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\security\runtime_security_policy_v1.yaml` sha256=`ddbc497cee4f1185f192da70711c84c1ebd1e5c83c1bf461fd2d21116cb97745`
- secrets_inventory: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\security\secrets_inventory_v1.yaml` sha256=`e11cecbdeed3f1c0989e35ba3b1e3eb0413fe3497c6d180bcf8c17e77e759d81`
- host_config: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\runtime\execution_host_local_v1.yaml` sha256=`b0bb98476d6be0531cd0447d2130e3d3cf9cafa1c44ed37719285204e532c7d6`

## Host Checks

- timezone expected: `Asia/Tokyo`
- timezone detected: `東京 (標準時)`
- timezone match: `True`
- python version file exists: `True`
- python current version: `3.14.3`
- git dirty: `True`
- tracked secret files: `[]`

## Runtime Flags

- kill switch file exists: `False`
- trading disabled file exists: `False`

## Directory Checks

- `data/normalized/corrected_bundle` exists=`True` is_dir=`True`
- `runs` exists=`True` is_dir=`True`
- `artifacts` exists=`True` is_dir=`True`
- `logs` exists=`False` is_dir=`False`
- `state` exists=`False` is_dir=`False`

## Issues

- `WARN` `missing_required_directory`: Required directory is missing or not a directory: logs
- `WARN` `missing_required_directory`: Required directory is missing or not a directory: state
- `WARN` `git_dirty_state`: Git worktree is dirty.

## Output Paths

- runtime_safety_report_json: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\broker_dryrun\runtime_safety\runtime_safety_report.json`
- runtime_safety_report_md: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\broker_dryrun\runtime_safety\runtime_safety_report.md`
- redacted_environment_snapshot_json: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_ops\shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z\stages\broker_dryrun\runtime_safety\redacted_environment_snapshot.json`
