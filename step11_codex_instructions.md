# Step 11 Codex Instructions: Broker Dry-Run Integration

You are working in the local repository for the lead-lag investment research / shadow operations stack.

Step 11 must be additive, safety-first, and non-live. The task is to integrate the existing broker-neutral dry-run path into batch shadow operations so that shadow packets can be translated into deterministic broker-neutral order intents and safe `NullBroker` acknowledgements.

Do not add real broker connectivity. Do not add credentials. Do not add paper/live order submission. Do not modify strategy logic.

---

## 0. Read first

Before editing, inspect the current repository state and read the relevant existing files:

- `README.md`
- `docs/broker_adapter_contract_v1.md`
- `docs/broker_safety_policy_v1.md`
- `docs/security_and_host_policy_v1.md`
- `docs/secrets_handling_v1.md`
- `docs/shadow_ops_profile_v1.md`
- `configs/brokers/null_broker_v1.yaml`
- `configs/security/runtime_security_policy_v1.yaml`
- `configs/security/secrets_inventory_v1.yaml`
- `configs/runtime/execution_host_local_v1.yaml`
- `configs/ops/shadow_ops_legacy_60d_local.yaml`
- `configs/ops/shadow_ops_canonical_60d_local.yaml`
- `src/leadlag/broker/`
- `src/leadlag/ops/shadow_ops.py`
- `src/leadlag/runtime/safety.py`
- `scripts/validate_runtime_safety.py`

Then run a preflight:

```powershell
.venv\Scripts\python.exe scripts\verify_environment.py
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step11_preflight
.venv\Scripts\python.exe -m leadlag.cli runtime-safety-check --security-config configs/security/runtime_security_policy_v1.yaml --secrets-inventory configs/security/secrets_inventory_v1.yaml --host-config configs/runtime/execution_host_local_v1.yaml --output-dir artifacts/runtime_safety/step11_preflight
```

If runtime safety is `WARN` with `ERROR=0`, that is acceptable for local shadow-only development. If it has any `ERROR`, stop and report.

---

## 1. Non-negotiable constraints

Do not change:

- PCA SUB calculation;
- signal computation;
- Table 1 sample filter;
- corrected bundle values;
- canonical simulator economics;
- daily hard gate behavior;
- weekly gate thresholds;
- promotion thresholds;
- existing default shadow behavior;
- existing NullBroker safety behavior.

Do not add:

- real broker network calls;
- credential loading for real brokers;
- paper broker connection;
- live broker connection;
- live order submission;
- scheduler installation.

Any config attempting `PAPER`, `LIVE`, or `allow_live_submission: true` must fail closed in Step 11.

---

## 2. Add broker dry-run batch config

Add a broker-dryrun validation/config file, for example:

```text
configs/broker_dryrun/broker_dryrun_batch_v1.yaml
```

It should define:

```yaml
version: broker_dryrun_batch_v1
mode: DRY_RUN
allowed_broker_ids:
  - null_broker_v1
allow_live_submission: false
allow_paper_submission: false
require_runtime_safety: true
allow_runtime_safety_warn: true
block_on_runtime_safety_error: true
require_packet_files:
  - run.json
  - orders_shadow.csv
  - risk_report.json
  - alerts.json
order_source: orders_shadow.csv
max_reject_rate: 0.0
max_missing_intent_rate: 0.0
require_ack_for_every_intent: true
write_daily_artifacts: true
```

Keep names consistent with existing style if the repo already has a better pattern.

---

## 3. Add batch broker dry-run module

Add a module such as:

```text
src/leadlag/broker/batch_dryrun.py
```

or, if repo conventions prefer operations modules:

```text
src/leadlag/ops/broker_dryrun.py
```

Implement a safe batch broker dry-run over a shadow batch directory.

### Required behavior

Input:

- `batch_dir`: a directory produced by `run-batch` or `shadow-ops`;
- `broker_config`: normally `configs/brokers/null_broker_v1.yaml`;
- `dryrun_config`: `configs/broker_dryrun/broker_dryrun_batch_v1.yaml`;
- `output_dir`.

