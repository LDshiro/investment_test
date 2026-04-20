# Step 03 Codex Instructions — Implement Data Contract Freeze

You are working in the local repository for the lead-lag shadow trading stack.

The user has completed Step 01 baseline freeze and Step 02 environment reproducibility. Your task is Step 03: **Data Contract Freeze**.

## Primary objective

Implement a machine-verifiable data contract for the corrected Yahoo bundle used by the research, backtest, historical shadow replay, weekly review, and future live migration.

Do **not** change strategy logic, PCA signal logic, risk gate behavior, weekly promotion logic, or the corrected bundle values.

This step is about schema, validation, documentation, hashes, and reproducible data interpretation.

---

## Non-negotiable constraints

1. Do not modify trading logic.
2. Do not modify PCA SUB calculations.
3. Do not modify risk gate thresholds or weekly promotion rules.
4. Do not modify corrected bundle data values.
5. Do not recalculate or overwrite `returns_cc.csv` from prices.
6. Preserve existing tests and baseline verification.
7. Keep the implementation local and deterministic.
8. Avoid network access.

---

## Context

The corrected bundle is expected to contain at least:

```text
returns_cc.csv
returns_oc_jp.csv
open_prices_adj.csv
close_prices_adj.csv
common_dates_core.csv
common_dates_full.csv
ff3_japan_daily.csv
mom_japan_daily.csv
carhart4_japan_daily.csv
```

Optional files may later include:

```text
patch_table.csv
bundle_manifest.json
data_hashes.json
```

Important interpretation:

- `returns_cc.csv` is the canonical predictor return file.
- It may include manually corrected Japanese ETF distribution-drop events.
- Therefore, do not recompute or overwrite it from `close_prices_adj.csv`.
- `returns_oc_jp.csv` is the canonical Japanese open-to-close realized return file.
- `returns_oc_jp.csv` should reconcile with `close_prices_adj.csv / open_prices_adj.csv - 1`.
- adjusted price files are for QC, plotting, and audit.
- common dates are sample construction inputs, not a universal filter for every calculation.

---

## Files to add or update

Add or update at least the following:

```text
configs/data_contracts/corrected_bundle_v1.yaml
docs/data_contract_corrected_bundle_v1.md
src/leadlag/data_contract.py
scripts/validate_data_contract.py
tests/test_data_contract.py
README.md
```

You may adjust paths if the repository uses a slightly different layout, but keep the contract name:

```text
corrected_bundle_v1
```

---

## 1. Add data contract config

Create:

```text
configs/data_contracts/corrected_bundle_v1.yaml
```

It should define:

```yaml
contract_name: corrected_bundle_v1
contract_version: 1.0.0
bundle_type: yahoo_corrected_research_bundle
required_files:
  - returns_cc.csv
  - returns_oc_jp.csv
  - open_prices_adj.csv
  - close_prices_adj.csv
  - common_dates_core.csv
  - common_dates_full.csv
  - ff3_japan_daily.csv
  - mom_japan_daily.csv
  - carhart4_japan_daily.csv
optional_files:
  - patch_table.csv
  - bundle_manifest.json
  - data_hashes.json
```

Also include expected universes:

US tickers:

```text
XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, XLC, XLRE
```

US core tickers:

```text
XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY
```

JP tickers:

```text
1617.T, 1618.T, 1619.T, 1620.T, 1621.T, 1622.T, 1623.T, 1624.T, 1625.T, 1626.T, 1627.T, 1628.T, 1629.T, 1630.T, 1631.T, 1632.T, 1633.T
```

Expected factor columns:

For FF3:

```text
MKT, SMB, HML, RF
```

For MOM:

```text
MOM
```

For Carhart4:

```text
MKT, SMB, HML, MOM, RF
```

If the current implementation uses column names such as `Mkt-RF` or `WML`, support aliases in the contract and validator. Do not force a destructive rename.

---

## 2. Implement `src/leadlag/data_contract.py`

Implement a small validation module with a clear API. Suggested structure:

```python
@dataclass
class DataContractIssue:
    severity: str  # ERROR, WARN, INFO
    code: str
    message: str
    details: dict[str, Any] | None = None

@dataclass
class DataContractResult:
    passed: bool
    issues: list[DataContractIssue]
    summaries: dict[str, Any]
```

Core functions:

```python
load_contract(path: Path) -> dict[str, Any]
validate_corrected_bundle(bundle_dir: Path, contract_path: Path) -> DataContractResult
write_validation_outputs(result: DataContractResult, output_dir: Path) -> None
```

Validation should check at least:

### Required file checks

- Every required file exists.
- Every required CSV can be read.
- Empty files are ERROR.

### Date checks

