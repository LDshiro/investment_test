from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json

import pandas as pd
from pandas.errors import EmptyDataError

from .models import (
    BrokerMode,
    OrderIntent,
    OrderSide,
    OrderType,
    TimeInForce,
    dataclass_to_payload,
)
from .null_adapter import NullBrokerAdapter, ack_record, payload_record
from .validation import BrokerConfigError, load_broker_candidate_config


class BrokerDryRunError(RuntimeError):
    pass


def load_packet_order_inputs(packet_dir: str | Path, *, allow_empty_orders: bool = False) -> tuple[Path, dict[str, Any], pd.DataFrame]:
    packet_path = Path(packet_dir).resolve()
    run_meta, orders_df = _load_packet_requirements(packet_path, allow_empty_orders=allow_empty_orders)
    return packet_path, run_meta, orders_df


def _load_packet_requirements(packet_dir: Path, *, allow_empty_orders: bool = False) -> tuple[dict[str, Any], pd.DataFrame]:
    run_path = packet_dir / "run.json"
    orders_path = packet_dir / "orders_shadow.csv"
    if not run_path.exists():
        raise BrokerDryRunError(f"run.json not found under packet dir: {packet_dir}")
    if not orders_path.exists():
        raise BrokerDryRunError(f"orders_shadow.csv not found under packet dir: {packet_dir}")

    run_meta = json.loads(run_path.read_text(encoding="utf-8"))
    try:
        orders_df = pd.read_csv(orders_path)
    except EmptyDataError:
        if allow_empty_orders:
            orders_df = pd.DataFrame()
        else:
            raise BrokerDryRunError(f"orders_shadow.csv is empty: {orders_path}") from None
    if orders_df.empty and not allow_empty_orders:
        raise BrokerDryRunError(f"orders_shadow.csv is empty: {orders_path}")
    return run_meta, orders_df


def _map_market(symbol: str) -> str:
    return "JP" if symbol.endswith(".T") else "US"


def _map_order_side(open_side: str, close_side: str | None) -> OrderSide:
    open_norm = str(open_side).upper()
    close_norm = str(close_side or "").upper()
    if open_norm == "BUY":
        return OrderSide.BUY
    if open_norm == "SELL" and close_norm == "BUY_TO_COVER":
        return OrderSide.SELL_SHORT
    if open_norm == "SELL":
        return OrderSide.SELL
    if open_norm == "BUY_TO_COVER":
        return OrderSide.BUY_TO_COVER
    raise BrokerDryRunError(f"unsupported order side in packet: {open_side}")


def _nullable_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _build_notional_jpy(row: pd.Series) -> float | None:
    explicit = _nullable_float(row.get("target_notional_jpy"))
    if explicit is not None:
        return explicit
    quantity = _nullable_float(row.get("intended_open_qty"))
    open_price = _nullable_float(row.get("open_price_adj"))
    if quantity is None or open_price is None:
        return None
    return float(quantity) * float(open_price)


def packet_row_metadata(row: pd.Series) -> dict[str, Any]:
    return {
        "close_side": None if pd.isna(row.get("close_side")) else str(row.get("close_side")),
        "intended_close_qty": _nullable_float(row.get("intended_close_qty")),
        "open_price_adj": _nullable_float(row.get("open_price_adj")),
        "close_price_adj": _nullable_float(row.get("close_price_adj")),
        "target_weight": _nullable_float(row.get("target_weight")),
    }


def intent_from_order_row(row: pd.Series, *, run_meta: dict[str, Any], packet_path: str | Path) -> OrderIntent:
    symbol = str(row["ticker"])
    quantity = _nullable_float(row.get("intended_open_qty"))
    if quantity is None or quantity <= 0:
        raise BrokerDryRunError(f"invalid intended_open_qty for symbol {symbol}: {row.get('intended_open_qty')}")
    return OrderIntent(
        run_id=str(run_meta["run_id"]),
        trade_date=str(run_meta["trade_date"]),
        symbol=symbol,
        market=_map_market(symbol),
        side=_map_order_side(str(row["side"]), row.get("close_side")),
        quantity=quantity,
        notional_jpy=_build_notional_jpy(row),
        order_type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        limit_price=None,
        strategy_id=run_meta.get("strategy"),
        source_packet_path=str(Path(packet_path).resolve()),
        allow_live_submission=False,
        metadata=packet_row_metadata(row),
    )


