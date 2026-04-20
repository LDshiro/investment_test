# Shadow Ops Profile v1

Step 08 adds a single orchestration command for shadow-only operations. The goal is
to run the existing safe workflow end to end without changing trading behavior.

## What `shadow-ops` does

`shadow-ops` loads a standalone operations profile and runs these stages in order:

1. data contract validation
2. historical shadow batch replay
3. shadow replay validation
4. weekly review
5. weekly gates
6. runbook rendering

It is an operations wrapper only. It does not modify PCA SUB logic, sample
filtering, corrected bundle values, simulator economics, daily hard gates, weekly
thresholds, promotion thresholds, or broker behavior.

## Why it is still shadow-only

The only allowed ops mode in Step 08 is `shadow_only`.

- `READY_FOR_SMALL_LIVE` is still only a review status
- it must not trigger live trading
- the operator digest is a review handoff artifact, not an automation trigger

## Profile schema

The profile lives under `configs/ops/` and is intentionally separate from
`AppConfig`.

Top-level shape:

```yaml
ops:
  name: shadow_ops_legacy_60d_local
  mode: shadow_only
  variant: legacy
  artifact_root: artifacts/shadow_ops
  stop_on_stage_failure: true
  overwrite_existing: false
  timestamp_outputs: true
  operator_digest: true

stages:
  validate_data_contract:
    enabled: true
    bundle_dir: data/normalized/corrected_bundle
    contract: configs/data_contracts/corrected_bundle_v1.yaml
  run_batch:
    enabled: true
    config: configs/profiles/shadow_corrected_batch_60d_local.yaml
  validate_shadow_replay:
    enabled: true
    config: configs/validation/shadow_replay_v1.yaml
  weekly_review:
    enabled: true
  weekly_gates:
    enabled: true
    rules_config: configs/review/weekly_rules_shadow_pre_live_v1.yaml
  render_runbook:
    enabled: true
    config: configs/ops/runbook_shadow_v1.yaml
```

Canonical mode swaps only the batch profile and replay-validation config.

## Output directory layout

Each run writes to:

```text
artifacts/shadow_ops/<ops_name>_<timestamp>/
```

Main files:

- `shadow_ops_summary.json`
- `operator_digest.md`
- `stage_status.csv`
- `stage_status.json`
- `paths.json`
- `logs/<stage>.stdout.txt`
- `logs/<stage>.stderr.txt`
- `stages/data_contract/`
- `stages/batch/`
- `stages/replay_validation/`
- `stages/weekly_review/`
- `stages/weekly_gates/`
- `stages/runbook/`

The batch packet tree is not duplicated. `paths.json` and the digest record the
actual external batch directory, and the batch stage only copies `batch_summary.*`
files for inspection.

When the underlying batch profile uses `skip_existing_packets: true`, the batch
stage also writes `batch_summary_for_downstream.csv` for internal use. This
normalizes `skipped_existing` rows from existing packet `run.json` metadata so
weekly review and weekly gates can evaluate the reused packets consistently.

## How to run legacy 60d ops

```bash
python -m leadlag.cli shadow-ops \
  --config configs/ops/shadow_ops_legacy_60d_local.yaml
```

## How to run canonical 60d ops

```bash
python -m leadlag.cli shadow-ops \
  --config configs/ops/shadow_ops_canonical_60d_local.yaml
```

The standalone script wrapper calls the same implementation:

```bash
python scripts/run_shadow_ops.py \
  --config configs/ops/shadow_ops_legacy_60d_local.yaml
```

## How to use `operator_digest.md`

`operator_digest.md` is designed to be pasted into AI review chat or a human review
thread. It contains:

- stage statuses
- batch total / completed / failed days
- GO / WARN / STOP counts
- latest weekly status
- promotion status
- promotion failed checks
- canonical reconciliation max diff bps when applicable
- artifact paths
- human action required yes/no
- recommended next action in review wording only

## What not to automate yet

- do not trigger live trading from `shadow-ops`
- do not auto-promote on `READY_FOR_SMALL_LIVE`
- do not bypass human review for `BLOCKED`, `WARN`, or `STOP`
- do not turn the digest into a capital-allocation signal
