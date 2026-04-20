# Step 07 Codex Instructions — Operations Runbook

You are working in the local repository for the lead-lag shadow trading stack.

The goal of Step 07 is to add an operations runbook for shadow/pre-live operations. This step is intentionally conservative. Do not change trading logic, PCA logic, sample filtering, corrected bundle data, simulator economics, daily hard gates, weekly gate rules, promotion rules, or broker interfaces.

## 0. Preflight

Before editing, run or inspect the current state:

```powershell
.venv\Scripts\python.exe scripts\verify_environment.py
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step07_preflight
```

If any command fails, stop and report the blocker. Do not proceed with edits until the reason is understood.

## 1. Add human-readable runbook docs

Create the following directory if needed:

```text
docs/runbooks/
```

Add:

```text
docs/runbooks/shadow_ops_runbook_v1.md
docs/runbooks/incident_response_v1.md
docs/runbooks/postmortem_template_v1.md
```

### `docs/runbooks/shadow_ops_runbook_v1.md`

This should be the main operations manual. Include at least:

1. Scope and non-goals
2. Operating modes
   - backtest
   - historical shadow
   - continuous shadow
   - broker dry-run, future
   - tiny live, future
   - full live, future / out of scope
3. Daily operating cycle
   - US close / data update
   - JP pre-open review
   - JP close / post-close review
4. Daily packet checklist
   - `summary.md`
   - `run.json`
   - `signals.csv`
   - `orders_shadow.csv`
   - `fills_shadow.csv`
   - `positions.csv`
   - `pnl.csv`
   - `risk_report.json`
   - `alerts.json`
   - canonical sidecars when enabled
5. GO / WARN / STOP actions
6. Weekly review procedure
7. Weekly gates / promotion assessment interpretation
8. Manual override policy
9. Kill switch policy
10. Deployment/change review checklist
11. AI-assisted review procedure
12. Escalation matrix
13. What not to do

Important wording:

- `READY_FOR_SMALL_LIVE` is not permission to start live automatically. It only permits a separate human-reviewed small-live step.
- AI review is advisory. Deterministic gates and human kill-switch authority take precedence.
- In the current repo phase, default operation remains shadow only.

### `docs/runbooks/incident_response_v1.md`

Define incident levels and responses.

Use these levels:

- `P0`: possible capital loss, unauthorized order, API/secrets exposure, live order mismatch, broken kill switch, hard gate bypass, corrupted production data.
- `P1`: STOP run/week, failed shadow replay day, failed data contract, missing required packet, baseline verification failure, unresolved canonical reconciliation failure.
- `P2`: repeated WARN, abnormal cost drift, low hit rate, high alert density, recurrent reconciliation drift under STOP threshold, non-critical scheduler failure.
- `P3`: documentation issue, cleanup, known warning, minor reporting issue, non-urgent technical debt.

For each level define:

- trigger examples
- immediate action
- who/what reviews it
- whether trading/shadow continues
- required artifact
- resolution criteria

### `docs/runbooks/postmortem_template_v1.md`

Create a concise incident postmortem template with:

- Incident ID
- Date/time
- Severity
- Detected by
- Affected mode
- Summary
- Timeline
- Root cause
- Impact
- Immediate mitigation
- Permanent fix
- Tests added
- Recurrence prevention
- Links to packets/artifacts
- Final status

## 2. Add machine-readable ops config

Create:

```text
configs/ops/runbook_shadow_v1.yaml
```

It should include at least:

```yaml
runbook_id: shadow_ops_runbook_v1
version: 1
scope: shadow_pre_live
status_actions:
  GO: ...
  WARN: ...
  STOP: ...
  HOLD_SHADOW: ...
  READY_FOR_SMALL_LIVE: ...
  BLOCKED: ...
incident_levels:
  P0: ...
  P1: ...
  P2: ...
  P3: ...
required_daily_packet_files:
  - summary.md
  - run.json
  - signals.csv
  - orders_shadow.csv
  - fills_shadow.csv
  - positions.csv
  - pnl.csv
  - risk_report.json
  - alerts.json
checklists:
  daily_pre_open: ...
  daily_post_close: ...
  weekly_review: ...
  deployment_review: ...
  promotion_review: ...
manual_override_policy: ...
kill_switch_policy: ...
ai_review_policy: ...
```

Keep this config descriptive. It should not drive trading behavior in this step.

## 3. Add optional validation/rendering utility

Add a small module and script to validate/render the runbook config.

Suggested files:

```text
src/leadlag/ops/runbook.py
scripts/render_runbook_checklists.py
```

Optional CLI subcommand is acceptable if it fits the repo style:

```text
leadlag render-runbook --config configs/ops/runbook_shadow_v1.yaml --output-dir artifacts/runbook/step07
```

If you add a CLI, keep it additive. Do not affect existing commands.

The renderer should produce:

```text
artifacts/runbook/step07/runbook_summary.md
artifacts/runbook/step07/daily_checklist.md
artifacts/runbook/step07/weekly_checklist.md
artifacts/runbook/step07/incident_matrix.md
artifacts/runbook/step07/runbook_validation.json
```

Validation should catch missing required top-level fields and duplicate incident levels/statuses if applicable.

## 4. Add tests

Add lightweight tests, for example:

```text
tests/test_runbook_config.py
```

Test at least:

- `configs/ops/runbook_shadow_v1.yaml` loads
- required top-level keys exist
- required packet files include the expected daily packet files
- incident levels include P0/P1/P2/P3
- statuses include GO/WARN/STOP/HOLD_SHADOW/READY_FOR_SMALL_LIVE/BLOCKED
- renderer or validator runs on the config

Do not require external broker credentials or internet.

## 5. Update README

Add a short section pointing to the runbook files and the rendering command.

Do not rewrite the whole README.

## 6. Run final verification

Run:

```powershell
.venv\Scripts\python.exe -m compileall src scripts tests
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step07
```

If you implemented the renderer/CLI, run it as well, for example:

```powershell
.venv\Scripts\python.exe scripts\render_runbook_checklists.py --config configs/ops/runbook_shadow_v1.yaml --output-dir artifacts/runbook/step07
```

or:

```powershell
.venv\Scripts\python.exe -m leadlag.cli render-runbook --config configs/ops/runbook_shadow_v1.yaml --output-dir artifacts/runbook/step07
```

## 7. Final report format

Report back in this structure:

```text
Summary

Files changed

Commands executed

Runbook artifact location

Acceptance checklist
- preflight passed:
- runbook docs added:
- machine-readable runbook config added:
- renderer/validator added:
- daily/weekly/incident/deployment/promotion procedures covered:
- pytest passes:
- baseline verification passes:
- data contract validation passes:
- existing trading logic unchanged:
- simulator economics unchanged:
- daily hard gates unchanged:
- weekly gates/promotion rules unchanged:

Follow-up notes / blockers
```

## 8. Non-goals and forbidden changes

Do not:

- change PCA SUB logic
- change Table 1 sample filtering
- change corrected bundle values
- change canonical simulator economics
- change daily hard gate behavior
- change weekly gates or promotion thresholds
- add live broker integration
- add real order submission
- loosen live promotion requirements
- store secrets in repo