def intents_from_packet(packet_dir: str | Path) -> tuple[dict[str, Any], list[OrderIntent]]:
    packet_path, run_meta, orders_df = load_packet_order_inputs(packet_dir, allow_empty_orders=False)

    intents: list[OrderIntent] = []
    for _, row in orders_df.iterrows():
        intents.append(intent_from_order_row(row, run_meta=run_meta, packet_path=packet_path))
    return run_meta, intents


def intent_record(intent: OrderIntent) -> dict[str, Any]:
    record = dataclass_to_payload(intent)
    record["metadata_json"] = json.dumps(record.pop("metadata"), ensure_ascii=False, sort_keys=True)
    return record


def broker_dryrun_from_packet(packet_dir: str | Path, broker_config_path: str | Path, output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    broker_cfg = load_broker_candidate_config(broker_config_path)
    if broker_cfg["broker_id"] != "null_broker_v1":
        raise BrokerConfigError("Step 09 broker_dryrun_from_packet only supports null_broker_v1")

    run_meta, intents = intents_from_packet(packet_dir)
    adapter = NullBrokerAdapter(
        broker_id=broker_cfg["broker_id"],
        mode=BrokerMode.DRY_RUN,
        config=broker_cfg,
    )

    payload_rows: list[dict[str, Any]] = []
    ack_rows: list[dict[str, Any]] = []
    for intent in intents:
        payload_rows.append(payload_record(adapter.prepare_order_payload(intent)))
        ack_rows.append(ack_record(adapter.dry_run_order(intent)))

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    intents_csv = out_dir / "broker_order_intents.csv"
    payloads_csv = out_dir / "broker_payloads.csv"
    acks_csv = out_dir / "broker_acks.csv"
    summary_json = out_dir / "broker_dryrun_summary.json"

    pd.DataFrame([intent_record(intent) for intent in intents]).to_csv(intents_csv, index=False)
    pd.DataFrame(payload_rows).to_csv(payloads_csv, index=False)
    pd.DataFrame(ack_rows).to_csv(acks_csv, index=False)
    summary_json.write_text(
        json.dumps(
            {
                "packet_dir": str(Path(packet_dir).resolve()),
                "broker_id": broker_cfg["broker_id"],
                "run_id": run_meta["run_id"],
                "trade_date": run_meta["trade_date"],
                "strategy_id": run_meta.get("strategy"),
                "intent_count": len(intents),
                "ack_count": len(ack_rows),
                "environment_diagnostics": [dataclass_to_payload(item) for item in adapter.validate_environment()],
                "output_paths": {
                    "broker_order_intents_csv": str(intents_csv),
                    "broker_payloads_csv": str(payloads_csv),
                    "broker_acks_csv": str(acks_csv),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    status = {
        "output_dir": str(out_dir),
        "packet_dir": str(Path(packet_dir).resolve()),
        "broker_id": broker_cfg["broker_id"],
        "intent_count": len(intents),
        "ack_count": len(ack_rows),
    }
    return out_dir, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a historical shadow packet into broker-neutral dry-run artifacts.")
    parser.add_argument("--packet-dir", required=True, help="Historical shadow packet directory")
    parser.add_argument("--broker-config", required=True, help="Broker candidate config YAML")
    parser.add_argument("--output-dir", required=True, help="Directory for dry-run artifacts")
    args = parser.parse_args(argv)

    out_dir, status = broker_dryrun_from_packet(args.packet_dir, args.broker_config, args.output_dir)
    print(f"broker dry-run completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
