# baseline_shadow_stack_v1

- created_at_utc: `2026-04-17T13:37:20Z`
- requested branch: `ops/step01-baseline-freeze`
- requested tag: `baseline-shadow-stack-v1`
- git available: `False`
- dependency snapshot: `artifacts/baseline_shadow_stack_v1/pip_freeze.txt`

## Acceptance Checks

- tests pass: `pass`
- corrected bundle inspection succeeds: `pass`
- one historical shadow run succeeds: `pass`
- one batch replay succeeds: `pass`
- weekly review succeeds: `pass`
- weekly gates succeeds: `pass`
- hashes recorded: `pass`
- commands recorded: `pass`
- artifacts written under baseline root: `pass`

## Canonical Profiles

- `configs/profiles/backtest_corrected_local.yaml`
- `configs/profiles/shadow_corrected_local.yaml`
- `configs/profiles/shadow_corrected_batch_local.yaml`
- `configs/profiles/shadow_corrected_batch_20d_local.yaml`
- `configs/review/weekly_rules_shadow_default.yaml`

## Data Hashes

- `data/normalized/corrected_bundle/returns_cc.csv`: `f587c7b08476ea078013549193c3d28dc08111360000d0fe1ec69160d33b955b`
- `data/normalized/corrected_bundle/returns_oc_jp.csv`: `3ba6b9094b222e24a429a97f180bac4e08f3aadf7996507fcad4b790fd9c76ec`
- `data/normalized/corrected_bundle/close_prices_adj.csv`: `f4de26ee1cc507266e097acf527b56fb6b9451b0c66312bc24668cfaa490b607`
- `data/normalized/corrected_bundle/open_prices_adj.csv`: `a84da1b6e49ba68dddae4aea69addd58241b03be55737ad4771aaf1ecba20405`
- `data/normalized/corrected_bundle/common_dates_core.csv`: `b01b687327d69be250d392f0c44d1efdc86cd17bd0da19bb938da75693d39a81`
- `data/normalized/corrected_bundle/common_dates_full.csv`: `2508abf132c79870aaa6bb894898be859161f43d740b061b84c804e234e8b108`
- `data/normalized/corrected_bundle/ff3_japan_daily.csv`: `83684708fcb86a2fc8d389a455da7b9a23ea0b09f4aac7a0ba130835760edeaf`
- `data/normalized/corrected_bundle/mom_japan_daily.csv`: `3546a1c41d3944650a7bad0621916d404a87a74039a2a23e7753cc1b1ea13923`
- `data/normalized/corrected_bundle/carhart4_japan_daily.csv`: `6626c42c241ef6ecf66c9ab116c23f5dff1c7607d980831a40b777171cfc5e33`

## Notes

- Canonical baseline branch label: ops/step01-baseline-freeze
- Canonical baseline tag label: baseline-shadow-stack-v1
- Inspect-bundle reference command uses configs/profiles/backtest_corrected.yaml because backtest_corrected_local.yaml is pinned to /mnt/data.
- patch_table.csv not present in corrected bundle.
