# Step 01 — Codex Instructions: Freeze the Baseline

You are working inside the local repository for the lead-lag shadow/live stack.

Your goal is to implement **Step 01: baseline freeze**.
Do **not** change trading logic. Do **not** retune configs. Do **not** modify strategy behavior unless absolutely required to make reproducibility metadata work.

## High-level objective
Create a durable, reproducible baseline for the current repo, configs, data bundle, and reference outputs so that later steps can be compared against a frozen known-good state.

## Baseline identifiers
Use these exact identifiers:
- baseline name: `baseline_shadow_stack_v1`
- baseline branch: `ops/step01-baseline-freeze`
- baseline tag (document only; do not force git tag creation if repo is not a git clone): `baseline-shadow-stack-v1`
- artifact root: `artifacts/baseline_shadow_stack_v1/`

## Constraints
1. Do not change the strategy math.
2. Do not change risk gates or promotion rules.
3. Do not change bundle schema.
4. Do not remove existing files.
5. Keep changes minimal and surgical.
6. Prefer adding scripts / docs over rewriting existing modules.
7. If the repo is not a git clone, still record “git unavailable” cleanly in the baseline manifest.

## Existing repo areas you should inspect first
Inspect at least:
- `README.md`
- `pyproject.toml`
- `configs/`
- `src/leadlag/cli.py`
- `src/leadlag/runtime/`
- `src/leadlag/reporting/`
- `tests/`
- `data/normalized/corrected_bundle/`

## Canonical profiles to freeze
Freeze metadata for these profiles if they exist:
- `configs/profiles/backtest_corrected_local.yaml`
- `configs/profiles/shadow_corrected_local.yaml`
- `configs/profiles/shadow_corrected_batch_local.yaml`
- `configs/profiles/shadow_corrected_batch_20d_local.yaml`
- `configs/review/weekly_rules_shadow_default.yaml`

If local-path variants such as `_mntdata` also exist, include them in the manifest but mark local-path versions as canonical.

## Required deliverables
Add or generate the following:

### 1. Baseline documentation
Create:
- `docs/baseline_freeze.md`

It should explain:
- what the baseline freeze is,
- why it exists,
- what is included,
- what is intentionally excluded,
- how to regenerate it,
- how later steps should use it.

### 2. Baseline freeze script
Create a lightweight script, preferably:
- `scripts/freeze_baseline.py`

The script should:
- inspect environment metadata,
- collect git metadata if available,
- hash canonical config files,
- hash corrected bundle files,
- run or record reference commands,
- write outputs into `artifacts/baseline_shadow_stack_v1/`.

Design goal: idempotent and readable.

### 3. Optional baseline verification script
If practical, create:
- `scripts/verify_baseline.py`

It should validate that required baseline artifacts exist and that the manifest is internally consistent.

### 4. Baseline artifact tree
Generate:
- `artifacts/baseline_shadow_stack_v1/README.md`
- `artifacts/baseline_shadow_stack_v1/baseline_manifest.json`
- `artifacts/baseline_shadow_stack_v1/baseline_manifest.md`
- `artifacts/baseline_shadow_stack_v1/config_hashes.json`
- `artifacts/baseline_shadow_stack_v1/data_hashes.json`
- `artifacts/baseline_shadow_stack_v1/reference_commands.md`
- `artifacts/baseline_shadow_stack_v1/reference_results/` (directory)
- `artifacts/baseline_shadow_stack_v1/sha256_manifest.txt`

## Required content in the baseline manifest
The manifest must include at least:
- `baseline_name`
- `created_at_utc`
- `git` object with commit / branch / dirty state / tag target if available
- `environment` object with python version, platform, cwd, dependency snapshot location
- `canonical_profiles`
- `auxiliary_profiles`
- `config_hashes`
- `data_hashes`
- `reference_commands`
- `reference_artifacts`
- `acceptance_checks`
- `notes`

## Corrected bundle files that must be hashed
Hash these if present:
- `returns_cc.csv`
- `returns_oc_jp.csv`
- `close_prices_adj.csv`
- `open_prices_adj.csv`
- `common_dates_core.csv`
- `common_dates_full.csv`
- `ff3_japan_daily.csv`
- `mom_japan_daily.csv`
- `carhart4_japan_daily.csv`

## Reference commands to execute and freeze
Try to run these from the repo root. If exact command names differ, adapt carefully and record the final executed commands.

### A. Tests
Run:
- `pytest`

### B. Inspect corrected bundle
Run the existing bundle inspection command. If it exists as CLI, prefer that.
Expected outcome: successful inspection of corrected bundle and sample filter exact-match discovery.

### C. One historical shadow run
Run one historical shadow run using the local shadow profile.
Prefer the profile:
- `configs/profiles/shadow_corrected_local.yaml`

### D. One batch replay
Run one batch replay using:
- `configs/profiles/shadow_corrected_batch_local.yaml`
or, if more stable in this repo,
- `configs/profiles/shadow_corrected_batch_20d_local.yaml`

### E. Weekly review
Run the weekly review command on the batch output.

### F. Weekly gates
Run the weekly gates command using:
- `configs/review/weekly_rules_shadow_default.yaml`

Record the exact commands in `reference_commands.md` and place summary outputs or symlinks/copies under `reference_results/`.

## Acceptance criteria
Step 01 is complete only if all of the following are true:
- tests pass,
- corrected bundle inspection succeeds,
- one historical shadow run succeeds,
- one batch replay succeeds,
- weekly review succeeds,
- weekly gates succeeds,
- hashes are recorded,
- commands are recorded,
- artifacts are written under `artifacts/baseline_shadow_stack_v1/`.

## README update
Update `README.md` to include a compact section explaining:
- what “baseline freeze” means,
- how to regenerate it,
- where artifacts live,
- what commands to run.

Do not bloat the README. Add a clear, compact operational section.

## Implementation preferences
- Use standard library wherever possible.
- If you need hashing, use SHA256.
- Prefer JSON + Markdown for artifacts.
- Keep file paths portable.
- Avoid hard-coding `/mnt/data`.
- If a command produces output directories dynamically, capture their resolved locations in the manifest.

## What to inspect for dynamic paths
The batch / shadow / weekly flows may generate run directories dynamically. Your baseline manifest should record actual output paths produced by the executed commands.

## If the repo already contains similar artifacts
Do not delete them. Add the new baseline freeze artifacts under the dedicated baseline directory.

## If something is missing
If a required command does not exist or cannot run as documented:
1. inspect the CLI,
2. find the correct equivalent,
3. use it,
4. document the substitution explicitly in the manifest and summary.

## Final response format
When you are done, provide a concise execution report with these sections:
1. Summary
2. Files changed
3. Commands executed
4. Acceptance checklist
5. Baseline artifact directory
6. Follow-up notes / blockers

## Important guardrail
If you notice a temptation to tweak strategy logic “just to improve consistency,” do not do that in this step. Baseline freeze is a reproducibility step, not an improvement step.
