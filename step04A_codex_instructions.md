# Step 04A Codex Instructions — Canonical Simulator Preparation

You are working in the local `leadlag` repo after Step 03. The user wants to progress toward live operation and maintenance. This step prepares the canonical simulator audit layer. Do not implement major simulator behavior changes yet.

## Objective
Implement a simulator contract and golden-day audit harness that makes the current backtest/shadow simulator behavior inspectable and deterministic.

This is Step 04A. Step 04B will later strengthen cost/slippage/fill/PnL behavior.

## Hard constraints
Do not change:

- PCA SUB signal computation
- strategy selection logic
- risk gates
- weekly promotion rules
- corrected bundle data values
- data contract policy
- CLI behavior that existing tests depend on, except additive subcommands/options

Keep changes additive wherever possible.

## Expected files to add or update
Preferred additions:

```text
configs/simulator/canonical_simulator_v1.yaml
docs/canonical_simulator_v1.md
docs/golden_day_audit.md
src/leadlag/simulator_audit.py
scripts/audit_simulator_golden_days.py
tests/test_simulator_audit.py
```

If the repo structure suggests better paths, choose consistent paths and explain the change in the final report.

## Implementation requirements

### 1. Create simulator contract config
Create `configs/simulator/canonical_simulator_v1.yaml` describing the current canonical simulator assumptions.

Include at least:

```yaml
version: canonical_simulator_v1
mode_scope:
  - backtest
  - historical_shadow
  - broker_dry_run_comparison
price_sources:
  predictor_returns: returns_cc.csv
  target_returns: returns_oc_jp.csv
  adjusted_open_prices: open_prices_adj.csv
  adjusted_close_prices: close_prices_adj.csv
calendar:
  sample_filter: table1_exact_match
  target_core_count: 2590
  target_xlc_count: 1758
  target_xlre_count: 2409
execution_model:
  current_behavior: describe_current_shadow_fill_assumption_here
  cost_model: describe_current_cost_assumption_here
  slippage_model: current_or_none
outputs:
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
audit:
  min_golden_days: 5
  deterministic_rerun_required: true
```

Use actual current behavior from the repo. Do not invent behavior; inspect the code and document what exists.

### 2. Create documentation
Create `docs/canonical_simulator_v1.md` explaining:

- why the canonical simulator exists
- what it is the truth source for
- what inputs it consumes
- how signals become orders
- how orders become fills
- how fills become positions
- how positions become PnL
- what is intentionally not modeled yet
- how it differs from broker paper trading or live trading

Create `docs/golden_day_audit.md` explaining:

- what golden days are
- how they are selected
- how to run the audit
- what files are produced
- how deterministic reruns are checked
- what must be reviewed by a human

### 3. Implement golden-day selection
Implement a function in `src/leadlag/simulator_audit.py` that selects deterministic golden days from the available corrected bundle / sample-filter window.

Suggested logic:

1. Resolve the corrected bundle from config.
2. Resolve the exact-match sample filter date range if the repo already exposes this.
3. Prefer the most recent 20 valid trade dates as candidate pool.
4. Run historical shadow or read batch summary to identify examples.
5. Select at least 5 days:
   - latest valid date
   - one earlier normal GO day
   - one day with non-zero alerts if available
   - one day with scaling/cap alert if available
   - one date near calendar edge/holiday if available
6. If categories are unavailable, select 5 evenly spaced valid dates in the most recent 60 valid trade dates.

The function should be deterministic.

### 4. Implement audit runner
Implement `scripts/audit_simulator_golden_days.py`.

Suggested CLI:

```bash
python scripts/audit_simulator_golden_days.py \
  --config configs/profiles/shadow_corrected_local.yaml \
  --simulator-contract configs/simulator/canonical_simulator_v1.yaml \
  --output-dir artifacts/simulator_audit/canonical_v1 \
  --refresh
```

The script should:

- select or load golden days
- run one historical shadow packet per golden day using the existing runner path
- write a machine-readable audit summary
- write a human-readable markdown summary
- write per-day extracted summaries, including:
  - trade_date
  - asof_us_date
  - status
  - selected names count
  - gross exposure
  - expected cost bps
  - shadow net return
  - alert count
  - triggered gates count
  - packet path
- write a deterministic rerun hash or fingerprint for relevant outputs

Recommended outputs:

```text
artifacts/simulator_audit/canonical_v1/
  golden_days.csv
  audit_summary.csv
  audit_summary.json
  audit_summary.md
  fingerprints.json
  packets/<trade_date>/...
```

### 5. Deterministic rerun check
The audit script should support a deterministic rerun check.

Simplest acceptable implementation:

- Run once into a temporary or alternate directory.
- Extract stable fields from generated packets.
- Hash stable fields only. Exclude timestamps, absolute paths, generated_at, run_id if they are intentionally different.
- Compare fingerprints.

If deterministic rerun is too difficult due to existing volatile output fields, document the volatile fields and implement stable-field comparison instead.

### 6. Tests
Add lightweight tests in `tests/test_simulator_audit.py`.

Test at least:

- golden-day selection returns deterministic dates for a synthetic or tiny fixture
- fingerprinting ignores volatile timestamp/path fields
- audit summary schema contains required columns

Do not require a full real corrected bundle for unit tests unless existing test infrastructure already does so reliably.

### 7. Run commands
Run:

```bash
python -m compileall src/leadlag/simulator_audit.py scripts/audit_simulator_golden_days.py tests/test_simulator_audit.py
python -m pytest tests/test_simulator_audit.py -q
python scripts/audit_simulator_golden_days.py --config configs/profiles/shadow_corrected_local.yaml --simulator-contract configs/simulator/canonical_simulator_v1.yaml --output-dir artifacts/simulator_audit/canonical_v1 --refresh
python -m pytest -q
python scripts/verify_baseline.py
```

If paths differ on Windows, use the local `.venv` Python path consistently.

### 8. Final report to user
Report:

1. Summary
2. Files changed
3. Commands executed
4. Selected golden days
5. Audit outputs written
6. Deterministic rerun result
7. Acceptance checklist
8. Follow-up notes / blockers

Explicitly state whether strategy logic, risk gates, promotion rules, and bundle schema were unchanged.
