# leadlag-stack README

この README は、`leadlag_stack_scaffold_shadow_impl.zip` に含まれる実装コードの説明と、日々の検証・historical shadow run・将来の live 連携までを見据えた使い方をまとめたものです。

この repo の目的は、日米業種リードラグ戦略について、

- 研究
- 論文再現バックテスト
- 継続シャドー運用
- live_dryrun / live 候補

を **できるだけ同じ code path と設定体系** で扱えるようにすることです。

現時点で特に完成度が高いのは、

- corrected bundle を使った **Table 1 確認**
- corrected bundle を使った **再現バックテスト**
- corrected bundle を使った **1日分の historical shadow packet 生成**
- **hard gate 判定** と **daily packet 出力**

です。

一方で、将来の production native 実装として用意してある `src/leadlag/strategy/pca_sub.py` はまだ scaffold 段階です。現在の実証済み backtest / historical shadow の中核計算は、以前の再現用エンジンを `src/leadlag_repro/` として vendoring し、それを `src/leadlag/runtime/corrected_backtest.py` と `src/leadlag/runtime/corrected_shadow.py` から呼ぶ構造になっています。

---

## 1. この repo の考え方

この repo では、次の原則を採っています。

1. **canonical simulator を真実の検証器にする**
2. broker paper/test 環境は **配線確認用** に限定する
3. backtest / shadow / live_dryrun / live は **mode 切替** で扱う
4. 毎営業日 `daily packet` を出して、AI や人間が監査しやすい形にする
5. データ修正は `patch_table.csv` で明示管理する
6. config は `base.yaml + component config + profile` の多層構成で管理する

つまり、

- **収益検証の正本** は自前ロジック
- **接続確認の正本** は broker adapter
- **実運用摩擦の正本** は少額 live

という三層です。

---

## 2. 現在の状態

### 実装済み

- config loader と Pydantic 検証
- corrected bundle の読込
- Table 1 観測数一致窓の探索
- corrected bundle を使った再現 backtest
- historical shadow run
- daily packet の実ファイル出力
- hard gate 判定
- cost 仮定つき fill 生成
- run metadata のハッシュ管理
- pytest による基本テスト

### まだ scaffold / placeholder の部分

- `src/leadlag/strategy/pca_sub.py` の純粋 native 実装
- broker adapter の実発注本体
- scheduler の本格運用 integration
- live 約定データの取り込み
- native canonical simulator への完全移行

現状は、

- **研究と historical shadow を確実に回すための器** はできている
- **production 直結の broker 実装** はこれから差し込む

という状態です。

---

## 3. ディレクトリ構成

```text
leadlag-stack/
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ configs/
│  ├─ base.yaml
│  ├─ data/
│  ├─ strategy/
│  ├─ cost/
│  ├─ risk/
│  ├─ broker/
│  ├─ packets/
│  └─ profiles/
├─ docs/
│  ├─ repo_blueprint.md
│  ├─ config_reference.md
│  ├─ daily_packet_schema.md
│  ├─ operating_model.md
│  └─ integration_notes_corrected_bundle.md
├─ src/
│  ├─ leadlag/
│  │  ├─ cli.py
│  │  ├─ config/
│  │  ├─ data/
│  │  ├─ strategy/
│  │  ├─ portfolio/
│  │  ├─ sim/
│  │  ├─ runtime/
│  │  ├─ reporting/
│  │  └─ broker/
│  ├─ leadlag_repro/
│  └─ leadlag_stack.egg-info/
└─ tests/
```

### 主要ディレクトリの役割

#### `configs/`
設定ファイル群です。`base.yaml` を土台に、用途別 config を `extends` で積みます。

#### `docs/`
設計メモです。README より簡潔ですが、repo の哲学と packet 設計が整理されています。

#### `src/leadlag/`
この repo の本体です。将来の production home になる想定です。

#### `src/leadlag_repro/`
以前に検証済みだった再現用実装を vendoring したものです。現在の backtest / historical shadow はここに依存しています。

#### `tests/`
設定の読み込み、packet layout、gate 判定、weights 計算、profile merge のテストです。

---

## 4. 重要なモジュールの説明

### 4.1 CLI

ファイル: `src/leadlag/cli.py`

エントリポイントです。現在使える主要コマンドは次です。

- `validate-config`
- `inspect-bundle`
- `validate-data-contract`
- `run`
- `run-batch`
- `weekly-review`
- `weekly-gates`

#### `validate-config`
YAML を読み込み、Pydantic で検証します。

#### `inspect-bundle`
corrected bundle を読み込み、Table 1 の exact match window を探索し、その要約を表示します。

