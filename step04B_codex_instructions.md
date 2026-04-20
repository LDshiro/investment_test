# Step 04B Codex Instructions: Canonical Simulator Implementation

You are working in the `investment_test` repo. The goal of this step is to implement an opt-in canonical simulator for historical shadow runs, while preserving the existing default behavior.

## Non-negotiable constraints

1. Do not change PCA SUB signal generation.
2. Do not change Table 1 sample filtering.
3. Do not change corrected bundle CSV values.
4. Do not change weekly gate or promotion rules.
5. Do not make canonical simulator the default path yet.
6. Do not add any live broker order submission.
7. Do not store secrets or credentials.
8. Keep the current default profiles working.

If you discover that Step 04A simulator-contract files are missing, do not improvise silently. Implement the minimum missing contract docs/interfaces as part of this step and mention that in the final report.

## Preflight

Run:

```bash
git status --short
python scripts/verify_environment.py
python scripts/verify_baseline.py
python -m pytest -q
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step04B_preflight
```

If any of these fail before your changes, stop and report the failure.

## Inspect existing files

Before coding, inspect at least:

```text
src/leadlag/runtime/corrected_shadow.py
src/leadlag/portfolio/costs.py
src/leadlag/portfolio/weights.py
src/leadlag/portfolio/risk_gates.py
src/leadlag/config/models.py
src/leadlag/config/loader.py
src/leadlag/cli.py
configs/profiles/shadow_corrected_local.yaml
configs/profiles/shadow_corrected_batch_local.yaml
configs/cost/
configs/risk/
docs/
tests/
```

Also inspect any Step 04A files, if present, such as simulator contract docs, golden-day fixtures, or audit outputs. Reuse them rather than duplicating concepts.

## Implementation plan

### 1. Add canonical simulator data models

Create or update:

```text
src/leadlag/sim/models.py
```

Add typed dataclasses or Pydantic models for:

```text
SimulationConfig
OrderIntent
SimulatedFill
PositionSnapshot
PnLBreakdown
SimulationResult
ReconciliationResult
```

Minimum fields:

```text
OrderIntent:
  trade_date
  ticker
  target_weight
  target_notional_jpy
  side
  entry_price
  exit_price
  expected_oc_return

SimulatedFill:
  trade_date
  ticker
  leg            # entry or exit
  side           # buy, sell, sell_short, buy_to_cover
  quantity
  price
  notional_jpy
  cost_bps
  cost_jpy

PositionSnapshot:
  trade_date
  ticker
  weight
  quantity
  entry_price
  exit_price
  gross_pnl_jpy
  cost_jpy
  net_pnl_jpy
  gross_return
  net_return_contribution

PnLBreakdown:
  trade_date
  nav_start_jpy
  nav_end_jpy
  gross_pnl_jpy
  cost_jpy
  borrow_cost_jpy
  net_pnl_jpy
  gross_return
  cost_return
  net_return
  gross_exposure
  net_exposure
  turnover_entry
  turnover_exit
  n_positions
```

Use simple, serializable types. Avoid objects that are hard to write to CSV/JSON.

### 2. Implement canonical formulas

Create or update:

```text
src/leadlag/sim/canonical.py
```

Implement a pure function such as:

```python
def simulate_intraday_open_close(
    *,
    trade_date: str,
    weights: pd.Series,
    open_prices: pd.Series,
    close_prices: pd.Series,
    nav_start_jpy: float,
    entry_cost_bps: float,
    exit_cost_bps: float,
    borrow_fee_bps_annual: float = 0.0,
    annualization_days: int = 252,
    allow_fractional_quantity: bool = True,
) -> SimulationResult:
    ...
```

Canonical formulas:

```text
return_oc_i       = close_i / open_i - 1
target_notional_i = nav_start * weight_i
quantity_i        = target_notional_i / open_i  # fractional in shadow mode
gross_pnl_i       = quantity_i * (close_i - open_i)
entry_cost_i      = abs(target_notional_i) * entry_cost_bps / 10000
exit_notional_i   = abs(quantity_i * close_i)
exit_cost_i       = exit_notional_i * exit_cost_bps / 10000
borrow_cost_i     = abs(target_notional_i) * (borrow_fee_bps_annual / annualization_days) / 10000, if weight_i < 0
net_pnl_i         = gross_pnl_i - entry_cost_i - exit_cost_i - borrow_cost_i
net_return        = sum(net_pnl_i) / nav_start
nav_end           = nav_start + sum(net_pnl_i)
```

Important:

- Costs must be recorded separately, not embedded into fill prices.
- Use adjusted open/close prices from the corrected bundle.
- In shadow mode, fractional quantity is allowed by default.
- If `allow_fractional_quantity=False`, round quantities conservatively and record the rounding difference. Do not make this the default yet.
- Drop zero-weight names from orders/fills/positions, but record zero-trade results for STOP/no-trade days.
- Missing open/close prices for selected names should produce a clear error or STOP-compatible result. Do not silently fill missing values.

### 3. Add reconciliation helper

Create or update:

```text
src/leadlag/sim/reconciliation.py
```

Implement functions that compare legacy packet output and canonical output:

