# canonical_simulator_v1

`canonical_simulator_v1` は、現時点の backtest / historical shadow simulator が「どういう入力を読み、どう packet を作っているか」を固定する監査用 contract です。Step 04A の目的は simulator を改善することではなく、今ある挙動を inspectable にすることです。

## なぜ canonical simulator が必要か

- 論文再現 backtest と historical shadow のあいだで、何が truth source なのかを固定するため
- broker paper / future live と比較するときに、先に internal canonical path を監査できるようにするため
- Step 04B 以降で cost / fill / PnL を強化しても、比較元の挙動を保存できるようにするため

## 何の truth source か

この simulator は、少なくとも次の truth source です。

- corrected Yahoo bundle の current interpretation
- Table 1 exact-match sample filter の current use
- historical shadow packet の current generation path
- current deployment-oriented weight scaling と hard gate evaluation
- current assumed fill / cost / one-day PnL calculation

broker paper trading や future live execution は別の truth source を持ちえますが、まず比較対象として canonical simulator を固定します。

## 入力

- predictor return: `returns_cc.csv`
- target return: `returns_oc_jp.csv`
- adjusted prices: `open_prices_adj.csv`, `close_prices_adj.csv`
- factor files: `ff3_japan_daily.csv`, `mom_japan_daily.csv`, `carhart4_japan_daily.csv`
- sample filter input: `common_dates_core.csv`
- optional patch governance input: `patch_table.csv`

historical shadow path は、`leadlag_repro` で paper-aligned strategy output を作り、その output を `leadlag` runtime で deployment-oriented shadow packet に変換しています。

## signal から orders へ

1. corrected bundle を読み込みます。
2. Table 1 exact-match sample filter を解決します。
3. 2010-2014 pre-sample から expand26to28 prior を構築します。
4. `leadlag_repro` の paper-aligned strategy output から対象日の JP signal を取り出します。
5. adjusted open / close price が両方ある JP 名だけを tradable とします。
6. tradable signal から equal-weight target を作ります。
7. target weight は `max_single_name_abs`、ついで `max_gross` に合わせて scale されます。
8. current risk gate を評価します。

## orders から fills へ

gate status が `STOP` でなければ、各 selected name について 2 本の仮想 fill を作ります。

- open fill
- close fill

current behavior では partial fill、queue position、latency、market impact、VWAP/TWAP、split execution は model していません。same-day open / close の 2-fill assumption が canonical behavior です。

## fills から positions / PnL へ

- target notional は `shadow_nav_jpy * abs(target_weight)` です。
- quantity は adjusted open assumed execution price から逆算します。
- gross PnL は `close_mid - open_mid` ベースです。
- net PnL は assumed execution open / close price ベースです。
- short が有効なら borrow fee を日割りで控除します。
- `pnl.csv` は 1 日の gross/net/cost/borrow/cumulative return を出します。

## まだ model していないもの

- intraday path
- partial fills
- broker queue / latency
- real order acknowledgement / reject
- borrow availability
- venue routing
- live cash management
- broker reconciliation

Step 04A では、これらを追加しません。今の simulator が何を model していて何を model していないかを文書化するだけです。

## broker paper / live との違い

- canonical simulator は internal truth source です。
- broker paper は broker API / paper venue の仕様に依存します。
- live は actual execution friction と operational failure mode を持ちます。

したがって、canonical simulator は live の代用品ではなく、live 差分を測るための基準です。
