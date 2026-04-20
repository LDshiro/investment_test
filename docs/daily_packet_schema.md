# Daily packet schema

毎営業日1つの packet を出力する。historical shadow run でも同じ schema を使う。

## 必須

### `summary.md`
- GO / WARN / STOP
- 最重要アラート 3件
- tradable names
- expected gross/net
- expected cost
- today vs yesterday 差分
- historical shadow では realized gross/net と paper counterfactual も併記

### `run.json`
- `run_id`
- `mode`
- `code_version`
- `config_hash`
- `data_version`
- `patch_version`
- `data_status`
- `model_status`
- `run_status`
- `started_at`
- `finished_at`
- `trade_date`
- `asof_us_date`

### `signals.csv`
- `date`
- `ticker`
- `signal_raw`
- `signal_rank`
- `tradable_flag`
- `paper_weight_raw`
- `target_weight`

### `orders_shadow.csv`
- `date`
- `ticker`
- `side`
- `target_weight`
- `intended_open_qty`
- `intended_close_qty`
- `open_price_adj`
- `close_price_adj`
- `target_notional_jpy`

### `fills_shadow.csv`
- `date`
- `ticker`
- `fill_type`
- `side`
- `qty`
- `mid_price`
- `assumed_price`
- `cost_bps`

### `positions.csv`
- `date`
- `ticker`
- `weight`
- `position_qty`
- `gross_pnl_jpy`
- `net_pnl_jpy`

### `pnl.csv`
- `date`
- `gross_return`
- `net_return`
- `cost_return`
- `gross_pnl_jpy`
- `net_pnl_jpy`
- `cost_pnl_jpy`
- `cumulative_return`

### `risk_report.json`
- `gate_results`
- `expected_cost_bps`
- `gross_exposure`
- `net_exposure`
- `max_name_abs`
- `paper_gross_exposure`
- `paper_net_exposure`

### `alerts.json`
- `alerts: [ {severity, code, message, ticker?, date?} ]`

## 任意

- `figure_signals.png`
- `figure_equity_curve.png`