#### `validate-data-contract`
corrected bundle を `corrected_bundle_v1` contract で検証し、validation report と file hash artifact を出力します。

#### `run`
`run.mode` と `data.source` を見て処理を分岐します。

- `backtest + corrected_bundle` → `run_corrected_backtest()`
- `shadow + corrected_bundle` → `run_corrected_shadow()`
- それ以外 → scaffold packet のみ生成

---

### 4.2 Config 系

ファイル:

- `src/leadlag/config/models.py`
- `src/leadlag/config/loader.py`

`models.py` には config 全体の schema が定義されています。

主なセクションは次です。

- `run`
- `calendar`
- `data`
- `universe`
- `sample`
- `strategy`
- `costs`
- `risk`
- `broker`
- `packet`
- `runtime`

`loader.py` は `extends:` を再帰的に読み、deep merge して最終 config を作ります。

### config の読み込み順

1. profile YAML を読む
2. `extends:` で親 YAML を再帰ロード
3. 親から子へ deep merge
4. Pydantic で検証

この実装により、`base.yaml` を全体既定値にしつつ、profile 側で少数項目だけ上書きできます。

---

### 4.3 Data 層

ファイル:

- `src/leadlag/data/contracts.py`
- `src/leadlag/data/corrected_bundle.py`
- `src/leadlag/data/store.py`

#### `contracts.py`
`MarketPanels` と `CorrectedBundle` という dataclass を定義しています。

#### `corrected_bundle.py`
CSV 群を wide DataFrame と date list に読み込みます。

読み込むもの:

- `returns_cc`
- `returns_oc_jp`
- `common_dates_core`
- `common_dates_full`
- `ff3`
- `mom`
- `carhart4`
- `open_prices_adj`
- `close_prices_adj`
- `patch_table`（任意）

#### `store.py`
Parquet の読み書きと DuckDB クエリの薄い wrapper です。
今の corrected bundle runner では主役ではありませんが、将来の raw / normalized / features 保存に使う前提の土台です。

---

### 4.4 Strategy 層

ファイル:

- `src/leadlag/strategy/pca_sub.py`
- `src/leadlag/strategy/prior_subspace.py`
- `src/leadlag/strategy/momentum.py`
- `src/leadlag/strategy/double_sort.py`
- `src/leadlag/strategy/universe.py`

#### `pca_sub.py`
現在は scaffold only です。`pca_sub_signal()` はゼロシグナルを返す placeholder で、将来ここに native 実装を入れる想定です。

#### `prior_subspace.py`
事前部分空間の basis を組みます。

- v1: global factor
- v2: US / JP country spread
- v3: cyclical / defensive factor

Gram-Schmidt で単純直交化しています。

#### `momentum.py`
JP 側リターンの平均で MOM シグナルを作る簡易関数です。

#### `double_sort.py`
2 種類の signal の rank を合成する placeholder 実装です。

#### `universe.py`
現時点では `cfg.universe.jp` をそのまま返します。

> 重要: 現在の実運用的な backtest / shadow path では、ここではなく vendored `leadlag_repro` 側の実装が使われています。

---

### 4.5 Portfolio 層

ファイル:

- `src/leadlag/portfolio/weights.py`
- `src/leadlag/portfolio/risk_gates.py`
- `src/leadlag/portfolio/costs.py`

#### `weights.py`
`long_short_equal_weight()` は signal 上位・下位から等ウェイトを作ります。

- `allow_short=True` なら long / short 両方
- `allow_short=False` なら long-only

`scale_weights_to_limits()` は次の 2 つを満たすように weights を縮小します。

- `max_single_name_abs`
- `max_gross`

縮小した場合は alerts 用の warning を返します。

#### `risk_gates.py`
shadow / live_dryrun の安全装置です。評価項目は次です。

- `no_common_dates`
- `missing_price`
- `missing_factor`
- `unapproved_patch`
- `tradable_names_too_few`
- `cost_too_high`
- `gross_exposure_exceeded`
- `net_exposure_exceeded`（short 許可時）
- `max_single_name_abs_exceeded`
- `universe_shrinkage`

判定結果は

- `GO`
- `WARN`
- `STOP`

の 3 段階です。

**critical alert が 1 つでもあれば STOP** です。

#### `costs.py`
コストモデルの集約です。

- open side cost = commission + open_half_spread + slippage_open
- close side cost = commission + close_half_spread + slippage_close
- expected round-trip cost = gross exposure × (open + close) + short carry

short carry は `borrow_fee_bps_annual / annualization_days` を日割りで使います。

---

### 4.6 Runtime 層

ファイル:

