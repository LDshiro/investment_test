# Step 06 Codex Instructions — Weekly Gate and Promotion Rule Calibration

You are working in the local repository for `LDshiro/investment_test`.

Step 06 is safety-sensitive. The goal is to calibrate and document weekly GO / WARN / STOP and small-live promotion rules. Do not optimize rules to force a READY outcome.

## 0. Hard constraints

Do not change:

- PCA SUB signal logic
- Table 1 sample filtering
- corrected bundle values
- data contract semantics
- canonical simulator return/cost accounting
- daily hard gate behavior
- broker interfaces
- existing default weekly rules unless a bug fix is strictly necessary

Prefer additive changes:

- add new configs
- add new docs
- add calibration utility
- add tests
- add artifacts

The existing files `configs/review/weekly_rules_shadow_default.yaml` and `configs/review/weekly_rules_shadow_small_live_candidate.yaml` should remain usable.

## 1. Preflight

Run:

```bash
python scripts/verify_environment.py
python scripts/verify_baseline.py
python -m pytest -q
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step06_preflight
```

If any preflight step fails, stop and report the failure before making changes.

## 2. Inspect current Step 05 outputs

Use the existing Step 05 artifacts if present:

```text
artifacts/shadow_replay_validation/step05_legacy_60d/
artifacts/shadow_replay_validation/step05_canonical_60d/
```

Confirm the following exist:

```text
weekly_review/weekly_summary.csv
weekly_gates/weekly_status_evaluated.csv
weekly_gates/promotion_assessment.json
weekly_gates/promotion_assessment.md
replay_validation/replay_validation_report.md
```

If these artifacts are missing, regenerate them using the existing 60d profiles before continuing.

## 3. Add a weekly gate calibration policy document

Create:

```text
docs/weekly_gate_calibration_policy.md
```

The document should explain:

- Difference between weekly status and promotion status
- Why STOP should be operational/safety-oriented
- Why poor but non-catastrophic performance should usually be WARN/HOLD, not STOP
- Why promotion rules should not be tuned to pass the current sample
- Required evidence before moving toward tiny/small live
- How to interpret legacy vs canonical replay consistency
- How the policy relates to future live-dryrun and tiny live phases

## 4. Add a stricter pre-live ruleset

Add a new config:

```text
configs/review/weekly_rules_shadow_pre_live_v1.yaml
```

Suggested behavior:

- Extend or mirror the default rule schema.
- Keep all hard STOP conditions from `weekly_rules_shadow_default.yaml`.
- Promotion should be stricter than the default small-live rule.
- Use a longer lookback if the code supports it, preferably 8 weeks. If the current rule engine only supports 4 weeks reliably, keep 4 but document the limitation.
- Require no STOP weeks.
- Require no failed days.
- Require no critical alert days.
- Require no triggered hard-gate days.
- Require latest week to be GO.
- Require most weeks to be GO.
- Require compounded shadow return to be non-negative.
- Require weighted hit rate to be at least around 40%.
- Require weighted average tradable names to remain comfortably high.
- Require expected costs to remain within the currently observed stable range.

Recommended live overrides should be more conservative than the existing small-live candidate, for example:

```yaml
recommended_live_overrides:
  run:
    mode: live_dryrun
  risk:
    allow_short: false
    max_gross: 0.25
    max_single_name_abs: 0.05
  deployment:
    max_live_names: 1
    fixed_ticket_notional_jpy: 25000
    expected_objective: Measure live-vs-shadow execution friction only; not PnL maximization.
```

Do not loosen `non_negative_shadow_return` merely because the current Step 05 latest window is negative.

## 5. Add a calibration utility

Add either a CLI command and/or script. Prefer both if lightweight.

Suggested files:

```text
src/leadlag/reporting/weekly_rule_calibration.py
scripts/calibrate_weekly_rules.py
```

Optional CLI command:

```bash
python -m leadlag.cli weekly-rule-calibration \
  --weekly-review-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_review \
  --weekly-review-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_default.yaml \
  --rules-config configs/review/weekly_rules_shadow_small_live_candidate.yaml \
  --rules-config configs/review/weekly_rules_shadow_pre_live_v1.yaml \
  --output-dir artifacts/weekly_rule_calibration/step06
```

The utility should compare multiple rule configs across multiple weekly review directories.

Output at least:

```text
artifacts/weekly_rule_calibration/step06/calibration_report.md
artifacts/weekly_rule_calibration/step06/ruleset_weekly_status_comparison.csv
artifacts/weekly_rule_calibration/step06/promotion_comparison.csv
artifacts/weekly_rule_calibration/step06/calibration_manifest.json
```

Recommended columns:

For `ruleset_weekly_status_comparison.csv`:

```text
source_name
ruleset_name
week_label
weekly_status
stop_reasons
warn_reasons
shadow_return_compounded
shadow_hit_rate
avg_tradable_names
avg_expected_cost_bps
```

For `promotion_comparison.csv`:

```text
source_name
ruleset_name
promotion_status
reason
latest_week_status
go_weeks
warn_weeks
stop_weeks
total_trade_days
total_shadow_return_compounded
weighted_shadow_hit_rate
weighted_avg_expected_cost_bps
weighted_avg_tradable_names
failed_requirements
```

If existing weekly gate functions can be reused directly, import them. If not, call the existing weekly-gates command internally or refactor conservatively without changing behavior.

## 6. Apply current rules and new rules

Run weekly-gates using default and pre-live rules for both legacy and canonical outputs:

```bash
python -m leadlag.cli weekly-gates \
  --review-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_default.yaml \
  --output-dir artifacts/weekly_rule_calibration/step06/legacy_default

python -m leadlag.cli weekly-gates \
  --review-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_default.yaml \
  --output-dir artifacts/weekly_rule_calibration/step06/canonical_default

python -m leadlag.cli weekly-gates \
  --review-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_pre_live_v1.yaml \
  --output-dir artifacts/weekly_rule_calibration/step06/legacy_pre_live_v1

python -m leadlag.cli weekly-gates \
  --review-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_pre_live_v1.yaml \
  --output-dir artifacts/weekly_rule_calibration/step06/canonical_pre_live_v1
```

Then run the calibration utility that summarizes all outputs.

## 7. Tests

Add tests for:

- New pre-live rules config can be loaded.
- Weekly calibration utility works on a tiny synthetic weekly summary.
- STOP overrides WARN and GO.
- Promotion returns BLOCKED when failed days or hard gate days exist.
- Promotion returns HOLD when operationally fine but performance requirements are not met.
- Existing default weekly rules remain loadable.

Run:

```bash
python -m pytest -q
python scripts/verify_baseline.py
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1_step06
```

## 8. Acceptance criteria

Step 06 is acceptable if:

- Existing default weekly-gates behavior still works.
- A stricter pre-live ruleset exists and is documented.
- Calibration report compares default, small-live candidate, and pre-live rulesets.
- Legacy and canonical Step 05 outputs are both included in calibration.
- The current system is not promoted to live merely by loosening rules.
- `pytest -q` passes.
- `verify_baseline.py` passes.
- data contract validation passes.
- No trading or simulator behavior changed.

## 9. Final report format

Report back in this format:

```text
Summary
Files changed
Commands executed
Rule configs evaluated
Legacy 60d result by ruleset
Canonical 60d result by ruleset
Promotion statuses
Recommended decision for current state
Acceptance checklist
Follow-up notes / blockers
```

Be explicit if the result remains HOLD_SHADOW. That is acceptable and likely desirable at this stage.
