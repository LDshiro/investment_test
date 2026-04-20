# Config reference

## merge ルール

- すべての YAML は `extends` を持てる
- 下位ファイルが上位設定を deep-merge で上書きする
- list は丸ごと置換する
- `configs/base.yaml` を **最上位の土台** とし、`configs/data|strategy|cost|risk|broker|packets` は **leaf component config** にする
- profile では `base.yaml` を最初に extend し、そのあと component config を読む

## 最重要セクション

### run
- `name`: run 名
- `mode`: backtest / shadow / live_dryrun / live
- `runs_root`: 出力先
- `historical_trade_date`: historical shadow run の対象日
- `shadow_nav_jpy`: 1日 shadow run で使う仮想元本

### sample
- `enforce_table1_counts`: Table 1 観測数合わせを使うか
- `table1_target.common_n`: 共通営業日数
- `table1_target.xlc_n`, `table1_target.xlre_n`: XLC/XLRE の N
- `cfull_window_start/end`: `C_full` 推定期間

### strategy
- `lookback_L`: ローリング窓
- `n_components_K`: 使う主成分数
- `prior_dim_K0`: 事前部分空間の次元
- `lambda_reg`: 正則化係数
- `quantile_q`: long/short 分位点
- `cfull_policy`: `core26_expand_to_28` など

### risk
- `allow_short`: 初期 live では false 推奨
- `max_gross`: 総建玉
- `max_single_name_abs`: 1銘柄最大比率
- `hard_gates`: STOP 条件
- `min_tradable_names`: 最低 tradable 銘柄数
- `max_expected_cost_bps`: 元本比 expected round-trip cost 上限

### broker
- `kind`: null / kabu / ibkr
- `paper_sync`: paper 環境への同期
- `dry_run_only`: 実送信禁止