```text
legacy pnl.csv / fills_shadow.csv / positions.csv
canonical_pnl.csv / canonical_fills.csv / canonical_positions.csv
```

The reconciliation should output at least:

```text
legacy_net_return
canonical_net_return
net_return_diff
net_return_diff_bps
legacy_gross_exposure
canonical_gross_exposure
legacy_cost_bps_or_return, if available
canonical_cost_return
status
notes
```

Write:

```text
sim_reconciliation.csv
sim_reconciliation.json
sim_reconciliation.md
```

The markdown should be understandable to a human. It should say whether the difference is within tolerance and list the largest sources of difference.

### 4. Add opt-in config/profile

Add a simulator config. Prefer:

```text
configs/sim/canonical_shadow_v1.yaml
```

Suggested content:

```yaml
simulator:
  name: canonical_v1
  enabled: true
  use_for_shadow_packets: false
  write_canonical_artifacts: true
  write_reconciliation: true
  allow_fractional_quantity: true
  cost_application: separate_cash_cost
  entry_price: adjusted_open
  exit_price: adjusted_close
  reconciliation:
    tolerance_net_return_bps: 1.0
    fail_on_tolerance_breach: false
```

Then add a profile:

```text
configs/profiles/shadow_corrected_canonical_local.yaml
```

It should extend the existing `shadow_corrected_local.yaml` and the new simulator config.

Do not alter `configs/profiles/shadow_corrected_local.yaml` default behavior.

If `src/leadlag/config/models.py` rejects the new section, add a backward-compatible simulator model with safe defaults:

```yaml
simulator.enabled: false
simulator.use_for_shadow_packets: false
simulator.write_canonical_artifacts: false
```

### 5. Integrate with corrected shadow runtime as opt-in

Update:

```text
src/leadlag/runtime/corrected_shadow.py
```

Goal:

- Existing default shadow packet remains unchanged.
- If `cfg.simulator.enabled == true`, run canonical simulation after the existing weights/signals/risk gate step.
- Write canonical artifacts into the same daily packet directory or a clear subdirectory, e.g.:

```text
canonical_orders.csv
canonical_fills.csv
canonical_positions.csv
canonical_pnl.csv
canonical_simulation_result.json
sim_reconciliation.csv
sim_reconciliation.json
sim_reconciliation.md
```

STOP behavior:

- If hard gate says STOP, do not simulate trades.
- Still write `canonical_pnl.csv` with zero PnL and status STOP.
- Write reconciliation explaining no-trade status.

### 6. Add optional CLI helper if it fits cleanly

If the current CLI design makes it easy, add:

```bash
python -m leadlag.cli simulate-canonical --config configs/profiles/shadow_corrected_canonical_local.yaml
```

This is optional. The required path is:

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_canonical_local.yaml
```

### 7. Documentation

Create or update:

```text
docs/canonical_simulator_v1.md
README.md
```

Document:

- Why canonical simulator exists.
- How it differs from legacy shadow output.
- Formula for PnL and costs.
- Fractional quantity assumption.
- What files are written.
- How to run one-day canonical shadow.
- How to read reconciliation.
- Why it is opt-in for now.

### 8. Tests

Add tests such as:

```text
tests/test_canonical_simulator.py
tests/test_canonical_simulator_reconciliation.py
```

Minimum tests:

1. One long position, zero cost: net return equals OC return times weight.
2. One short position, zero cost: net return equals negative OC return times abs weight.
3. Entry/exit costs reduce net PnL by expected bps.
4. Borrow fee applies only to short positions.
5. Multiple positions aggregate correctly.
6. STOP/no-trade result writes zero-trade artifacts or result object.
7. Reconciliation detects a known return difference in bps.
8. Existing default profile still validates.
9. Canonical profile validates.

### 9. Commands to run after implementation

Run:

```bash
python -m compileall src scripts tests
python -m pytest -q
python scripts/verify_environment.py
python scripts/verify_baseline.py
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step04B
python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml
python -m leadlag.cli run --config configs/profiles/shadow_corrected_canonical_local.yaml
```

If a command fails, fix it unless the failure is unrelated and pre-existing. If a baseline hash fails because canonical artifacts changed default output, that is a bug: restore default behavior and keep canonical opt-in.

### 10. Expected final report format

Report back with:

```text
1. Summary
2. Files changed
3. Commands executed
4. Canonical one-day run location
5. Reconciliation summary
6. Acceptance checklist
7. Follow-up notes / blockers
```

In the reconciliation summary include:

```text
trade_date
legacy_net_return
canonical_net_return
net_return_diff_bps
status
notes
```

## Suggested acceptance checklist

```text
preflight passed: pass/fail
canonical simulator implemented: pass/fail
canonical profile added: pass/fail
default shadow profile unchanged: pass/fail
one-day canonical run succeeds: pass/fail
canonical artifacts written: pass/fail
reconciliation artifacts written: pass/fail
pytest passes: pass/fail
baseline verification passes: pass/fail
data contract validation passes: pass/fail
trading logic unchanged: pass/fail
risk gates unchanged: pass/fail
weekly gates unchanged: pass/fail
```