For each daily packet:

1. Read `run.json`.
2. Read `orders_shadow.csv`.
3. Convert each open-side order row into a broker-neutral `OrderIntent` using the existing Step 09 model layer.
4. Preserve close-leg or shadow-only fields only as metadata.
5. Pass each intent through the null broker dry-run adapter.
6. Write per-day outputs.
7. Accumulate summary statistics.

### Output files

For each date:

```text
<output_dir>/daily/<trade_date>/
  broker_order_intents.csv
  broker_payloads.json
  broker_acks.json
  broker_diagnostics.json
```

For the whole batch:

```text
<output_dir>/broker_dryrun_summary.csv
<output_dir>/broker_dryrun_summary.json
<output_dir>/broker_dryrun_summary.md
<output_dir>/broker_dryrun_validation.json
```

### Required summary fields

At minimum include:

- `trade_date`
- `packet_dir`
- `run_status`
- `intent_count`
- `payload_count`
- `ack_count`
- `reject_count`
- `diagnostic_error_count`
- `diagnostic_warn_count`
- `gross_notional_jpy` if available
- `buy_notional_jpy` if available
- `sell_notional_jpy` if available
- `broker_id`
- `broker_mode`
- `passed`

For batch-level JSON include:

- `total_days`
- `completed_days`
- `failed_days`
- `intent_count_total`
- `ack_count_total`
- `reject_count_total`
- `diagnostic_error_count_total`
- `diagnostic_warn_count_total`
- `passed`
- `reason_if_failed`

### Safety expectations

- Reject any broker config whose mode is not safe null/dry-run.
- Reject `allow_live_submission: true`.
- Never import or call kabu / IBKR libraries.
- Never open sockets or make HTTP requests.
- Never read real credential environment variables.
- Use deterministic fake broker order IDs.

---

## 4. Add CLI and script

Add a CLI command:

```bash
python -m leadlag.cli broker-dryrun-batch \
  --batch-dir <batch_dir> \
  --broker-config configs/brokers/null_broker_v1.yaml \
  --dryrun-config configs/broker_dryrun/broker_dryrun_batch_v1.yaml \
  --output-dir artifacts/broker_dryrun_batch/manual_test
```

Also add a script wrapper:

```text
scripts/broker_dryrun_batch.py
```

The script should call the same code path as the CLI.

---

## 5. Integrate with shadow-ops as an optional stage

Extend `shadow-ops` configuration, but keep old profiles valid and unchanged.

Add opt-in profiles:

```text
configs/ops/shadow_ops_broker_dryrun_legacy_60d_local.yaml
configs/ops/shadow_ops_broker_dryrun_canonical_60d_local.yaml
```

These should inherit or mirror the existing Step 08 profiles:

- legacy: `configs/ops/shadow_ops_legacy_60d_local.yaml`
- canonical: `configs/ops/shadow_ops_canonical_60d_local.yaml`

and enable a new optional stage like:

```yaml
broker_dryrun:
  enabled: true
  broker_config: configs/brokers/null_broker_v1.yaml
  dryrun_config: configs/broker_dryrun/broker_dryrun_batch_v1.yaml
  output_subdir: broker_dryrun
  require_runtime_safety: true
  allow_runtime_safety_warn: true
```

When enabled, `shadow-ops` should run:

1. data contract validation;
2. batch replay;
3. replay validation;
4. weekly review;
5. weekly gates;
6. runbook rendering;
7. broker dry-run batch.

If the current `shadow-ops` ordering is better with broker dry-run before/after weekly gates, choose the more auditable ordering and document it. The key requirement is that broker dry-run uses the final packet directory created by the batch replay.

The old profiles must continue to run without the broker dry-run stage.

---

## 6. Add docs

Add:

```text
docs/broker_dryrun_ops_v1.md
```

The docs should explain:

