# Broker Adapter Contract v1

Step 09 defines a broker-neutral adapter contract without adding any live order
submission path.

## Core idea

- The adapter layer consumes already-generated order intents or historical
  `orders_shadow.csv` rows.
- It normalizes them into broker-neutral payloads and dry-run acknowledgements.
- It does not decide trades, prices, weights, or gate outcomes.

## Internal models

The broker package defines typed models for:

- `BrokerMode`
- `OrderSide`
- `OrderType`
- `TimeInForce`
- `OrderIntent`
- `BrokerOrderPayload`
- `BrokerOrderAck`
- `BrokerOrderStatus`
- `ExecutionReport`
- `PositionSnapshot`
- `AccountSnapshot`
- `ShortabilitySnapshot`
- `BrokerCapabilities`
- `BrokerDiagnostic`

`OrderIntent` is the main broker-neutral input. It carries:

- `run_id`
- `trade_date`
- `symbol`
- `market`
- `side`
- `quantity`
- `notional_jpy`
- `order_type`
- `tif`
- `limit_price`
- `strategy_id`
- `source_packet_path`
- `allow_live_submission`
- `metadata`

## Base adapter protocol

Concrete adapters implement:

- `get_capabilities()`
- `validate_environment()`
- `prepare_order_payload(intent)`
- `dry_run_order(intent)`
- `get_order_status(broker_order_id)`
- `get_positions()`
- `get_account_snapshot()`
- `get_shortability(symbols)`

There is intentionally no live submitter in Step 09.

## Packet mapping policy

Historical packet dry-run uses the **open-side only** mapping from
`orders_shadow.csv`.

Each row becomes one `OrderIntent`:

- `ticker -> symbol`
- `side -> side`
- `intended_open_qty -> quantity`
- `target_notional_jpy -> notional_jpy`
- `order_type = MARKET`
- `tif = DAY`
- `limit_price = None`
- `market = JP` for `.T`, otherwise `US`

Audit-only metadata preserves:

- `close_side`
- `intended_close_qty`
- `open_price_adj`
- `close_price_adj`
- `target_weight`

This keeps Step 09 aligned with a future pre-open broker flow without claiming
that same-day exit behavior can be automated yet.

## Null adapter behavior

`NullBrokerAdapter`:

- only supports `NULL` and `DRY_RUN`
- rejects `allow_live_submission=True`
- generates deterministic fake broker IDs
- returns local payloads, acks, and statuses
- never opens sockets, reads credentials, or sends network requests

The older `leadlag.broker.null.NullBroker` name is retained only as a thin
compatibility shim to the dry-run adapter.
