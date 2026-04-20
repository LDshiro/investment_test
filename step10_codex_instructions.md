# Step 10 Codex Instructions: Secrets, Safety, and Execution Host Preparation

You are working in the local repository for the lead-lag investment shadow/live-preparation stack.

Step 10 is a safety and environment-hardening step. Do not implement live broker connectivity. Do not add real credentials. Do not change trading behavior.

## 0. Read first

Before editing, inspect the current repository state:

```bash
git status --short
python scripts/verify_environment.py
python scripts/verify_baseline.py
python -m pytest -q
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step10_preflight
```

If any preflight check fails, stop and report the failure. Do not continue by changing strategy behavior.

## 1. Non-negotiable constraints

Do not modify:

- PCA SUB logic
- signal computation
- Table 1 sample filtering
- corrected bundle values
- canonical simulator economics
- daily hard gate behavior
- weekly gate / promotion thresholds
- broker candidate scoring semantics from Step 09 unless strictly necessary for safety docs
- existing shadow-ops behavior

Do not add:

- real broker credentials
- credential encryption system that requires local machine-specific setup
- live broker adapter
- live order submission path
- automatic paper/live order placement
- scheduler installation side effects

This step may add validation, docs, templates, and dry-run-only safety tooling.

## 2. Add runtime safety / security configs

Add these files or equivalent names:

```text
configs/security/runtime_security_policy_v1.yaml
configs/security/secrets_inventory_v1.yaml
configs/runtime/execution_host_local_v1.yaml
```

### 2.1 `runtime_security_policy_v1.yaml`

Include at least:

```yaml
version: runtime_security_policy_v1
stance: shadow_only_until_explicit_human_approval
forbidden:
  commit_real_secrets: true
  print_secret_values: true
  live_order_submission_without_two_step_enable: true
  broker_network_connection_in_step10: true
  auto_promote_ready_for_small_live: true
secret_redaction:
  redact_patterns:
    - password
    - secret
    - token
    - api_key
    - private_key
    - account
  replacement: "***REDACTED***"
runtime_flags:
  require_kill_switch_file_check: true
  kill_switch_file: state/KILL_SWITCH_ON
  trading_disabled_file: state/TRADING_DISABLED
  allow_shadow_without_secrets: true
  allow_dryrun_without_secrets: true
  allow_live_without_human_approval: false
logging:
  forbid_secret_values_in_logs: true
  max_log_file_mb: 50
backups:
  require_daily_artifact_backup_plan: true
  require_restore_test_plan: true
```

### 2.2 `secrets_inventory_v1.yaml`

This is an inventory and template only. It must not contain real values.

Include placeholder variable names for future broker work, for example:

```yaml
version: secrets_inventory_v1
secrets:
  - name: KABU_API_PASSWORD
    required_for_modes: [future_paper, future_live]
    required_now: false
    source: user_environment_or_local_secret_manager
    never_commit: true
  - name: IBKR_HOST
    required_for_modes: [future_paper, future_live]
    required_now: false
    source: user_environment_or_local_secret_manager
    never_commit: true
  - name: IBKR_PORT
    required_for_modes: [future_paper, future_live]
    required_now: false
    source: user_environment_or_local_secret_manager
    never_commit: true
```

Do not require these for current shadow-only checks.

### 2.3 `execution_host_local_v1.yaml`

Include local host expectations, but keep them warning-oriented for now:

```yaml
version: execution_host_local_v1
expected:
  timezone: Asia/Tokyo
  python_version_file: .python-version
  required_directories:
    - data/normalized/corrected_bundle
    - runs
    - artifacts
    - logs
    - state
  no_real_secrets_in_repo: true
  git_clean_required_for_live: true
  git_clean_required_for_shadow: false
  network_required_for_shadow: false
  scheduler_installed_required_now: false
```

## 3. Update `.env.example` safely

If `.env.example` exists, update it. If it does not exist, create it.

It must contain placeholders only:

```bash
# Shadow mode needs no real broker credentials.
LEADLAG_MODE=shadow
LEADLAG_ARTIFACT_ROOT=artifacts
LEADLAG_LOG_DIR=logs

# Future broker placeholders only. Do not fill real values.
KABU_API_PASSWORD=
IBKR_HOST=
IBKR_PORT=
```

Also ensure `.gitignore` ignores common local secret files, for example:

```text
.env
.env.local
*.secret
secrets.local.yaml
state/KILL_SWITCH_ON
state/TRADING_DISABLED
```

Do not ignore `.env.example`.

## 4. Add docs

Add these docs:

```text
docs/security_and_host_policy_v1.md
docs/secrets_handling_v1.md
docs/execution_host_setup_v1.md
docs/kill_switch_policy_v1.md
```

The docs should explain:

- current operating stance is shadow-only / dry-run-safe
- no real secrets should be committed
- `.env.example` is a template only
- future broker secrets must live outside git
- `READY_FOR_SMALL_LIVE` is not an automatic permission to trade
- kill switch semantics:
  - `state/KILL_SWITCH_ON` means do not proceed to any paper/live order-sending workflow
  - `state/TRADING_DISABLED` means all live-capable workflows must be disabled