- `src/leadlag/runtime/corrected_backtest.py`
- `src/leadlag/runtime/corrected_shadow.py`
- `src/leadlag/runtime/packets.py`
- `src/leadlag/runtime/meta.py`
- `src/leadlag/runtime/jobs.py`
- `src/leadlag/runtime/alerts.py`

#### `corrected_backtest.py`
corrected bundle と vendored `leadlag_repro` をつないで backtest を実行します。

主な役割:

- corrected bundle 読み込み
- Table 1 sample filter の探索
- Table 1-like stats の確認
- 再現 backtest の実行
- `summary.md` と `run.json` の更新

#### `corrected_shadow.py`
historical shadow run の中心です。現時点で最も重要なファイルです。

この処理は大まかに次の順で進みます。

1. corrected bundle を読み込む
2. Table 1 観測数一致の sample window を探索する
3. 2010–2014 の prior を `core26 -> 28` 拡張で構築する
4. vendored fast backtest を走らせる
5. その結果から指定日の signal を取り出す
6. open / close price が揃った JP 名だけを tradable とみなす
7. `allow_short`, `max_gross`, `max_single_name_abs` で weights を risk-aware に変換する
8. hard gate を評価する
9. STOP でなければ open/close の仮想 fill を作る
10. daily packet を保存する

#### `packets.py`
packet directory を生成し、最低限の required files を placeholder として揃えます。

#### `meta.py`
再現性と監査のためのハッシュを作ります。

- `hash_tree()` → repo tree のコード/設定/README 等のハッシュ
- `hash_config()` → config のハッシュ
- `hash_data_root()` → data file 群のサイズ/mtime ベースのハッシュ
- `patch_version()` → patch table 単体ハッシュ
- `make_run_id()` → run 名 + timestamp ベースの ID

これにより、`run.json` から

- どのコードで
- どの設定で
- どのデータで
- どの patch で

回したかを追跡できます。

---

### 4.7 Reporting 層

ファイル: `src/leadlag/reporting/daily.py`

`build_daily_summary()` が `summary.md` を組み立てます。

入る内容は主に次です。

- GO / WARN / STOP
- strategy 名
- trade date / as-of US date
- shadow NAV
- tradable names / selected names
- gross / net exposure
- expected round-trip cost
- realized gross / net return
- paper counterfactual return
- 前営業日との差分
- top longs / bottom names
- alerts 一覧

---

### 4.8 Broker 層

ファイル:

- `src/leadlag/broker/base.py`
- `src/leadlag/broker/null.py`

現時点では `NullBroker` が中心です。

`configs/broker/kabu.yaml` と `configs/broker/ibkr.yaml` は **adapter 設計用の設定ファイル** であり、実送信までの production 実装はまだありません。

つまり、今の broker 層は

- shadow 用の no-op
- 将来の live_dryrun/live 差し込み口

という位置づけです。

---

### 4.9 Vendored reproduction engine

ディレクトリ: `src/leadlag_repro/`

これは以前検証済みの再現エンジンです。現時点では次の用途に使っています。

- corrected bundle の再現バックテスト
- Table 1 sample filter 探索
- prior 構築
- PCA SUB / MOM / PCA PLAIN / DOUBLE の fast backtest
- 回帰や論文再現値の出力

つまり、現在の repo は

- `leadlag_repro` = 数値検証の proven engine
- `leadlag` = production/shadow の home

という構成です。

---

## 5. corrected bundle の前提

`configs/data/corrected_bundle.yaml` は、次のファイルを前提にしています。

- `returns_cc.csv`
- `returns_oc_jp.csv`
- `common_dates_core.csv`
- `common_dates_full.csv`
- `ff3_japan_daily.csv`
- `mom_japan_daily.csv`
- `carhart4_japan_daily.csv`
- `open_prices_adj.csv`
- `close_prices_adj.csv`
- `patch_table.csv`（任意）

### 推奨ディレクトリ構成

```text
my_corrected_bundle/
├─ returns_cc.csv
├─ returns_oc_jp.csv
├─ common_dates_core.csv
├─ common_dates_full.csv
├─ ff3_japan_daily.csv
├─ mom_japan_daily.csv
├─ carhart4_japan_daily.csv
├─ open_prices_adj.csv
├─ close_prices_adj.csv
└─ patch_table.csv   # optional
```

### patch table の扱い

`patch_table.csv` が存在し、かつ `approved` 列がある場合、すべて `True` でないと `unapproved_patch` gate が発火しえます。

`approved` 列がなければ、現在の実装では「存在は認識するが STOP まではしない」という扱いです。

---

## 6. インストール

### 必須環境

- package metadata 上の最小要件: Python 3.11 以上
- local reproducibility 用の pin: Python 3.14.3

### 依存パッケージ

`pyproject.toml` で次を要求しています。

