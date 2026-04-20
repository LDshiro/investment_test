from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json

from .models import (
    AccountSnapshot,
    BrokerCapabilities,
    BrokerDiagnostic,
    BrokerMode,
    BrokerOrderAck,
    BrokerOrderPayload,
    BrokerOrderStatus,
    OrderIntent,
    OrderType,
    ShortabilitySnapshot,
    TimeInForce,
    PositionSnapshot,
    dataclass_to_payload,
)
from .validation import raise_for_error_diagnostics, validate_order_intent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NullBrokerAdapter:
    def __init__(self, *, broker_id: str = "null_broker_v1", mode: BrokerMode = BrokerMode.NULL, config: dict[str, Any] | None = None) -> None:
        if mode not in {BrokerMode.NULL, BrokerMode.DRY_RUN}:
            raise ValueError("NullBrokerAdapter only supports NULL or DRY_RUN mode in Step 09")
        self.broker_id = broker_id
        self.mode = mode
        self.config = dict(config or {})
        self._status_store: dict[str, BrokerOrderStatus] = {}

    def _intent_digest(self, intent: OrderIntent) -> str:
        payload = {
            "broker_id": self.broker_id,
            "run_id": intent.run_id,
            "trade_date": intent.trade_date,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "quantity": intent.quantity,
            "order_type": intent.order_type.value,
            "tif": intent.tif.value,
            "source_packet_path": intent.source_packet_path,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return sha256(serialized.encode("utf-8")).hexdigest()

    def get_capabilities(self) -> BrokerCapabilities:
        order_types = [
            OrderType.MARKET,
            OrderType.LIMIT,
            OrderType.MARKET_ON_CLOSE,
            OrderType.LIMIT_ON_CLOSE,
            OrderType.UNKNOWN,
        ]
        tif_values = [
            TimeInForce.DAY,
            TimeInForce.IOC,
            TimeInForce.FOK,
            TimeInForce.GTC,
            TimeInForce.UNKNOWN,
        ]
        return BrokerCapabilities(
            broker_id=self.broker_id,
            broker_mode=self.mode,
            supports_dry_run=True,
            supports_paper=False,
            supports_live_api=False,
            supports_shortability_check=False,
            supports_position_query=True,
            supports_order_status_query=True,
            supported_markets=list(self.config.get("supported_markets", ["JP", "US"])),
            supported_asset_types=list(self.config.get("supported_asset_types", ["equity", "etf"])),
            order_types_known=order_types,
            time_in_force_known=tif_values,
            notes=[
                "Dry-run only adapter.",
                "Never opens sockets or sends network requests.",
            ],
        )

    def validate_environment(self) -> list[BrokerDiagnostic]:
        return [
            BrokerDiagnostic(
                severity="INFO",
                code="null_adapter_no_network",
                message="NullBrokerAdapter does not use network connections or credentials.",
            ),
            BrokerDiagnostic(
                severity="INFO",
                code="null_adapter_fail_closed",
                message=f"NullBrokerAdapter mode is {self.mode.value} and will fail closed outside NULL/DRY_RUN.",
            ),
        ]

    def prepare_order_payload(self, intent: OrderIntent) -> BrokerOrderPayload:
        diagnostics = validate_order_intent(intent, adapter_mode=self.mode)
        raise_for_error_diagnostics(diagnostics, context="prepare_order_payload rejected unsafe order intent")

        digest = self._intent_digest(intent)
        payload = {
            "broker_id": self.broker_id,
            "broker_mode": self.mode.value,
            "client_order_id": f"DRYRUN-CLIENT-{digest[:16]}",
            "symbol": intent.symbol,
            "market": intent.market,
            "side": intent.side.value,
            "quantity": intent.quantity,
            "notional_jpy": intent.notional_jpy,
            "order_type": intent.order_type.value,
            "tif": intent.tif.value,
            "limit_price": intent.limit_price,
            "allow_live_submission": intent.allow_live_submission,
            "source_packet_path": intent.source_packet_path,
            "metadata": intent.metadata,
        }
        return BrokerOrderPayload(
            broker_id=self.broker_id,
            broker_mode=self.mode,
            client_order_id=payload["client_order_id"],
            symbol=intent.symbol,
            market=intent.market,
            side=intent.side,
            quantity=intent.quantity,
            notional_jpy=intent.notional_jpy,
            order_type=intent.order_type,
            tif=intent.tif,
            limit_price=intent.limit_price,
            source_packet_path=intent.source_packet_path,
            payload=payload,
            metadata={
                "payload_checksum": digest,
                "diagnostics": [diag.code for diag in diagnostics],
            },
        )

    def dry_run_order(self, intent: OrderIntent) -> BrokerOrderAck:
        prepared = self.prepare_order_payload(intent)
        digest = prepared.metadata["payload_checksum"]
        broker_order_id = f"DRYRUN-ORDER-{digest[:20]}"
        ack = BrokerOrderAck(
            broker_id=self.broker_id,
            broker_mode=self.mode,
            client_order_id=prepared.client_order_id,
            broker_order_id=broker_order_id,
            ack_status="accepted_dryrun",
            message="Order accepted by NullBrokerAdapter dry-run path.",
            received_at=_utc_now(),
            payload_checksum=digest,
            diagnostics=["no_network_requests", "live_submission_disabled"],
            metadata={
                "payload": prepared.payload,
            },
        )
        self._status_store[broker_order_id] = BrokerOrderStatus(
            broker_order_id=broker_order_id,
            status="DRY_RUN_ACCEPTED",
            filled_quantity=0.0,
            remaining_quantity=float(intent.quantity or 0.0),
            average_fill_price=None,
            updated_at=ack.received_at,
            raw_status="accepted_dryrun",
            metadata={"client_order_id": prepared.client_order_id},
        )
        return ack

    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        return self._status_store.get(
            broker_order_id,
            BrokerOrderStatus(
                broker_order_id=broker_order_id,
                status="UNKNOWN",
                updated_at=_utc_now(),
                raw_status="unknown",
            ),
        )

    def get_positions(self) -> list[PositionSnapshot]:
        return []

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            broker_id=self.broker_id,
            account_id="DRYRUN",
            broker_mode=self.mode,
            cash_balance=0.0,
            net_liquidation=0.0,
            buying_power=0.0,
            as_of=_utc_now(),
            metadata={"adapter": "NullBrokerAdapter"},
        )

    def get_shortability(self, symbols: list[str]) -> list[ShortabilitySnapshot]:
        return [
            ShortabilitySnapshot(
                broker_id=self.broker_id,
                symbol=symbol,
                market="UNKNOWN",
                is_shortable=False,
                as_of=_utc_now(),
                notes="Null dry-run adapter does not query real shortability.",
            )
            for symbol in symbols
        ]


def payload_record(payload: BrokerOrderPayload) -> dict[str, Any]:
    item = dataclass_to_payload(payload)
    item["payload_json"] = json.dumps(item.pop("payload"), ensure_ascii=False, sort_keys=True)
    item["metadata_json"] = json.dumps(item.pop("metadata"), ensure_ascii=False, sort_keys=True)
    return item


def ack_record(ack: BrokerOrderAck) -> dict[str, Any]:
    item = dataclass_to_payload(ack)
    item["diagnostics"] = ";".join(item.get("diagnostics", []))
    item["metadata_json"] = json.dumps(item.pop("metadata"), ensure_ascii=False, sort_keys=True)
    return item