- current Step 10 does not send orders or connect to brokers
- human approval remains required before paper/live activation
- backup and restore expectations for runs/artifacts/logs

Keep docs practical and short enough for operations use.

## 5. Add runtime safety code

Add a package, or use existing structure if better:

```text
src/leadlag/security/__init__.py
src/leadlag/security/redaction.py
src/leadlag/security/config.py
src/leadlag/runtime/host_checks.py
src/leadlag/runtime/safety.py
scripts/validate_runtime_safety.py
```

### 5.1 Redaction

Implement a pure utility that recursively redacts values from:

- dict
- list
- scalar strings

It should redact if a key name contains one of the configured secret patterns. It should also redact string values that look like obvious secret assignments, e.g. `api_key=...`, `token: ...`, `password=...`.

Tests must show that raw secret-looking values never appear in generated reports.

### 5.2 Runtime safety check

Implement a validator that loads:

- security policy config
- secrets inventory config
- execution host config

and writes:

```text
artifacts/runtime_safety/step10/runtime_safety_report.json
artifacts/runtime_safety/step10/runtime_safety_report.md
artifacts/runtime_safety/step10/redacted_environment_snapshot.json
```

The report should include:

- status: PASS / WARN / FAIL
- issue counts by severity
- config paths and hashes
- directory existence checks
- kill switch file status
- trading disabled file status
- forbidden secret file findings
- optional current Python version
- optional current timezone / local time
- environment snapshot with redaction

For current shadow-only mode, missing broker secrets should not fail.

Fail conditions should include:

- an obvious local secret file is tracked by git, if detectable
- `.env.example` contains non-empty secret-looking values
- runtime config cannot be parsed
- output reports contain unredacted secret-like values from the test path

Warn conditions may include:

- missing `state/` directory, if the script creates it or recommends creating it
- timezone not Asia/Tokyo
- git dirty state
- backup plan doc missing

Be conservative, but avoid making normal shadow development impossible.

## 6. Add CLI command

Add a CLI command:

```bash
python -m leadlag.cli runtime-safety-check \
  --security-config configs/security/runtime_security_policy_v1.yaml \
  --secrets-inventory configs/security/secrets_inventory_v1.yaml \
  --host-config configs/runtime/execution_host_local_v1.yaml \
  --output-dir artifacts/runtime_safety/step10
```

The standalone script should expose the same behavior:

```bash
python scripts/validate_runtime_safety.py \
  --security-config configs/security/runtime_security_policy_v1.yaml \
  --secrets-inventory configs/security/secrets_inventory_v1.yaml \
  --host-config configs/runtime/execution_host_local_v1.yaml \
  --output-dir artifacts/runtime_safety/step10
```

## 7. Add tests

Add focused tests, for example:

```text
tests/test_security_redaction.py
tests/test_runtime_safety_config.py
tests/test_runtime_safety_check.py
```

Tests should cover:

- secret-like keys are redacted
- nested structures are redacted
- `.env.example` placeholder-only policy passes
- non-empty secret placeholder in a temp `.env.example` fails or warns according to policy
- runtime safety report can be generated in a temp directory
- no live-capable flag is enabled by default

## 8. Update README

Add a short section for Step 10:

- runtime safety check command
- where artifacts are written
- statement that no broker credentials are required for shadow mode
- statement that real secrets must never be committed
- statement that this does not enable live trading

## 9. Run required commands

After implementation, run:

```bash
python -m compileall src scripts tests
python -m pytest tests/test_security_redaction.py tests/test_runtime_safety_config.py tests/test_runtime_safety_check.py -q
python -m pytest -q
python scripts/verify_baseline.py
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step10
python -m leadlag.cli runtime-safety-check \
  --security-config configs/security/runtime_security_policy_v1.yaml \
  --secrets-inventory configs/security/secrets_inventory_v1.yaml \
  --host-config configs/runtime/execution_host_local_v1.yaml \
  --output-dir artifacts/runtime_safety/step10
python scripts/validate_runtime_safety.py \
  --security-config configs/security/runtime_security_policy_v1.yaml \
  --secrets-inventory configs/security/secrets_inventory_v1.yaml \
  --host-config configs/runtime/execution_host_local_v1.yaml \
  --output-dir artifacts/runtime_safety/step10_script
```

If the full test suite has only the existing `datetime.utcnow()` warning, it is acceptable. Do not fix that warning in this step unless it is required by your changes.

## 10. Final report format

Return a concise report containing:

```text
Summary
Files changed
Commands executed
Runtime safety artifact location
Runtime safety result
Secret redaction result
Kill switch / trading-disabled status
Acceptance checklist
Follow-up notes / blockers
```

Acceptance checklist should include:

```text
preflight passed
security configs added
secrets inventory added
execution host config added
.env.example safe
.gitignore protects local secret files
runtime safety CLI added
runtime safety script added
redaction tests pass
runtime safety check passes
pytest passes
baseline verification passes
data contract validation passes
no broker credentials added
no broker network connection added
no live order submission path added
trading logic unchanged
simulator economics unchanged
daily hard gates unchanged
weekly gates unchanged
```

