# Step 05 Codex Instructions: Historical Shadow Continuous Validation

You are working in the local repository for the investment shadow-trading project.

Repository URL for context:

```text
https://github.com/LDshiro/investment_test
```

## Objective

Implement Step 05: historical shadow continuous validation.

The goal is to prove that the current shadow system can run continuously over a 60-trading-day window in both:

1. the default legacy shadow path, and
2. the opt-in canonical simulator sidecar path added in Step 04B.

You must add replay validation tooling that audits generated daily packets, summarizes failures / alerts / gates, and checks canonical reconciliation stability.

## Strict non-goals

Do not change:

- PCA SUB signal logic
- Table 1 sample filter logic
- corrected bundle values
- data contract semantics
- risk gate logic
- weekly gate or promotion rule logic
- default `shadow_corrected_local.yaml` behavior
- existing baseline artifacts except by creating new Step 05 artifacts

Canonical support must remain opt-in.

## Preflight

Before editing, inspect current status:

```bash
git status --short
python scripts/verify_environment.py
python scripts/verify_baseline.py
python -m pytest -q
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step05_preflight
```

If the project uses `.venv`, use the existing venv Python executable. On Windows this is usually:

```powershell
.venv\Scripts\python.exe
```

Continue only if preflight passes. If something unrelated is already dirty, record it in the final report and avoid touching it.

## Implementation tasks

### 1. Add 60-day batch profiles

Add a legacy 60-day replay profile:

```text
configs/profiles/shadow_corrected_batch_60d_local.yaml
```

It should be based on the existing batch local profile but use:

```yaml
batch:
  date_source: sample_filter
  end_date: 2025-11-28
  max_days: 60
  trade_dates: []
  skip_existing_packets: true
  stop_on_error: true
  write_batch_summary: true
```

Add a canonical 60-day replay profile:

```text
configs/profiles/shadow_corrected_canonical_batch_60d_local.yaml
```

It should behave like the 60-day legacy batch profile, but each per-day packet should use the opt-in canonical simulator sidecar path from Step 04B.

If the current config system supports inheritance, inherit from the existing local batch and canonical profiles. If not, duplicate minimally and document the reason.

Do not alter existing default profiles.

### 2. Add validation configs

Add:

```text
configs/validation/shadow_replay_v1.yaml
configs/validation/shadow_replay_canonical_v1.yaml
```

Suggested defaults:

```yaml
required_packet_files:
  - summary.md
  - run.json
  - signals.csv
  - orders_shadow.csv
  - fills_shadow.csv
  - positions.csv
  - pnl.csv
  - risk_report.json
  - alerts.json

optional_packet_files:
  - figure_signals.png
  - figure_equity_curve.png

allow_statuses:
  - GO
  - WARN
  - STOP

max_failed_days: 0
max_missing_required_files: 0
require_batch_summary: true
require_monotonic_trade_dates: true
require_unique_trade_dates: true
```

For canonical validation, additionally require:

```yaml
canonical_required_packet_files:
  - canonical_pnl.csv
  - canonical_simulation_result.json
  - sim_reconciliation.json

canonical_reconciliation:
  require_status_pass: true
  max_abs_net_return_diff_bps: 1.0
  max_abs_gross_return_diff_bps: 1.0
  max_abs_cost_return_diff_bps: 1.0
```

If Step 04B uses slightly different filenames, use the actual names and document them.

### 3. Implement replay validation module

Add a module such as:

```text
src/leadlag/ops/shadow_replay_validation.py
```

It should expose a function similar to:

```python
def validate_shadow_replay(
    batch_dir: Path,
    validation_config: Path | dict,
    output_dir: Path,
) -> ReplayValidationResult:
    ...
```

It should read:

- `batch_summary.csv`
- per-day packet directories referenced by the batch summary, if available
- `run.json`
- `risk_report.json`
- `alerts.json`
- `pnl.csv`
- canonical sidecars, if canonical validation is enabled

The validator should produce:

```text
replay_validation_report.md
replay_validation_report.json
daily_packet_audit.csv
status_counts.csv
alert_summary.csv
risk_gate_summary.csv
```

For canonical replay, also produce:

```text
canonical_reconciliation_summary.csv
```

The validator should return PASS / WARN / FAIL.

Minimum FAIL conditions:

- missing `batch_summary.csv`
- missing required packet file
- failed day count exceeds config
- duplicate trade dates when disallowed
- non-monotonic trade dates when disallowed
- invalid status outside allow list
- canonical reconciliation status not PASS when required
- canonical diff exceeds configured threshold

WARN conditions may include:

- STOP days, if not configured as hard fail
- WARN days
- non-empty alerts
- high expected costs
- high gross exposure

Keep the validator conservative but not overly opinionated. Step 06 will tune policy thresholds.

