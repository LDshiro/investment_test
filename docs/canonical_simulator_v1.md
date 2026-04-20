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

## Step 04B の位置づけ

Step 04B では、この contract を土台にして opt-in の `canonical_v1` simulator を historical shadow packet に sidecar として書き出します。

- legacy historical shadow packet は既定のまま残します
- canonical simulator は比較用の sidecar output です
- reconciliation で legacy と canonical の差分を明示します
- `use_for_shadow_packets` は将来の切替フラグですが、Step 04B ではまだ default packet を置き換えません

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

## Step 04B canonical PnL formula

Step 04B の opt-in canonical path では、legacy shadow と違って cost を fill price に埋め込まず、cash cost として明示的に分けて記録します。

- `return_oc_i = close_i / open_i - 1`
- `target_notional_i = nav_start_jpy * weight_i`
- `quantity_i = target_notional_i / open_i`
- `gross_pnl_i = quantity_i * (close_i - open_i)`
- `entry_cost_i = abs(target_notional_i) * entry_cost_bps / 10000`
- `exit_cost_i = abs(quantity_i * close_i) * exit_cost_bps / 10000`
- `borrow_cost_i = abs(target_notional_i) * (borrow_fee_bps_annual / annualization_days) / 10000` for shorts only
- `net_pnl_i = gross_pnl_i - entry_cost_i - exit_cost_i - borrow_cost_i`

この path でも価格 source は corrected bundle の adjusted open / adjusted close です。fractional quantity は shadow mode の default として許容します。

## Legacy との差

- legacy shadow: assumed execution price に cost bps を埋め込む
- canonical shadow: open/close mid price はそのまま使い、execution cost を別勘定で落とす
- legacy quantity: open assumed execution price ベース
- canonical quantity: adjusted open price ベース
- 両者とも risk gate 後の同じ target weight を使う

したがって、Step 04B の reconciliation では gross return 差だけでなく cost return 差も必ず確認します。

## Step 04B で書かれる sidecar files

`configs/profiles/shadow_corrected_canonical_local.yaml` で `run` すると、legacy packet files に加えて次を書きます。

- `canonical_orders.csv`
- `canonical_fills.csv`
- `canonical_positions.csv`
- `canonical_pnl.csv`
- `canonical_simulation_result.json`
- `sim_reconciliation.csv`
- `sim_reconciliation.json`
- `sim_reconciliation.md`

STOP 日は trade を作りませんが、zero-trade canonical artifact と reconciliation は書きます。

## 実行方法

1 日分の opt-in canonical shadow は次です。

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_canonical_local.yaml
```

default profile をそのまま比較対象として回す場合は次です。

```bash
python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml
```

## Reconciliation の読み方

`sim_reconciliation.md` は少なくとも次を確認するための human-readable summary です。

- `legacy_net_return`
- `canonical_net_return`
- `net_return_diff_bps`
- `legacy_gross_exposure`
- `canonical_gross_exposure`
- `legacy_cost_return`
- `canonical_cost_return`
- tolerance 内かどうか

Step 04B では tolerance breach は advisory が default です。差分が tolerance を超えても、`fail_on_tolerance_breach=true` にしない限り shadow run 自体は止めません。
