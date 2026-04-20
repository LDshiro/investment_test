# corrected_bundle_v1 Data Contract

`corrected_bundle_v1` は、`data/normalized/corrected_bundle` を research、backtest、historical shadow replay、weekly review、将来の live migration で同じ意味に解釈するための machine-verifiable contract です。

この step は strategy math、PCA SUB、risk gate、weekly promotion rule、bundle values を変えるものではありません。目的は、schema、validation、hash、documentation を固定して bundle interpretation を再現可能にすることです。

## Required Files

- `returns_cc.csv`
- `returns_oc_jp.csv`
- `open_prices_adj.csv`
- `close_prices_adj.csv`
- `common_dates_core.csv`
- `common_dates_full.csv`
- `ff3_japan_daily.csv`
- `mom_japan_daily.csv`
- `carhart4_japan_daily.csv`

## Optional Files

- `patch_table.csv`
- `bundle_manifest.json`
- `data_hashes.json`

## Canonical Interpretation

- `returns_cc.csv`
  Predictor side close-to-close returns の canonical file です。manual correction を含みうるため、`close_prices_adj.csv` から再計算して上書きしません。
- `returns_oc_jp.csv`
  日本 open-to-close realized return の canonical file です。validator は `close_prices_adj.csv / open_prices_adj.csv - 1` と照合します。
- `open_prices_adj.csv` / `close_prices_adj.csv`
  QC、plot、audit 用の adjusted price file です。`returns_oc_jp.csv` の整合確認に使います。
- `common_dates_core.csv` / `common_dates_full.csv`
  sample construction input です。bundle 全体の universal filter としては扱いません。validator は `returns_cc.csv` に対する subset と complete-case を確認します。
- `ff3_japan_daily.csv` / `mom_japan_daily.csv` / `carhart4_japan_daily.csv`
  weekly review や factor-aware QC に使う factor input です。`Mkt-RF` と `WML` の alias を contract で正式サポートします。

## Universes And Factor Aliases

- US all: `XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, XLC, XLRE`
- US core: `XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY`
- JP: `1617.T` から `1633.T`
- FF3 required columns: `MKT, SMB, HML, RF`
- MOM required column: `MOM`
- Carhart4 required columns: `MKT, SMB, HML, MOM, RF`
- Accepted aliases:
  - `MKT`: `MKT`, `Mkt-RF`
  - `MOM`: `MOM`, `WML`

## Patch Table Policy

`patch_table.csv` があれば、少なくとも次の列を持つ前提です。

- `ticker`
- `date`
- `field`
- `before`
- `after`
- `reason`
- `patch_id`
- `status`

accepted status values は `approved`, `pending`, `rejected` です。ただし active bundle に含めてよい status は既定で `approved` のみです。`pending` と `rejected` を含む bundle は ERROR になります。`patch_table.csv` が無い場合は WARN で、bundle invalid にはしません。

## Severity Levels

- `ERROR`: contract violation。validation は fail です。
- `WARN`: canonical policy 上は許容されるが監査上は注意が必要です。
- `INFO`: alias resolution などの参考情報です。

## Validation Commands

standalone script:

```bash
python scripts/validate_data_contract.py \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

CLI integration:

```bash
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

## Validation Outputs

validator は次を書きます。

- `validation_report.md`
- `validation_report.json`
- `ticker_summary.csv`
- `file_hashes.json`

`validation_report.md` では contract name/version、bundle path、PASS/FAIL、severity counts、ERROR/WARN/INFO sections、date range summary、non-null summary、canonical returns policy を確認できます。

`ticker_summary.csv` では universe ticker ごとの presence と non-null count を追えます。`file_hashes.json` は bundle 配下 file の SHA-256 manifest です。

## Backtest / Shadow / Live との接続

- backtest / shadow はこの contract で前提 file と interpretation を固定できます。
- weekly review は factor file alias を壊さずに同じ bundle を監査できます。
- future live migration では、strategy logic を変えずに「入力 bundle が contract を満たしているか」を先に判定できます。

要するに、Step 03 は trading logic の改善ではなく、input data の meaning を凍結する step です。
