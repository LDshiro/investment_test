from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SimulationConfig:
    trade_date: str
    nav_start_jpy: float
    entry_cost_bps: float
    exit_cost_bps: float
    borrow_fee_bps_annual: float = 0.0
    annualization_days: int = 252
    allow_fractional_quantity: bool = True
    cost_application: str = "separate_cash_cost"
    entry_price_source: str = "adjusted_open"
    exit_price_source: str = "adjusted_close"


@dataclass(slots=True)
class OrderIntent:
    trade_date: str
    ticker: str
    target_weight: float
    target_notional_jpy: float
    side: str
    entry_price: float
    exit_price: float
    expected_oc_return: float


@dataclass(slots=True)
class SimulatedFill:
    trade_date: str
    ticker: str
    leg: str
    side: str
    quantity: float
    price: float
    notional_jpy: float
    cost_bps: float
    cost_jpy: float


@dataclass(slots=True)
class PositionSnapshot:
    trade_date: str
    ticker: str
    weight: float
    quantity: float
    entry_price: float
    exit_price: float
    gross_pnl_jpy: float
    cost_jpy: float
    net_pnl_jpy: float
    gross_return: float
    net_return_contribution: float
    entry_cost_jpy: float = 0.0
    exit_cost_jpy: float = 0.0
    borrow_cost_jpy: float = 0.0
    expected_oc_return: float = 0.0


@dataclass(slots=True)
class PnLBreakdown:
    trade_date: str
    nav_start_jpy: float
    nav_end_jpy: float
    gross_pnl_jpy: float
    cost_jpy: float
    borrow_cost_jpy: float
    net_pnl_jpy: float
    gross_return: float
    cost_return: float
    net_return: float
    gross_exposure: float
    net_exposure: float
    turnover_entry: float
    turnover_exit: float
    n_positions: int
    execution_cost_jpy: float = 0.0


@dataclass(slots=True)
class SimulationResult:
    config: SimulationConfig
    status: str
    order_intents: list[OrderIntent] = field(default_factory=list)
    fills: list[SimulatedFill] = field(default_factory=list)
    positions: list[PositionSnapshot] = field(default_factory=list)
    pnl: PnLBreakdown | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReconciliationResult:
    trade_date: str
    legacy_net_return: float
    canonical_net_return: float
    net_return_diff: float
    net_return_diff_bps: float
    legacy_gross_exposure: float
    canonical_gross_exposure: float
    legacy_cost_return: float | None
    canonical_cost_return: float
    status: str
    notes: list[str] = field(default_factory=list)
    tolerance_net_return_bps: float = 1.0
    within_tolerance: bool = True
    diagnostics: dict[str, Any] = field(default_factory=dict)


def dataclass_to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