- what broker dry-run means;
- why this is still not paper/live trading;
- how packet rows become broker-neutral order intents;
- why close-leg fields are metadata only;
- what artifacts are produced;
- how to run the CLI;
- how to interpret pass/fail;
- what must be true before future paper/live integration.

Update `README.md` with a concise link and command examples.

---

## 7. Add tests

Add tests such as:

```text
tests/test_broker_dryrun_batch.py
tests/test_broker_dryrun_shadow_ops_integration.py
tests/test_broker_dryrun_safety.py
```

Test at least:

- valid batch with one or two fake packet dirs produces summary;
- every order row becomes an intent;
- every intent gets a deterministic null broker ack;
- invalid broker mode fails closed;
- `allow_live_submission: true` fails closed;
- missing `orders_shadow.csv` fails or records failure according to config;
- old shadow-ops profiles still parse/run through config validation without broker-dryrun requirement;
- broker-dryrun-enabled profiles include the stage.

Do not require external broker APIs.

---

## 8. Execute validation

Run:

```powershell
.venv\Scripts\python.exe -m compileall src scripts tests
.venv\Scripts\python.exe -m pytest tests\test_broker_dryrun_batch.py tests\test_broker_dryrun_shadow_ops_integration.py tests\test_broker_dryrun_safety.py -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step11
.venv\Scripts\python.exe -m leadlag.cli runtime-safety-check --security-config configs/security/runtime_security_policy_v1.yaml --secrets-inventory configs/security/secrets_inventory_v1.yaml --host-config configs/runtime/execution_host_local_v1.yaml --output-dir artifacts/runtime_safety/step11
```

Then run a standalone batch broker dry-run using an existing or newly generated 60d batch. If no suitable batch path exists, first run a 60d legacy shadow-ops or run-batch.

Example:

```powershell
.venv\Scripts\python.exe -m leadlag.cli broker-dryrun-batch --batch-dir <resolved_legacy_batch_dir> --broker-config configs/brokers/null_broker_v1.yaml --dryrun-config configs/broker_dryrun/broker_dryrun_batch_v1.yaml --output-dir artifacts/broker_dryrun_batch/step11_legacy_manual
```

Then run legacy and canonical ops profiles:

```powershell
.venv\Scripts\python.exe -m leadlag.cli shadow-ops --config configs/ops/shadow_ops_broker_dryrun_legacy_60d_local.yaml
.venv\Scripts\python.exe -m leadlag.cli shadow-ops --config configs/ops/shadow_ops_broker_dryrun_canonical_60d_local.yaml
```

---

## 9. Final report format

When done, report in this exact structure:

```text
Summary
...

Files changed
...

Commands executed
...

Standalone broker dry-run artifact location
...

Legacy broker-dryrun shadow-ops run location
...

Canonical broker-dryrun shadow-ops run location
...

Broker dry-run summary
legacy completed_days / failed_days: ...
legacy intent_count_total / ack_count_total / reject_count_total: ...
canonical completed_days / failed_days: ...
canonical intent_count_total / ack_count_total / reject_count_total: ...

Safety guarantees
real broker connection added: no
credential handling for real broker added: no
live order submission path added: no
paper broker submission path added: no
NullBroker only: yes
runtime safety ERROR count: ...

Acceptance checklist
preflight passed: pass/fail
broker-dryrun batch config added: pass/fail
standalone broker-dryrun-batch works: pass/fail
legacy shadow-ops broker dry-run works: pass/fail
canonical shadow-ops broker dry-run works: pass/fail
old shadow-ops profiles unchanged: pass/fail
pytest passes: pass/fail
baseline verification passes: pass/fail
data contract validation passes: pass/fail
runtime safety passes: pass/fail
trading logic unchanged: pass/fail
simulator economics unchanged: pass/fail
daily hard gates unchanged: pass/fail
weekly gates unchanged: pass/fail

Follow-up notes / blockers
...
```

Stop and report immediately if any live/paper broker connection or credential handling becomes necessary. That is out of scope for Step 11.
