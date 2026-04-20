# Baseline Freeze

`baseline_shadow_stack_v1` is the reproducibility anchor for the current shadow/live stack. It captures the repo state we are willing to compare future changes against without changing strategy math, risk gates, promotion rules, or corrected-bundle schema.

## Why it exists

Later steps in this repo will evolve reporting, operations, and production wiring. Without a frozen baseline, it becomes hard to answer basic questions such as:

- did performance move because the strategy changed or because the environment changed?
- did a config or data file drift?
- are new operational outputs still compatible with the known-good stack?

The baseline freeze solves that by recording the current configs, corrected bundle hashes, environment details, and a small set of reference command results under one named artifact directory.

## What is included

- canonical baseline identifiers
  - name: `baseline_shadow_stack_v1`
  - branch label for documentation: `ops/step01-baseline-freeze`
  - tag label for documentation: `baseline-shadow-stack-v1`
- environment metadata for the generated baseline
- git metadata when available, or a clean `git unavailable` record when not
- SHA256 hashes for canonical config files
- SHA256 hashes for corrected-bundle files used by the stack
- frozen outputs for these reference flows
  - `pytest`
  - corrected-bundle inspection
  - one historical shadow run
  - one batch replay
  - weekly review
  - weekly gates
- a manifest, markdown summary, and SHA256 manifest for everything written under the baseline artifact root

## What is intentionally excluded

- any retuning of strategy parameters
- changes to PCA math, portfolio construction, or signal generation
- changes to hard gates or weekly promotion logic
- corrected-bundle schema changes
- cleanup or deletion of pre-existing run directories

This step is about freezing the current baseline, not improving it.

## Canonical and auxiliary profiles

Canonical profiles frozen by the baseline:

- `configs/profiles/backtest_corrected_local.yaml`
- `configs/profiles/shadow_corrected_local.yaml`
- `configs/profiles/shadow_corrected_batch_local.yaml`
- `configs/profiles/shadow_corrected_batch_20d_local.yaml`
- `configs/review/weekly_rules_shadow_default.yaml`

Auxiliary `_mntdata` variants are included in the manifest as non-canonical references.

One important nuance: `backtest_corrected_local.yaml` points at `/mnt/data/...`, which is not portable to this local workspace. The baseline still hashes that canonical file, but the reference `inspect-bundle` command is executed with `configs/profiles/backtest_corrected.yaml` and the substitution is recorded in the manifest and command log.

## How to regenerate

From the repo root:

```bash
python scripts/freeze_baseline.py
```

The script will:

1. create `.venv` if needed
2. install `-e .[dev]` into that venv when needed
3. run the reference commands inside the venv
4. write baseline artifacts to `artifacts/baseline_shadow_stack_v1/`

To force a fresh reference-command rerun:

```bash
python scripts/freeze_baseline.py --refresh
```

To verify the generated baseline:

```bash
python scripts/verify_baseline.py
```

## How later steps should use it

- treat `artifacts/baseline_shadow_stack_v1/` as the frozen comparison target
- compare future config/data hashes against the baseline before attributing behavior changes to code edits
- compare later shadow/batch/weekly outputs against the reference artifacts when changing operational code paths
- if a future step intentionally creates a new baseline, do it under a new baseline name rather than rewriting this one

## Git branch and tag labels

The intended labels for this baseline are:

- branch: `ops/step01-baseline-freeze`
- tag: `baseline-shadow-stack-v1`

The freeze scripts only record these labels. They do not create or force git branches or tags, and they explicitly handle the case where the workspace is not a git clone.
