# Broker Dry-Run Ops v1

## Purpose

Broker dry-run converts historical `orders_shadow.csv` rows into broker-neutral `OrderIntent` objects and deterministic `NullBroker` acknowledgements. This is still a shadow-only audit step. It does not place paper orders, live orders, or broker network calls.

## Why This Is Still Non-Live

- only `null_broker_v1` is allowed
- adapter mode must remain `DRY_RUN`
- `allow_live_submission` must remain `false`
- runtime safety `FAIL` blocks the batch
- no real broker credentials, sockets, or HTTP requests are used

## Packet Mapping

- each `orders_shadow.csv` row becomes one open-side broker-neutral `OrderIntent`
- `ticker -> symbol`
- `side -> side`
- `intended_open_qty -> quantity`
- `target_notional_jpy -> notional_jpy`
- default `order_type=MARKET`, `tif=DAY`
- market is inferred as `JP` for `.T` symbols and `US` otherwise

Close-leg and shadow-only fields such as `close_side`, `intended_close_qty`, `open_price_adj`, `close_price_adj`, and `target_weight` are preserved only in metadata for auditability.

## Artifacts

Per day:

- `daily/<trade_date>/broker_order_intents.csv`
- `daily/<trade_date>/broker_payloads.json`
- `daily/<trade_date>/broker_acks.json`
- `daily/<trade_date>/broker_diagnostics.json`

Batch level:

- `broker_dryrun_summary.csv`
- `broker_dryrun_summary.json`
- `broker_dryrun_summary.md`
- `broker_dryrun_validation.json`

## CLI

Standalone batch dry-run:

```bash
python -m leadlag.cli broker-dryrun-batch \
  --batch-dir runs/<batch_dir> \
  --broker-config configs/brokers/null_broker_v1.yaml \
  --dryrun-config configs/broker_dryrun/broker_dryrun_batch_v1.yaml \
  --output-dir artifacts/broker_dryrun_batch/manual_test
```

Integrated shadow-ops profile:

```bash
python -m leadlag.cli shadow-ops \
  --config configs/ops/shadow_ops_broker_dryrun_legacy_60d_local.yaml
```

## Pass / Fail Interpretation

- pass: every required packet was readable, every convertible row became an intent, every intent received a deterministic null-broker ack, and runtime safety was acceptable
- fail: missing packet files, blocked runtime safety, unsafe broker config, intent conversion failures above threshold, or missing acknowledgements

`STOP` days with an existing but empty `orders_shadow.csv` are allowed and remain pass if the packet is otherwise intact.

## Before Any Future Paper / Live Step

- runtime safety must remain green enough for the chosen environment
- real broker credentials must stay outside git
- adapter behavior must be proven in explicit paper-only testing
- AI review may assist, but it cannot be the only authorization mechanism for future order sending
