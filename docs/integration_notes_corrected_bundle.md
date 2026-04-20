# Corrected bundle integration notes

This repo now vendors the previously validated `leadlag_repro` engine under `src/leadlag_repro/` and bridges it from the scaffold CLI.

## What is wired now

- `leadlag inspect-bundle --config ...`
  - loads the corrected bundle
  - verifies Table 1 exact-match window search on `common_dates_core`
  - prints bundle summary
- `leadlag run --config configs/profiles/backtest_corrected.yaml`
  - creates a run packet directory
  - executes the corrected-bundle reproduction pipeline
  - writes `backtest_outputs/` with Table 1, Table 2, Table 3, Table 4, Figure 2, and status files
  - updates `summary.md` and `run.json`

## What is still intentionally separate

- the scaffold `leadlag.*` shadow/live runtime is still the long-term home for production execution
- the current backtest bridge uses the validated legacy engine to avoid breaking reproducibility while the new runtime is still being assembled

## Expected corrected-bundle file names

- `returns_cc.csv`
- `returns_oc_jp.csv`
- `open_prices_adj.csv`
- `close_prices_adj.csv`
- `common_dates_core.csv`
- `common_dates_full.csv`
- `ff3_japan_daily.csv`
- `mom_japan_daily.csv`
- `carhart4_japan_daily.csv`

Optional:

- `patch_table.csv`
