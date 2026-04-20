from __future__ import annotations

from typing import Protocol

from .models import (
    AccountSnapshot,
    BrokerCapabilities,
    BrokerDiagnostic,
    BrokerOrderAck,
    BrokerOrderPayload,
    BrokerOrderStatus,
    OrderIntent,
    ShortabilitySnapshot,
    PositionSnapshot,
)


class BrokerAdapter(Protocol):
    def get_capabilities(self) -> BrokerCapabilities: ...

    def validate_environment(self) -> list[BrokerDiagnostic]: ...

    def prepare_order_payload(self, intent: OrderIntent) -> BrokerOrderPayload: ...

    def dry_run_order(self, intent: OrderIntent) -> BrokerOrderAck: ...

    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus: ...

    def get_positions(self) -> list[PositionSnapshot]: ...

    def get_account_snapshot(self) -> AccountSnapshot: ...

    def get_shortability(self, symbols: list[str]) -> list[ShortabilitySnapshot]: ...
