# Step 12 Human Review Checklist

Use this checklist after Codex finishes Step 12.

## 1. Safety boundary

Confirm the final report says all of the following.

```text
real broker connection added: no
paper broker connection added: no
live order submission path added: no
credential handling added: no
NullBroker only: yes
DRY_RUN only: yes
runtime safety ERROR count: 0
```

If any item is not true, do not approve Step 12.

## 2. Calibration run coverage

Confirm both legacy and canonical paths were calibrated, unless Codex explicitly explains why one was unavailable.

Expected:

```text
legacy calibrated: pass
canonical calibrated: pass
legacy completed_days: 60
canonical completed_days: 60
legacy reject_count_total: 0
canonical reject_count_total: 0
```

## 3. Core reconciliation checks

Confirm the report includes these checks.

- shadow order count equals broker intent count
- broker intent count equals ack count
- reject count is zero
- missing required fields count is zero
- duplicate intent fingerprint count is zero or explicitly justified
- intent fingerprints are deterministic
- open-leg orders are submitted; close-leg fields are metadata only
- no forbidden fields or sensitive env values are emitted

## 4. Output artifacts

Expected artifacts:

```text
artifacts/broker_dryrun_calibration/step12/calibration_summary.md
artifacts/broker_dryrun_calibration/step12/calibration_summary.json
artifacts/broker_dryrun_calibration/step12/calibration_by_source.csv
artifacts/broker_dryrun_calibration/step12/calibration_by_day.csv
artifacts/broker_dryrun_calibration/step12/calibration_issues.csv
```

## 5. Regression checks

Confirm these commands passed.

```text
python -m pytest -q
python scripts/verify_baseline.py
python -m leadlag.cli validate-data-contract ...
python -m leadlag.cli runtime-safety-check ...
```

Runtime safety may be WARN if the only warnings are known local-dev warnings such as missing `logs/`, missing `state/`, or dirty git state. ERROR must be zero.

## 6. Non-goals respected

Confirm Step 12 did not modify:

- PCA SUB logic
- corrected bundle values
- canonical simulator economics
- daily hard gates
- weekly gates / promotion thresholds
- broker scoring weights
- live/paper broker adapter behavior

## 7. Approval decision

Approve Step 12 only if:

```text
calibration status: PASS or explicitly acceptable WARN
safety boundary: pass
pytest: pass
baseline verification: pass
data contract validation: pass
runtime safety ERROR=0
no real broker/paper/live path added
```

If calibration is WARN because of documentation-only or known local-dev warnings, Step 12 may still be acceptable. If calibration is WARN/FAIL due to order mapping, missing orders, rejected orders, or inconsistent counts, do not approve until fixed.
