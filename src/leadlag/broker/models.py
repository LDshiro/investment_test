from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class BrokerMode(str, Enum):
    NULL = "NULL"
    DRY_RUN = "DRY_RUN"
    PAPER = "PAPER"
    LIVE = "LIVE"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SELL_SHORT = "SELL_SHORT"
    BUY_TO_COVER = "BUY_TO_COVER"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    MARKET_ON_CLOSE = "MARKET_ON_CLOSE"
    LIMIT_ON_CLOSE = "LIMIT_ON_CLOSE"
    UNKNOWN = "UNKNOWN"


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"
    GTC = "GTC"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class OrderIntent:
    run_id: str
    trade_date: str
    symbol: str
    market: str
    side: OrderSide
    quantity: float | None = None
    notional_jpy: float | None = None
    order_type: OrderType = OrderType.MARKET
    tif: TimeInForce = TimeInForce.DAY
    limit_price: float | None = None
    strategy_id: str | None = None
    source_packet_path: str | None = None
    allow_live_submission: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrokerOrderPayload:
    broker_id: str
    broker_mode: BrokerMode
    client_order_id: str
    symbol: str
    market: str
    side: OrderSide
    quantity: float | None
    notional_jpy: float | None
    order_type: OrderType
    tif: TimeInForce
    limit_price: float | None
    source_packet_path: str | None
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrokerOrderAck:
    broker_id: str
    broker_mode: BrokerMode
    client_order_id: str
    broker_order_id: str
    ack_status: str
    message: str
    received_at: str
    payload_checksum: str
    diagnostics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrokerOrderStatus:
    broker_order_id: str
    status: str
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float | None = None
    updated_at: str | None = None
    raw_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    broker_order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    executed_at: str
    execution_id: str | None = None
    fees: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PositionSnapshot:
    broker_id: str
    account_id: str
    symbol: str
    market: str
    quantity: float
    average_price: float | None = None
    market_value: float | None = None
    currency: str = "JPY"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccountSnapshot:
    broker_id: str
    account_id: str
    broker_mode: BrokerMode
    cash_balance: float
    net_liquidation: float
    buying_power: float
    currency: str = "JPY"
    as_of: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ShortabilitySnapshot:
    broker_id: str
    symbol: str
    market: str
    is_shortable: bool
    as_of: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrokerCapabilities:
    broker_id: str
    broker_mode: BrokerMode
    supports_dry_run: bool
    supports_paper: bool
    supports_live_api: bool
    supports_shortability_check: bool
    supports_position_query: bool
    supports_order_status_query: bool
    supported_markets: list[str] = field(default_factory=list)
    supported_asset_types: list[str] = field(default_factory=list)
    order_types_known: list[OrderType] = field(default_factory=list)
    time_in_force_known: list[TimeInForce] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BrokerDiagnostic:
    severity: str
    code: str
    message: str
    details: dict[str, Any] | None = None


def serialize_for_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return serialize_for_json(asdict(value))
    if isinstance(value, dict):
        return {str(key): serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_for_json(item) for item in value]
    return value


def dataclass_to_payload(instance: Any) -> dict[str, Any]:
    if not is_dataclass(instance):
        raise TypeError("dataclass_to_payload expects a dataclass instance")
    return serialize_for_json(asdict(instance))
