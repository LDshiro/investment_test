# Data Contract Validation Report

- Contract: `corrected_bundle_v1` v`1.0.0`
- Bundle path: `C:\Users\shiro\OneDrive\ドキュメント\Spyder\MISOCP\investment\data\normalized\corrected_bundle`
- Result: `PASS`

## Issue Counts

- ERROR: 0
- WARN: 2
- INFO: 3

## Errors

- none

## Warnings

- `patch_table_missing`: Optional patch_table.csv is missing. details={"file": "patch_table.csv"}
- `returns_cc_differs_from_prices`: returns_cc.csv differs from close_prices_adj.pct_change(); this is diagnostic only because returns_cc.csv is canonical. details={"max_abs_diff": 0.16215724163120052, "mismatch_count": 12, "threshold": 1e-10}

## Info

- `factor_alias_resolved`: Factor aliases were resolved without renaming source columns. details={"aliases": {"MKT": "Mkt-RF"}, "file_key": "ff3"}
- `factor_alias_resolved`: Factor aliases were resolved without renaming source columns. details={"aliases": {"MOM": "WML"}, "file_key": "mom"}
- `factor_alias_resolved`: Factor aliases were resolved without renaming source columns. details={"aliases": {"MKT": "Mkt-RF", "MOM": "WML"}, "file_key": "carhart4"}

## Date Range Summary

- `returns_cc.csv`: rows=4159 start=2010-01-05 end=2025-12-31 unique=True monotonic=True weekend_count=0
- `returns_oc_jp.csv`: rows=4159 start=2010-01-05 end=2025-12-31 unique=True monotonic=True weekend_count=0
- `open_prices_adj.csv`: rows=4159 start=2010-01-05 end=2025-12-31 unique=True monotonic=True weekend_count=0
- `close_prices_adj.csv`: rows=4159 start=2010-01-05 end=2025-12-31 unique=True monotonic=True weekend_count=0
- `ff3_japan_daily.csv`: rows=4174 start=2010-01-01 end=2025-12-31 unique=True monotonic=True weekend_count=None
- `mom_japan_daily.csv`: rows=4174 start=2010-01-01 end=2025-12-31 unique=True monotonic=True weekend_count=None
- `carhart4_japan_daily.csv`: rows=4174 start=2010-01-01 end=2025-12-31 unique=True monotonic=True weekend_count=None
- `common_dates_core.csv`: rows=3795 start=2010-01-05 end=2025-12-30 unique=True monotonic=True weekend_count=None
- `common_dates_full.csv`: rows=1779 start=2018-06-20 end=2025-12-30 unique=True monotonic=True weekend_count=None

## Non-Null Summary

- `returns_cc.csv`: rows=4159 columns=28 min_non_null=1894 max_non_null=4023
- `returns_oc_jp.csv`: rows=4159 columns=17 min_non_null=3931 max_non_null=3931
- `open_prices_adj.csv`: rows=4159 columns=28 min_non_null=1895 max_non_null=4023
- `close_prices_adj.csv`: rows=4159 columns=28 min_non_null=1895 max_non_null=4023
- `ff3_japan_daily.csv`: rows=4174 columns=4 min_non_null=4174 max_non_null=4174
- `mom_japan_daily.csv`: rows=4174 columns=1 min_non_null=4174 max_non_null=4174
- `carhart4_japan_daily.csv`: rows=4174 columns=5 min_non_null=4174 max_non_null=4174

## Returns OC Reconciliation

- tolerance=1e-10
- max_abs_diff=3.220080452281948e-16
- mismatch_count=0

## Returns CC Diagnostic

- threshold=1e-10
- max_abs_diff=0.16215724163120052
- mismatch_count=12

## Canonical Returns Policy

- `returns_cc.csv` is canonical and is not recomputed or overwritten from adjusted prices.
- Differences versus `close_prices_adj.pct_change()` are diagnostic warnings only because approved manual corrections may exist.
