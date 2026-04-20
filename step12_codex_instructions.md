# Step 12 Codex Instructions — Shadow / Broker Dry-Run Reconciliation and Calibration

You are working in the `investment_test` repository. Implement Step 12 as an additive, non-live broker dry-run calibration layer.

The goal is to compare shadow order packets with broker-neutral order intents, NullBroker payloads, and NullBroker acknowledgements across the 60-business-day broker-dryrun shadow-ops outputs produced in Step 11.

Do not implement real broker connectivity. Do not add credential handling. Do not add paper or live order submission.

---

## 0. Preflight

Run these first and record the results in your final report.

```powershell
.venv\Scripts\python.exe scripts\verify_environment.py
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step12_preflight
.venv\Scripts\python.exe -m leadlag.cli runtime-safety-check --security-config configs/security/runtime_security_policy_v1.yaml --secrets-inventory configs/security/secrets_inventory_v1.yaml --host-config configs/runtime/execution_host_local_v1.yaml --output-dir artifacts/runtime_safety/step12_preflight
```

Runtime safety may be WARN only if ERROR=0 and warnings are known local-dev warnings. If ERROR>0, stop.

---

## 1. Hard constraints

Do not change:

```text
PCA SUB logic
signal computation
Table 1 sample filtering
corrected bundle values
canonical simulator economics
daily hard gate behavior
weekly gate / promotion thresholds
broker candidate scoring weights
NullBroker safety behavior
live / paper broker connection
credential handling
live order submission path
```

Step 12 must remain additive.

---

## 2. Add calibration config

Add:

```text
configs/broker_dryrun/broker_dryrun_calibration_v1.yaml
```

Suggested structure:

```yaml
calibration:
  id: broker_dryrun_calibration_v1
  description: "Reconcile shadow orders with broker-neutral dry-run intents and NullBroker acknowledgements."
  allowed_broker_ids:
    - null_broker_v1
  allowed_modes:
    - DRY_RUN
  require_null_broker_only: true
  require_no_rejections: true
  require_one_intent_per_shadow_order: true
  require_one_ack_per_intent: true
  require_deterministic_fingerprints: true
  require_open_leg_only_submission: true
  close_leg_policy: metadata_only
  forbid_sensitive_values_in_outputs: true
  max_missing_required_fields: 0
  max_reject_count: 0
  max_unmatched_shadow_orders: 0
  max_unmatched_intents: 0
  status_policy:
    fail_on:
      - real_broker_connection_detected
      - paper_or_live_mode_detected
      - credential_like_value_detected
      - reject_count_exceeds_threshold
      - unmatched_order_exceeds_threshold
      - missing_required_fields_exceeds_threshold
    warn_on:
      - optional_metadata_missing
      - source_artifact_layout_unrecognized_but_recoverable
```

Keep thresholds conservative.

---

## 3. Add docs

Add:

```text
docs/broker_dryrun_calibration_v1.md
```

Explain:

- purpose of calibration
- what is being reconciled
- why PASS does not mean live-ready
- legacy vs canonical source handling
- safety constraints
- expected artifacts
- known limitations with NullBroker

Make clear that this is still shadow/dry-run only.

---

## 4. Implement calibration module

Add one of the following, depending on the existing package layout:

```text
src/leadlag/broker/calibration.py
```

or

```text
src/leadlag/ops/broker_dryrun_calibration.py
```

Prefer `src/leadlag/broker/calibration.py` if the existing broker package is suitable.

Required functionality:

### Inputs

The tool should accept:

```text
--legacy-shadow-ops-dir <path>       optional
--canonical-shadow-ops-dir <path>    optional
--calibration-config <path>
--output-dir <path>
```

At least one of legacy/canonical dirs must be provided.

It should be able to read Step 11 outputs from either:

```text
artifacts/shadow_ops/<run_id>/...
```

or the repo's actual shadow-ops artifact layout.

Be tolerant of minor layout differences, but fail if broker dry-run outputs cannot be found.

### Reconciliation checks

For each source, compute at least:

```text
source_name
status
completed_days
failed_days
shadow_order_count_total
intent_count_total
ack_count_total
reject_count_total
unmatched_shadow_order_count
unmatched_intent_count
missing_required_field_count
duplicate_intent_fingerprint_count
paper_or_live_mode_detected
real_broker_connection_detected
credential_like_value_detected
open_leg_only_submission_passed
close_leg_metadata_only_passed
fingerprint_determinism_passed
```

For each day, output:

```text
source_name
trade_date
status
shadow_order_count
intent_count
ack_count
reject_count
missing_required_field_count
unmatched_shadow_order_count
unmatched_intent_count
issues
```

### Fingerprints

Create deterministic intent fingerprints from stable fields only. Suggested fields:

```text
trade_date
symbol
side
order_type
time_in_force
quantity_or_notional
strategy_id
run_id or packet_id
```

Do not include timestamps that change across reruns.

### Sensitive value scan

Use existing redaction / safety utilities if available. Otherwise implement a conservative scan over generated calibration outputs and relevant dry-run artifacts for key patterns such as:

