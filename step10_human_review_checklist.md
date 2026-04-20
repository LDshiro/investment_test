# Step 10 Human Review Checklist

Use this checklist after Codex completes Step 10.

## 1. Safety posture

- [ ] Report says no live broker connection was added.
- [ ] Report says no live order submission path was added.
- [ ] Report says no real credentials were added.
- [ ] Report says shadow-only / dry-run-safe posture remains the default.

## 2. Files and docs

- [ ] `configs/security/runtime_security_policy_v1.yaml` exists.
- [ ] `configs/security/secrets_inventory_v1.yaml` exists.
- [ ] `configs/runtime/execution_host_local_v1.yaml` exists.
- [ ] `.env.example` exists and contains placeholders only.
- [ ] `.gitignore` ignores local secret files but does not ignore `.env.example`.
- [ ] Docs for secrets, host setup, and kill switch exist.

## 3. Runtime safety outputs

- [ ] `artifacts/runtime_safety/step10/runtime_safety_report.md` exists.
- [ ] `artifacts/runtime_safety/step10/runtime_safety_report.json` exists.
- [ ] `artifacts/runtime_safety/step10/redacted_environment_snapshot.json` exists.
- [ ] Safety report is PASS or, at worst, PASS-with-WARN for non-live shadow mode.
- [ ] Missing future broker secrets are not treated as current blockers.
- [ ] Any WARN items are understandable.

## 4. Secret redaction

- [ ] Reports do not print secret-looking raw values.
- [ ] Redaction utility tests pass.
- [ ] `.env.example` does not contain real values.
- [ ] No new committed file contains a real password, token, API key, or private key.

## 5. Commands

Confirm Codex ran:

- [ ] `python -m pytest -q`
- [ ] `python scripts/verify_baseline.py`
- [ ] data contract validation
- [ ] `python -m leadlag.cli runtime-safety-check ...`
- [ ] `python scripts/validate_runtime_safety.py ...`

## 6. Invariant preservation

- [ ] PCA / signal code unchanged.
- [ ] corrected bundle values unchanged.
- [ ] canonical simulator economics unchanged.
- [ ] daily hard gates unchanged.
- [ ] weekly gate / promotion thresholds unchanged.
- [ ] broker selection / null dry-run safety not weakened.

## 7. Decision

- [ ] Step 10 can be accepted.
- [ ] Any blocker is documented clearly before moving to Step 11.