For every CSV with a Date column or date index:

- dates parse successfully
- dates are unique
- dates are monotonic increasing
- no weekend dates in price / return files, unless explicitly allowed

### Column checks

- `returns_cc.csv` contains US 11 + JP 17 tickers.
- `returns_oc_jp.csv` contains JP 17 tickers.
- adjusted price files contain US 11 + JP 17 tickers.
- `ff3_japan_daily.csv` contains required FF3 columns or accepted aliases.
- `mom_japan_daily.csv` contains required MOM column or accepted aliases.
- `carhart4_japan_daily.csv` contains required Carhart4 columns or accepted aliases.

### Returns OC reconciliation

Check:

```python
returns_oc_jp ~= close_prices_adj[jp] / open_prices_adj[jp] - 1
```

Use a tolerance such as `1e-10` or configurable tolerance from YAML.

This is an ERROR if exceeded.

### Returns CC policy

Do not treat mismatch between `returns_cc.csv` and `close_prices_adj.pct_change()` as an ERROR.

Instead:

- compute a diagnostic count of large differences
- emit WARN if differences exist
- explain that this may reflect approved manual corrections

### Common dates checks

Validate that:

- `common_dates_core.csv` dates are a subset of `returns_cc.csv` date index
- `common_dates_full.csv` dates are a subset of `returns_cc.csv` date index
- For every date in `common_dates_core`, US core 9 + JP17 are non-null in `returns_cc.csv`
- For every date in `common_dates_full`, US 11 + JP17 are non-null in `returns_cc.csv`

If the exact complete-case equality is already known and easy to verify, add it. If equality is too brittle, at least ensure subset + non-null complete-case.

### Patch table validation if present

If `patch_table.csv` exists, validate expected columns:

```text
ticker,date,field,before,after,reason,patch_id,status
```

Accepted status values:

```text
approved,pending,rejected
```

Emit ERROR if pending or rejected patches are included in an active bundle unless the contract allows them.

If `patch_table.csv` is missing, emit WARN, not ERROR.

### Hash manifest

Generate SHA-256 hashes for all bundle files and write them to output.

---

## 3. Add CLI script

Create:

```text
scripts/validate_data_contract.py
```

It should support:

```bash
python scripts/validate_data_contract.py \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

If possible, also integrate into the existing CLI:

```bash
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

If CLI integration requires too much invasive change, keep the standalone script and document it.

---

## 4. Output files

The validator should write:

```text
validation_report.md
validation_report.json
ticker_summary.csv
file_hashes.json
```

`validation_report.md` should include:

- contract name and version
- bundle path
- PASS / FAIL
- issue counts by severity
- ERROR section
- WARN section
- INFO section
- date range summary
- non-null count summary
- notes on canonical returns policy

---

## 5. Documentation

Create:

```text
docs/data_contract_corrected_bundle_v1.md
```

It should explain:

- purpose of the data contract
- required files
- optional files
- canonical interpretation of each file
- why `returns_cc.csv` is not recomputed from price files
- patch table policy
- severity levels
- how to run validation
- how to interpret validation outputs
- how this connects to backtest / shadow / live

Update README with a short section linking to this doc and showing the validation command.

---

## 6. Tests

Add tests in:

```text
tests/test_data_contract.py
```

Include tests for:

1. Missing required file produces ERROR and failed result.
2. Minimal valid synthetic bundle passes.
3. `returns_oc_jp` mismatch produces ERROR.
4. `returns_cc` mismatch versus price pct_change produces WARN, not ERROR.
5. Pending patch in `patch_table.csv` produces ERROR unless explicitly allowed.

Use small temporary synthetic data. Do not rely on large real data.

---

## 7. Commands to run

Run at least:

```bash
python scripts/validate_data_contract.py \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

If the actual bundle path differs, discover it from existing configs and use the correct path. Mention the path used in the final report.

Then run:

```bash
python -m pytest -q
python scripts/verify_baseline.py
```

If the repo requires the Step 02 bootstrap first, use the established bootstrap command from Step 02.

---

## 8. Acceptance checklist

Your final report should include this checklist:

```text
contract config added: pass/fail
contract docs added: pass/fail
validator script added: pass/fail
real corrected bundle validation: pass/fail
validation outputs written: pass/fail
pytest passes: pass/fail
baseline verification passes: pass/fail
trading logic unchanged: pass/fail
risk gates unchanged: pass/fail
promotion rules unchanged: pass/fail
```

---

## 9. Final response format

Return a concise report in this format:

```text
1. Summary
2. Files changed
3. Commands executed
4. Validation result
5. Acceptance checklist
6. Follow-up notes / blockers
```

If anything fails, do not hide it. Explain the exact failure and the minimal next action.