### 4. Add CLI command

Add a CLI subcommand such as:

```bash
python -m leadlag.cli validate-shadow-replay \
  --batch-dir runs/<batch_dir> \
  --validation-config configs/validation/shadow_replay_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_legacy_60d
```

and for canonical:

```bash
python -m leadlag.cli validate-shadow-replay \
  --batch-dir runs/<canonical_batch_dir> \
  --validation-config configs/validation/shadow_replay_canonical_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_canonical_60d
```

The command should exit non-zero on FAIL.

### 5. Add standalone script

Add:

```text
scripts/validate_shadow_replay.py
```

It should call the same implementation as the CLI command. This is useful for Codex / local maintenance scripts.

### 6. Add documentation

Add:

```text
docs/shadow_replay_validation.md
```

Explain:

- what historical shadow continuous validation is
- legacy vs canonical replay
- required packet files
- validation outputs
- how to interpret PASS / WARN / FAIL
- how this connects to weekly-review and weekly-gates
- what Step 05 does not prove yet

Update README only if necessary, with a short pointer to the new doc.

### 7. Add tests

Add tests such as:

```text
tests/test_shadow_replay_validation.py
```

Test at least:

- a minimal valid synthetic batch passes
- missing required packet file fails
- duplicate trade dates fail if disallowed
- canonical reconciliation diff exceeding threshold fails
- canonical reconciliation pass within threshold passes

Keep tests lightweight. Do not require the real corrected bundle in unit tests.

## Execution commands

After implementation, run:

```bash
python -m compileall src scripts tests
python -m pytest -q
python scripts/verify_baseline.py
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step05
```

Then run legacy 60-day replay:

```bash
python -m leadlag.cli run-batch \
  --config configs/profiles/shadow_corrected_batch_60d_local.yaml
```

Find the generated batch directory and run:

```bash
python -m leadlag.cli weekly-review \
  --batch-dir <legacy_batch_dir> \
  --output-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_review

python -m leadlag.cli weekly-gates \
  --review-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_default.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_gates

python -m leadlag.cli validate-shadow-replay \
  --batch-dir <legacy_batch_dir> \
  --validation-config configs/validation/shadow_replay_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_legacy_60d/replay_validation
```

Then run canonical 60-day replay:

```bash
python -m leadlag.cli run-batch \
  --config configs/profiles/shadow_corrected_canonical_batch_60d_local.yaml
```

Find the generated canonical batch directory and run:

```bash
python -m leadlag.cli weekly-review \
  --batch-dir <canonical_batch_dir> \
  --output-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_review

python -m leadlag.cli weekly-gates \
  --review-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_default.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_gates

python -m leadlag.cli validate-shadow-replay \
  --batch-dir <canonical_batch_dir> \
  --validation-config configs/validation/shadow_replay_canonical_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_canonical_60d/replay_validation
```

If canonical 60-day replay is too slow, do not silently reduce the scope. First run a 20-day canonical replay to debug, then run 60-day once working. The final acceptance target remains 60 days.

## Acceptance criteria

Step 05 is acceptable if:

- preflight passes
- legacy 60-day replay completes with failed days = 0
- canonical 60-day replay completes with failed days = 0
- replay validation passes for legacy
- replay validation passes for canonical
- weekly-review succeeds for both
- weekly-gates succeeds for both
- pytest passes
- baseline verification passes
- data contract validation passes
- no trading logic / PCA logic / risk gate / promotion rule changes are made
- generated artifacts are under `artifacts/shadow_replay_validation/`

## Final report format

Please report in this structure:

```text
Summary
<1-3 paragraphs>

Files changed
<list>

Commands executed
<list>

Legacy 60-day replay
batch_dir: <path>
completed_days: <n>
failed_days: <n>
GO/WARN/STOP counts: <...>
validation_status: <PASS/WARN/FAIL>
weekly_gates_latest_status: <...>

Canonical 60-day replay
batch_dir: <path>
completed_days: <n>
failed_days: <n>
GO/WARN/STOP counts: <...>
validation_status: <PASS/WARN/FAIL>
max_abs_net_return_diff_bps: <value>
max_abs_gross_return_diff_bps: <value>
max_abs_cost_return_diff_bps: <value>
weekly_gates_latest_status: <...>

Artifacts
<paths>

Acceptance checklist
preflight passed: pass/fail
legacy 60d replay: pass/fail
canonical 60d replay: pass/fail
legacy validation: pass/fail
canonical validation: pass/fail
weekly review/gates: pass/fail
pytest: pass/fail
baseline verification: pass/fail
data contract validation: pass/fail
trading logic unchanged: pass/fail
risk gates unchanged: pass/fail
promotion rules unchanged: pass/fail

Follow-up notes / blockers
<notes>
```

