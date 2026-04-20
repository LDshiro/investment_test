# Weekly rule calibration

This report compares multiple weekly rulesets across the legacy and canonical Step 05 weekly reviews.

## Review sources

- `step05_legacy_60d`: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_replay_validation\step05_legacy_60d\weekly_review`
- `step05_canonical_60d`: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\artifacts\shadow_replay_validation\step05_canonical_60d\weekly_review`

## Rulesets

- `weekly_rules_shadow_default`: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\review\weekly_rules_shadow_default.yaml`
- `weekly_rules_shadow_small_live_candidate`: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\review\weekly_rules_shadow_small_live_candidate.yaml`
- `weekly_rules_shadow_pre_live_v1`: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\configs\review\weekly_rules_shadow_pre_live_v1.yaml`

## Promotion comparison

| source_name          | ruleset_name                             | promotion_status   | latest_week_status   | reason                             | failed_requirements                                                                      |
|:---------------------|:-----------------------------------------|:-------------------|:---------------------|:-----------------------------------|:-----------------------------------------------------------------------------------------|
| step05_legacy_60d    | weekly_rules_shadow_default              | HOLD_SHADOW        | GO                   | promotion requirements not yet met | non_negative_shadow_return                                                               |
| step05_canonical_60d | weekly_rules_shadow_default              | HOLD_SHADOW        | GO                   | promotion requirements not yet met | non_negative_shadow_return                                                               |
| step05_legacy_60d    | weekly_rules_shadow_small_live_candidate | HOLD_SHADOW        | GO                   | promotion requirements not yet met | non_negative_shadow_return                                                               |
| step05_canonical_60d | weekly_rules_shadow_small_live_candidate | HOLD_SHADOW        | GO                   | promotion requirements not yet met | non_negative_shadow_return                                                               |
| step05_legacy_60d    | weekly_rules_shadow_pre_live_v1          | HOLD_SHADOW        | GO                   | promotion requirements not yet met | non_negative_shadow_return; sufficient_go_weeks; limited_warn_weeks; acceptable_hit_rate |
| step05_canonical_60d | weekly_rules_shadow_pre_live_v1          | HOLD_SHADOW        | GO                   | promotion requirements not yet met | non_negative_shadow_return; sufficient_go_weeks; limited_warn_weeks; acceptable_hit_rate |

## Recommended decision

Current recommendation: **HOLD_SHADOW**

Pre-live promotion requirements are not yet met: step05_legacy_60d: non_negative_shadow_return; sufficient_go_weeks; limited_warn_weeks; acceptable_hit_rate; step05_canonical_60d: non_negative_shadow_return; sufficient_go_weeks; limited_warn_weeks; acceptable_hit_rate

## Status comparison notes

| source_name          | ruleset_name                             | week_label   | weekly_status   | stop_reasons   | warn_reasons   |
|:---------------------|:-----------------------------------------|:-------------|:----------------|:---------------|:---------------|
| step05_canonical_60d | weekly_rules_shadow_default              | 2025-W48     | GO              |                |                |
| step05_canonical_60d | weekly_rules_shadow_pre_live_v1          | 2025-W48     | GO              |                |                |
| step05_canonical_60d | weekly_rules_shadow_small_live_candidate | 2025-W48     | GO              |                |                |
| step05_legacy_60d    | weekly_rules_shadow_default              | 2025-W48     | GO              |                |                |
| step05_legacy_60d    | weekly_rules_shadow_pre_live_v1          | 2025-W48     | GO              |                |                |
| step05_legacy_60d    | weekly_rules_shadow_small_live_candidate | 2025-W48     | GO              |                |                |

A HOLD_SHADOW result is acceptable at this stage. Step 06 is a calibration step, not a readiness-forcing step.