- pandas
- numpy
- pyyaml
- pydantic
- duckdb
- matplotlib
- statsmodels

### インストール手順

```bash
python -m venv .venv
source .venv/bin/activate   # Windows は .venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

開発用ツールも入れるなら:

```bash
pip install -e .[dev]
```

---

## 7. 設定ファイルの考え方

### 7.1 基本構造

- `configs/base.yaml` に全体既定値
- `configs/data/*.yaml` にデータソースごとの設定
- `configs/strategy/*.yaml` に戦略設定
- `configs/cost/*.yaml` にコスト設定
- `configs/risk/*.yaml` にリスク設定
- `configs/broker/*.yaml` にブローカー設定
- `configs/packets/*.yaml` に packet 仕様
- `configs/profiles/*.yaml` に実行プロファイル

### 7.2 profile の実例

#### `configs/profiles/backtest_corrected.yaml`
論文再現用 backtest profile です。

#### `configs/profiles/backtest_corrected_local.yaml`
ローカル実行用に `runs_root`, `logs_root`, `data.root` を上書きした profile です。

#### `configs/profiles/shadow_corrected.yaml`
historical shadow 用です。

#### `configs/profiles/shadow_corrected_local.yaml`
ローカル用 shadow profile で、`historical_trade_date` と `shadow_nav_jpy` を含みます。

### 7.3 まず最初に直すべき箇所

自分の環境で最初に直すことが多いのは次です。

```yaml
run:
  runs_root: /path/to/runs
  logs_root: /path/to/logs

data:
  root: /path/to/corrected_bundle
```

現在配布している `*_local.yaml` は `/mnt/data/...` を前提にしているので、自前環境では通常ここを変えます。

---

## 8. 既定の戦略・コスト・リスク設定

### strategy: `configs/strategy/pca_sub.yaml`

- `name: pca_sub`
- `lookback_L: 60`
- `n_components_K: 3`
- `prior_dim_K0: 3`
- `lambda_reg: 0.9`
- `quantile_q: 0.3`
- `annualization_days: 252`
- `cfull_policy: core26_expand_to_28`

### cost: `configs/cost/jp_etf_conservative.yaml`

- `commission_bps: 0.0`
- `open_half_spread_bps: 6.0`
- `close_half_spread_bps: 6.0`
- `slippage_open_bps: 4.0`
- `slippage_close_bps: 4.0`
- `borrow_fee_bps_annual: 0.0`

これは **初期の shadow/live 比較用の保守的コスト** です。

### risk: `configs/risk/default.yaml`

- `max_gross: 1.0`
- `max_net: 0.0`
- `max_single_name_abs: 0.15`
- `min_tradable_names: 6`
- `max_expected_cost_bps: 35.0`
- `allow_short: false`

ここが重要です。現在の default risk は **deployment oriented** であり、**論文どおりの raw long/short をそのまま出す設定ではありません**。

つまり、historical shadow run で paper のロングショート結果と差が出るのは正常です。shadow では、

- short 禁止
- gross cap
- single-name cap

が効いて、実行可能な portfolio に変換されます。

論文忠実な paper 形状に寄せたいなら、`allow_short: true` などを別 profile で明示的に変えてください。

---

## 9. 主要コマンド

この repo には console script は定義していないので、基本は `python -m leadlag.cli` で実行します。

### 9.1 config の妥当性確認

```bash
python -m leadlag.cli validate-config --config configs/profiles/backtest_corrected.yaml
```

期待される出力例:

```text
config ok: name=backtest_corrected mode=backtest source=corrected_bundle
```

### 9.2 corrected bundle の検査

```bash
python -m leadlag.cli inspect-bundle --config configs/profiles/backtest_corrected.yaml
```

このコマンドは、

- corrected bundle を読む
- `common_dates_core` 上で Table 1 一致窓を探索する
- sample filter の開始日・終了日・gap sum を出す

ためのものです。

### data contract の検証

```bash
python -m leadlag.cli validate-data-contract \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

standalone script 版を使うなら:

```bash
python scripts/validate_data_contract.py \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

### 9.3 backtest の実行

```bash
python -m leadlag.cli run --config configs/profiles/backtest_corrected.yaml
```

ローカル用 profile を使うなら:

```bash
python -m leadlag.cli run --config configs/profiles/backtest_corrected_local.yaml
```

実行後、packet directory の下に `backtest_outputs/` が作られ、Table 2, Table 3, Table 4, Figure 2 などが保存されます。

### 9.4 1日分の historical shadow run

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml
```

複数営業日をまとめて replay する場合は、batch profile を使います。

```bash
python -m leadlag.cli run-batch --config configs/profiles/shadow_corrected_batch_local.yaml
```

20営業日 replay 用 profile もあります。

```bash
python -m leadlag.cli run-batch --config configs/profiles/shadow_corrected_batch_20d_local.yaml
```

run-batch の出力先にある `batch_summary.csv` から、週次レビュー用の集計を作るには次を使います。

```bash
python -m leadlag.cli weekly-review \
  --batch-dir runs/shadow_corrected_batch_20d_local_batch_YYYY-MM-DD_YYYY-MM-DD_... \
  --output-dir reports/weekly_review_latest
```

script 版を直接使うこともできます。

```bash
python scripts/weekly_review_from_batch_summary.py \
  --batch-summary runs/.../batch_summary.csv \
  --output-dir reports/weekly_review_latest
```

Jupyter で確認したい場合は `notebooks/weekly_review_from_batch_summary.ipynb` を使います。

特定日を上書きするなら:

```bash
python -m leadlag.cli run \
  --config configs/profiles/shadow_corrected_local.yaml \
  --trade-date 2025-11-28
```

`--trade-date` を指定しない場合は、

1. `cfg.run.historical_trade_date`
2. それもなければ strategy output の最新 valid trade date

の順に使います。

---

## 10. historical shadow run の挙動

historical shadow run は、単なる placeholder ではなく、かなり具体的に以下を行います。

### 10.1 入力

- corrected bundle
- sample filter
- prior
- vendored PCA SUB backtest 結果
- open / close adjusted prices
- factor files
- patch table
- cost / risk config

### 10.2 当日の流れ

1. `trade_date` を決める
2. その日の raw signal を取り出す
3. 価格が揃った銘柄だけ `tradable` とする
4. `allow_short` に応じて equal-weight portfolio を作る
5. `max_gross` と `max_single_name_abs` に収まるよう scale する
6. expected cost を計算する
7. hard gate を評価する
8. GO/WARN なら仮想 open/close fill を作る
9. `orders_shadow.csv`, `fills_shadow.csv`, `positions.csv`, `pnl.csv` を保存する
10. `summary.md`, `run.json`, `risk_report.json`, `alerts.json` を保存する
11. optional charts を描く

### 10.3 `paper_counterfactual_return` とは何か

`run.json` と `summary.md` に出る `paper_counterfactual_return` は、

- vendored engine 上の **論文寄りの paper portfolio** の当日リターン

です。

一方、`shadow_net_return` は、

- tradable 制約
- short 制約
- gross cap
- single-name cap
- cost 仮定

を入れた **deployment-oriented shadow portfolio** の当日リターンです。

両者の差は、まさに実務化ギャップです。

---

## 11. daily packet の内容

1 run ごとに packet directory が 1 つ作られます。

既定の required files は次です。

- `summary.md`
- `run.json`
- `signals.csv`
- `orders_shadow.csv`
- `fills_shadow.csv`
- `positions.csv`
- `pnl.csv`
- `risk_report.json`
- `alerts.json`

optional files:

- `figure_signals.png`
- `figure_equity_curve.png`

### 11.1 各ファイルの意味

#### `summary.md`
人間と AI が最初に読む短い日報です。

#### `run.json`
run の識別情報、バージョン情報、データ状態、当日成績が入ります。

主な項目:

- `run_id`
- `mode`
- `code_version`
- `config_hash`
- `data_version`
- `patch_version`
- `data_status`
- `model_status`
- `run_status`
- `strategy`
- `bundle_root`
- `sample_filter_start / end`
- `trade_date`
- `asof_us_date`
- `shadow_nav_jpy`
- `paper_counterfactual_return`
- `shadow_net_return`
- `shadow_gross_return`
- `expected_cost_bps`

#### `signals.csv`
当日のシグナル snapshot です。

主な列:

- `ticker`
- `signal_raw`
- `signal_rank`
- `tradable_flag`
- `paper_weight_raw`
- `target_weight`

#### `orders_shadow.csv`
仮想注文意図です。

#### `fills_shadow.csv`
仮想 fill 行です。open / close の 2 本が基本です。

#### `positions.csv`
銘柄別の weight, quantity, PnL を持ちます。

#### `pnl.csv`
日単位の集計です。

主な列:

- `gross_return`
- `net_return`
- `cost_return`
- `gross_pnl_jpy`
- `net_pnl_jpy`
- `borrow_pnl_jpy`
- `cumulative_return`

#### `risk_report.json`
hard gate の詳細です。

#### `alerts.json`
warning / critical alert の一覧です。

---

## 12. hard gate の詳細

hard gate は `src/leadlag/portfolio/risk_gates.py` で評価します。

### 判定項目

- `no_common_dates`
- `missing_price`
- `missing_factor`
- `unapproved_patch`
- `tradable_names_too_few`
- `cost_too_high`
- `gross_exposure_exceeded`
- `net_exposure_exceeded`
- `max_single_name_abs_exceeded`
- `universe_shrinkage`

### severity の考え方

- `cfg.risk.hard_gates` に入っているものは critical 扱い
- `missing_price` と `unapproved_patch` は halt 設定次第で critical
- triggered で critical が 1 件でもあれば `STOP`
- critical がなく warning のみなら `WARN`
- 何もなければ `GO`

### 注意

`scale_weights_to_limits()` による縮小は、通常 `STOP` ではなく warning です。

つまり、

- signal は出ている
- そのままではリスク上限を超える
- だから scale して実行可能形へ寄せる

という設計です。

---

## 13. 出力の再現性

この repo は「いつ・何で・何を回したか」を追跡しやすくするため、`run.json` に複数のハッシュを残します。

### `code_version`
`leadlag-stack/<version>:<tree-hash>` の形式です。

### `config_hash`
最終 merge 後の config 全体の hash です。

### `data_version`
対象 data files の size と mtime から作る hash です。

### `patch_version`
`patch_table.csv` のファイル hash です。

これにより、後で

- コードを変えたのか
- config を変えたのか
- corrected bundle を差し替えたのか
- patch を更新したのか

を切り分けられます。

---

## 14. テスト

テストは `tests/` にあります。

現在入っているのは主に次です。

- profile config が正しく読めるか
- corrected bundle profile が正しい filename を向いているか
- missing price で STOP になるか
- packet directory が正しく作られるか
- shadow profile が component override を保っているか
- equal-weight ロジックが動くか

実行方法:

```bash
pytest
```

dev 依存込みで厳しめに見るなら:

```bash
pip install -e .[dev]
pytest
```

---

## 15. 実用上の使い分け

### 15.1 論文再現だけ見たい場合

使うもの:

- `backtest_corrected.yaml`
- `inspect-bundle`
- `run`

この用途では `src/leadlag_repro/` が中心です。

### 15.2 継続シャドー運用の器を育てたい場合

使うもの:

- `shadow_corrected.yaml`
- `shadow_corrected_local.yaml`
- `run --trade-date ...`
- packet 一式
- hard gate

この用途では `src/leadlag/runtime/corrected_shadow.py` と `src/leadlag/reporting/` が中心です。

### 15.3 将来 live_dryrun / live へ広げたい場合

使うもの:

- `configs/broker/kabu.yaml` または `configs/broker/ibkr.yaml`
- `broker/` に実 adapter を追加
- `NullBroker` と同じ interface に寄せる

ただし、**現時点では broker 実装は placeholder** です。

---

## 16. 拡張ポイント

### 16.1 新しい strategy を入れる

基本方針は、

1. `src/leadlag/strategy/<new_strategy>.py` を作る
2. `configs/strategy/<new_strategy>.yaml` を作る
3. `runtime/` から呼ぶ code path を追加する
4. 必要なら `leadlag_repro` から native 実装へ移す

です。

### 16.2 新しい data source を入れる

1. `src/leadlag/data/<source>.py` を作る
2. `DataSection.source` に応じた loader 分岐を増やす
3. `configs/data/<source>.yaml` を作る

### 16.3 broker adapter を足す

1. `src/leadlag/broker/<name>.py` を作る
2. `base.py` の interface に合わせる
3. `configs/broker/<name>.yaml` を作る
4. `live_dryrun` から先に試す

### 16.4 hard gate を追加する

`risk_gates.py` の `register()` 呼び出しを追加し、必要なら `configs/risk/default.yaml` の `hard_gates:` に加えます。

---

## 17. よくある使い方

### A. 手元の corrected bundle をまず検査する

```bash
python -m leadlag.cli validate-config --config configs/profiles/backtest_corrected.yaml
python -m leadlag.cli inspect-bundle --config configs/profiles/backtest_corrected.yaml
```

### B. Table 2 まで再計算する

```bash
python -m leadlag.cli run --config configs/profiles/backtest_corrected.yaml
```

### C. 1日分の historical shadow packet を作る

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml --trade-date 2025-11-28
```

### D. short を許可した論文寄り shadow profile を作る

たとえば `configs/profiles/shadow_paper_like.yaml` を自作して、次のように上書きします。

```yaml
extends:
  - shadow_corrected.yaml

run:
  name: shadow_paper_like
  mode: shadow

risk:
  allow_short: true
  max_gross: 2.0
  max_net: 0.0
  max_single_name_abs: 0.20
```

その上で:

```bash
python -m leadlag.cli run --config configs/profiles/shadow_paper_like.yaml --trade-date 2025-11-28
```

---

## 18. 既知の制約と注意点

1. `src/leadlag/strategy/pca_sub.py` はまだ production native ではありません。
2. backtest / historical shadow は vendored `leadlag_repro` 依存です。
3. broker adapter は実送信未実装です。
4. `*_local.yaml` は `/mnt/data/...` 前提なので、自分の環境向けに直す必要があります。
5. `data_version` は内容 hash ではなく size/mtime ベースなので、厳密内容ハッシュほど強くはありません。
6. factor file の欠損は gate で STOP します。
7. patch table に `approved` 列がある場合は承認運用が必要です。

---

## 19. トラブルシューティング

### `config not found`
profile の相対パスを誤っている可能性があります。repo root から実行するのが安全です。

### `trade date ... not available`
その日が strategy output の有効日付に入っていません。`inspect-bundle` と sample window を確認してください。

### `STOP` で packet が空に近い
hard gate が発火しています。`risk_report.json` と `alerts.json` を見て原因を確認してください。

### `patch_table_present_without_approved_column`
patch table 自体は読めていますが、承認列がありません。現状では warning 扱いです。運用で厳密化するなら `approved` を追加してください。

### backtest は通るのに shadow の PnL が弱い
正常です。shadow では `allow_short`, `max_gross`, `max_single_name_abs`, expected cost, tradable filter が効きます。`paper_counterfactual_return` と比べて差を観察してください。

---

## 20. おすすめの今後の進め方

この repo を土台に次に進めるなら、順番は次が安全です。

1. `shadow_corrected_local.yaml` を自分の環境向けに修正する
2. 毎日 1 日分の historical shadow packet を数日ぶん生成し、packet の読み方を固める
3. `allow_short: true` と現行 `allow_short: false` を比較し、paper と deployment の差を理解する
4. broker adapter を live_dryrun から差し込む
5. live に入る前に `daily packet + hard gate + alert` を固定化する
6. その後に native `leadlag.strategy.pca_sub` へ計算中核を移す

---

## 21. 最小クイックスタート

迷ったら、まずこれだけで十分です。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# data.root を自分の corrected bundle に直す
python -m leadlag.cli validate-config --config configs/profiles/shadow_corrected_local.yaml
python -m leadlag.cli inspect-bundle --config configs/profiles/shadow_corrected_local.yaml
python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml --trade-date 2025-11-28
```

その後、生成された packet を見て、

- `summary.md`
- `run.json`
- `signals.csv`
- `risk_report.json`
- `alerts.json`

の順で読むのが最も分かりやすいです。

---

## 18. Baseline Freeze

`baseline freeze` は、現行 stack の repo/config/data/reference outputs を比較基準として固定する運用ステップです。Step 01 の baseline 名は `baseline_shadow_stack_v1` で、artifact は `artifacts/baseline_shadow_stack_v1/` にまとまります。

最初の生成は次で行います。

```bash
python scripts/freeze_baseline.py
```

この script は `.venv` を自動で作成し、必要なら `pip install -e .[dev]` を実行したうえで、`pytest`、bundle inspection、historical shadow、batch replay、weekly review、weekly gates を凍結します。

生成物の検証は次です。

```bash
python scripts/verify_baseline.py
```

reference commands と manifest は `artifacts/baseline_shadow_stack_v1/` 以下に保存されます。後続ステップでは、この baseline の hash と frozen outputs を比較対象として使い、戦略ロジックを変えずに運用変更だけを評価してください。

---

## 19. Environment Reproducibility

Step 02 では、local 実行環境を `3.14.3` に pin し、lock file と bootstrap / verify script で再現しやすくしています。Python pin は `.python-version` にあり、environment artifact は `artifacts/environment_repro_v1/` に出力されます。

最初の bootstrap は次です。

```bash
python scripts/bootstrap_env.py --dev
```

きれいに作り直すなら:

```bash
python scripts/bootstrap_env.py --dev --recreate
```

検証は次です。

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/verify_environment.py
.venv\Scripts\python.exe scripts/verify_baseline.py
```

lock file の更新と snapshot export は次です。

```bash
python scripts/export_environment_snapshot.py --refresh-locks
```

この step は setup / docs / environment metadata を整えるもので、strategy math や risk / promotion logic は変更しません。詳細は `docs/environment_reproducibility.md` を参照してください。

---

## 20. Data Contract Freeze

Step 03 では、corrected Yahoo bundle の interpretation を `corrected_bundle_v1` として固定します。これは strategy logic を変える step ではなく、required files、ticker universe、factor alias、hash、validation output を機械検証可能にする step です。

最初の検証は次です。

```bash
python scripts/validate_data_contract.py \
  --bundle-dir data/normalized/corrected_bundle \
  --contract configs/data_contracts/corrected_bundle_v1.yaml \
  --output-dir artifacts/data_contract/corrected_bundle_v1
```

artifact は `artifacts/data_contract/corrected_bundle_v1/` に出力されます。詳細な policy と canonical interpretation は `docs/data_contract_corrected_bundle_v1.md` を参照してください。

---

## 21. Canonical Simulator Audit

Step 04A では、current historical shadow packet path を `canonical_simulator_v1` contract と golden-day audit で監査できるようにします。これは simulator を改善する step ではなく、今の packet 生成挙動を inspectable にする step です。

最初の実行は次です。

```bash
python scripts/audit_simulator_golden_days.py \
  --config configs/profiles/shadow_corrected_local.yaml \
  --simulator-contract configs/simulator/canonical_simulator_v1.yaml \
  --output-dir artifacts/simulator_audit/canonical_v1 \
  --refresh
```

artifact は `artifacts/simulator_audit/canonical_v1/` に出力されます。詳細は `docs/canonical_simulator_v1.md` と `docs/golden_day_audit.md` を参照してください。

---

## 22. Opt-In Canonical Shadow Simulator

Step 04B では、legacy historical shadow packet を既定のまま残しつつ、cash-cost 明示型の canonical simulator を sidecar として同じ packet directory に書けるようにします。

最初の実行は次です。

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_canonical_local.yaml
```

主な sidecar files は次です。

- `canonical_orders.csv`
- `canonical_fills.csv`
- `canonical_positions.csv`
- `canonical_pnl.csv`
- `canonical_simulation_result.json`
- `sim_reconciliation.csv`
- `sim_reconciliation.json`
- `sim_reconciliation.md`

default legacy path を比較対象としてそのまま回す場合は次です。

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml
```

詳細は `docs/canonical_simulator_v1.md` を参照してください。

---

## 23. Shadow Replay Validation

Step 05 では、60 営業日 historical shadow replay を legacy / canonical の両方で監査する `validate-shadow-replay` を追加します。

```bash
python -m leadlag.cli validate-shadow-replay \
  --batch-dir runs/<batch_dir> \
  --validation-config configs/validation/shadow_replay_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/debug_run
```

canonical replay では `configs/validation/shadow_replay_canonical_v1.yaml` を使います。詳細は `docs/shadow_replay_validation.md` を参照してください。

---

## 24. Weekly Gate Calibration

Step 06 では、weekly GO / WARN / STOP と promotion rule を calibration するための pre-live ruleset と comparison utility を追加します。これは readiness を無理に通す step ではなく、`HOLD_SHADOW` を含めた安全側の判定を明示する step です。

```bash
python -m leadlag.cli weekly-rule-calibration \
  --weekly-review-dir artifacts/shadow_replay_validation/step05_legacy_60d/weekly_review \
  --weekly-review-dir artifacts/shadow_replay_validation/step05_canonical_60d/weekly_review \
  --rules-config configs/review/weekly_rules_shadow_default.yaml \
  --rules-config configs/review/weekly_rules_shadow_small_live_candidate.yaml \
  --rules-config configs/review/weekly_rules_shadow_pre_live_v1.yaml \
  --output-dir artifacts/weekly_rule_calibration/step06
```

policy と解釈の詳細は `docs/weekly_gate_calibration_policy.md` を参照してください。

---

## 25. Operations Runbook

Step 07 では、shadow / pre-live operations 用の runbook docs と machine-readable runbook config を追加します。

- `docs/runbooks/shadow_ops_runbook_v1.md`
- `docs/runbooks/incident_response_v1.md`
- `docs/runbooks/postmortem_template_v1.md`
- `configs/ops/runbook_shadow_v1.yaml`

rendered checklist artifact は次で生成できます。

```bash
python -m leadlag.cli render-runbook \
  --config configs/ops/runbook_shadow_v1.yaml \
  --output-dir artifacts/runbook/step07
```

---

## 26. Shadow Ops Profile

Step 08 では、data contract validation、60 日 replay、replay validation、weekly review、weekly gates、runbook rendering を 1 コマンドでまとめる `shadow-ops` を追加します。これは shadow-only orchestration であり、live trading を起動しません。

legacy 60d:

```bash
python -m leadlag.cli shadow-ops \
  --config configs/ops/shadow_ops_legacy_60d_local.yaml
```

canonical 60d:

```bash
python -m leadlag.cli shadow-ops \
  --config configs/ops/shadow_ops_canonical_60d_local.yaml
```

詳細は `docs/shadow_ops_profile_v1.md` を参照してください。