```text
API_KEY
SECRET
TOKEN
PASSWORD
KABU
IBKR
```

Do not flag harmless config names too aggressively; flag credential-like assignments or raw values. If uncertain, WARN rather than FAIL, unless an actual credential-like value appears.

### Status

Status should be:

- `PASS` if all required checks pass
- `WARN` if only configured warnings occur
- `FAIL` if any fail condition occurs

---

## 5. Add script and CLI

Add:

```text
scripts/calibrate_broker_dryrun.py
```

Add CLI command:

```bash
python -m leadlag.cli broker-dryrun-calibration \
  --legacy-shadow-ops-dir <path> \
  --canonical-shadow-ops-dir <path> \
  --calibration-config configs/broker_dryrun/broker_dryrun_calibration_v1.yaml \
  --output-dir artifacts/broker_dryrun_calibration/step12
```

The script should call the same underlying module as the CLI.

---

## 6. Optional shadow-ops integration

If straightforward, add an optional calibration stage to shadow-ops config. Do not make it mandatory for existing configs unless defaults preserve current behavior.

Acceptable new configs:

```text
configs/ops/shadow_ops_broker_dryrun_calibrated_legacy_60d_local.yaml
configs/ops/shadow_ops_broker_dryrun_calibrated_canonical_60d_local.yaml
```

This is optional. The standalone calibration command is required.

---

## 7. Expected artifacts

Write:

```text
artifacts/broker_dryrun_calibration/step12/
  calibration_summary.md
  calibration_summary.json
  calibration_by_source.csv
  calibration_by_day.csv
  calibration_issues.csv
  legacy/
    calibration_summary.md
    calibration_by_day.csv
    calibration_issues.csv
  canonical/
    calibration_summary.md
    calibration_by_day.csv
    calibration_issues.csv
```

If one source is not provided, omit its subdirectory but report that it was not provided.

The markdown summary must include:

```text
overall status
legacy status
canonical status
intent/ack/reject totals
unmatched counts
missing field counts
safety guarantees
whether PASS means live-ready: no
human action required
```

---

## 8. Tests

Add focused tests. Suggested files:

```text
tests/test_broker_dryrun_calibration.py
tests/test_broker_dryrun_calibration_safety.py
```

Test at least:

- matching shadow orders / intents / acks -> PASS
- rejected ack -> FAIL
- missing required field -> FAIL
- PAPER/LIVE mode detected -> FAIL
- credential-like raw value in artifact -> FAIL or WARN according to policy
- duplicate fingerprints -> FAIL or WARN according to policy
- deterministic fingerprint function is stable

Run focused tests and full tests.

---

## 9. Execute on Step 11 outputs

Find the Step 11 shadow-ops broker dry-run output dirs. The reported names were:

```text
shadow_ops_broker_dryrun_legacy_60d_local_20260420T221652Z
shadow_ops_broker_dryrun_canonical_60d_local_20260420T221708Z
```

If exact dirs are not present, locate the latest matching legacy/canonical broker-dryrun shadow-ops artifact dirs.

Run:

```powershell
.venv\Scripts\python.exe -m leadlag.cli broker-dryrun-calibration --legacy-shadow-ops-dir <legacy_dir> --canonical-shadow-ops-dir <canonical_dir> --calibration-config configs/broker_dryrun/broker_dryrun_calibration_v1.yaml --output-dir artifacts/broker_dryrun_calibration/step12
```

Also run the script mirror:

```powershell
.venv\Scripts\python.exe scripts\calibrate_broker_dryrun.py --legacy-shadow-ops-dir <legacy_dir> --canonical-shadow-ops-dir <canonical_dir> --calibration-config configs/broker_dryrun/broker_dryrun_calibration_v1.yaml --output-dir artifacts/broker_dryrun_calibration/step12_script
```

---

## 10. Final verification

Run:

```powershell
.venv\Scripts\python.exe -m compileall src scripts tests
.venv\Scripts\python.exe -m pytest tests\test_broker_dryrun_calibration.py tests\test_broker_dryrun_calibration_safety.py -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step12
.venv\Scripts\python.exe -m leadlag.cli runtime-safety-check --security-config configs/security/runtime_security_policy_v1.yaml --secrets-inventory configs/security/secrets_inventory_v1.yaml --host-config configs/runtime/execution_host_local_v1.yaml --output-dir artifacts/runtime_safety/step12
```

---

## 11. Final report format

Return a concise report with:

```text
Summary
Files changed
Commands executed
Calibration artifact location
Legacy calibration summary
Canonical calibration summary
Safety guarantees
Acceptance checklist
Follow-up notes / blockers
```

Include these specific values if available:

```text
legacy status
canonical status
legacy completed_days / failed_days
canonical completed_days / failed_days
legacy shadow_order_count_total / intent_count_total / ack_count_total / reject_count_total
canonical shadow_order_count_total / intent_count_total / ack_count_total / reject_count_total
unmatched counts
missing field counts
runtime safety ERROR count
pytest count
```

If the calibration status is WARN or FAIL, explain why. Do not paper over any order mapping issue.
