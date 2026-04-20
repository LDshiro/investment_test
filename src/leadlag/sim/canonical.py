from __future__ import annotations

from dataclasses import asdict
from math import floor
from typing import Any

import pandas as pd

from leadlag.sim.models import (
    OrderIntent,
    PnLBreakdown,
    PositionSnapshot,
    SimulatedFill,
    SimulationConfig,
    SimulationResult,
)

ORDER_COLUMNS = [
    "trade_date",
    "ticker",
    "target_weight",
    "target_notional_jpy",
    "side",
    "entry_price",
    "exit_price",
    "expected_oc_return",
]

FILL_COLUMNS = [
    "trade_date",
    "ticker",
    "leg",
    "side",
    "quantity",
    "price",
    "notional_jpy",
    "cost_bps",
    "cost_jpy",
]

POSITION_COLUMNS = [
    "trade_date",
    "ticker",
    "weight",
    "quantity",
    "entry_price",
    "exit_price",
    "gross_pnl_jpy",
    "cost_jpy",
    "net_pnl_jpy",
    "gross_return",
    "net_return_contribution",
    "entry_cost_jpy",
    "exit_cost_jpy",
    "borrow_cost_jpy",
    "expected_oc_return",
]

PNL_COLUMNS = [
    "trade_date",
    "nav_start_jpy",
    "nav_end_jpy",
    "gross_pnl_jpy",
    "cost_jpy",
    "borrow_cost_jpy",
    "net_pnl_jpy",
    "gross_return",
    "cost_return",
    "net_return",
    "gross_exposure",
    "net_exposure",
    "turnover_entry",
    "turnover_exit",
    "n_positions",
    "execution_cost_jpy",
    "status",
]


def _empty_pnl(trade_date: str, nav_start_jpy: float, *, gross_exposure: float = 0.0, net_exposure: float = 0.0) -> PnLBreakdown:
    return PnLBreakdown(
        trade_date=trade_date,
        nav_start_jpy=nav_start_jpy,
        nav_end_jpy=nav_start_jpy,
        gross_pnl_jpy=0.0,
        cost_jpy=0.0,
        borrow_cost_jpy=0.0,
        net_pnl_jpy=0.0,
        gross_return=0.0,
        cost_return=0.0,
        net_return=0.0,
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        turnover_entry=0.0,
        turnover_exit=0.0,
        n_positions=0,
        execution_cost_jpy=0.0,
    )


def build_zero_trade_result(
    *,
    trade_date: str,
    nav_start_jpy: float,
    status: str = "STOP",
    notes: list[str] | None = None,
    diagnostics: dict[str, Any] | None = None,
    gross_exposure: float = 0.0,
    net_exposure: float = 0.0,
    entry_cost_bps: float = 0.0,
    exit_cost_bps: float = 0.0,
    borrow_fee_bps_annual: float = 0.0,
    annualization_days: int = 252,
    allow_fractional_quantity: bool = True,
) -> SimulationResult:
    config = SimulationConfig(
        trade_date=trade_date,
        nav_start_jpy=nav_start_jpy,
        entry_cost_bps=entry_cost_bps,
        exit_cost_bps=exit_cost_bps,
        borrow_fee_bps_annual=borrow_fee_bps_annual,
        annualization_days=annualization_days,
        allow_fractional_quantity=allow_fractional_quantity,
    )
    return SimulationResult(
        config=config,
        status=status,
        pnl=_empty_pnl(trade_date, nav_start_jpy, gross_exposure=gross_exposure, net_exposure=net_exposure),
        diagnostics=diagnostics or {},
        notes=notes or [],
    )


def _require_price_data(weights: pd.Series, open_prices: pd.Series, close_prices: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    non_zero = weights[weights != 0.0].astype(float)
    if non_zero.empty:
        return non_zero, open_prices.astype(float), close_prices.astype(float)

    missing: list[str] = []
    open_aligned = open_prices.reindex(non_zero.index).astype(float)
    close_aligned = close_prices.reindex(non_zero.index).astype(float)
    for ticker in non_zero.index:
        open_px = open_aligned.loc[ticker]
        close_px = close_aligned.loc[ticker]
        if pd.isna(open_px) or pd.isna(close_px) or open_px <= 0.0 or close_px <= 0.0:
            missing.append(str(ticker))
    if missing:
        raise ValueError(f"Missing or invalid open/close prices for selected names: {', '.join(missing)}")
    return non_zero, open_aligned, close_aligned


def simulate_intraday_open_close(
    *,
    trade_date: str,
    weights: pd.Series,
    open_prices: pd.Series,
    close_prices: pd.Series,
    nav_start_jpy: float,
    entry_cost_bps: float,
    exit_cost_bps: float,
    borrow_fee_bps_annual: float = 0.0,
    annualization_days: int = 252,
    allow_fractional_quantity: bool = True,
) -> SimulationResult:
    weights_nz, open_aligned, close_aligned = _require_price_data(weights, open_prices, close_prices)
    gross_exposure = float(weights_nz.abs().sum()) if not weights_nz.empty else 0.0
    net_exposure = float(weights_nz.sum()) if not weights_nz.empty else 0.0
    if weights_nz.empty:
        return build_zero_trade_result(
            trade_date=trade_date,
            nav_start_jpy=nav_start_jpy,
            status="NO_TRADE",
            notes=["No non-zero target weights."],
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            entry_cost_bps=entry_cost_bps,
            exit_cost_bps=exit_cost_bps,
            borrow_fee_bps_annual=borrow_fee_bps_annual,
            annualization_days=annualization_days,
            allow_fractional_quantity=allow_fractional_quantity,
        )

    config = SimulationConfig(
        trade_date=trade_date,
        nav_start_jpy=nav_start_jpy,
        entry_cost_bps=entry_cost_bps,
        exit_cost_bps=exit_cost_bps,
        borrow_fee_bps_annual=borrow_fee_bps_annual,
        annualization_days=annualization_days,
        allow_fractional_quantity=allow_fractional_quantity,
    )

    orders: list[OrderIntent] = []
    fills: list[SimulatedFill] = []
    positions: list[PositionSnapshot] = []
    diagnostics: dict[str, Any] = {
        "rounded_quantity_tickers": [],
        "rounding_residual_notional_jpy": {},
    }

    gross_pnl_total = 0.0
    execution_cost_total = 0.0
    borrow_cost_total = 0.0
    turnover_entry = 0.0
    turnover_exit = 0.0

    for ticker, weight in weights_nz.items():
        open_px = float(open_aligned.loc[ticker])
        close_px = float(close_aligned.loc[ticker])
        expected_oc_return = float(close_px / open_px - 1.0)
        signed_target_notional = float(nav_start_jpy * float(weight))
        qty = signed_target_notional / open_px
        if not allow_fractional_quantity:
            qty_abs = floor(abs(qty))
            rounded_qty = qty_abs if qty >= 0.0 else -qty_abs
            if rounded_qty != qty:
                diagnostics["rounded_quantity_tickers"].append(str(ticker))
                diagnostics["rounding_residual_notional_jpy"][str(ticker)] = float(
                    abs(signed_target_notional) - abs(rounded_qty * open_px)
                )
            qty = rounded_qty

        if qty == 0.0:
            diagnostics["rounding_residual_notional_jpy"][str(ticker)] = float(abs(signed_target_notional))
            continue

        entry_notional = abs(qty * open_px)
        exit_notional = abs(qty * close_px)
        entry_cost_jpy = entry_notional * entry_cost_bps / 10000.0
        exit_cost_jpy = exit_notional * exit_cost_bps / 10000.0
        borrow_cost_jpy = (
            abs(signed_target_notional) * (borrow_fee_bps_annual / float(annualization_days)) / 10000.0
            if qty < 0.0 and borrow_fee_bps_annual > 0.0
            else 0.0
        )
        gross_pnl_jpy = qty * (close_px - open_px)
        total_cost_jpy = entry_cost_jpy + exit_cost_jpy + borrow_cost_jpy
        net_pnl_jpy = gross_pnl_jpy - total_cost_jpy

        gross_pnl_total += gross_pnl_jpy
        execution_cost_total += entry_cost_jpy + exit_cost_jpy
        borrow_cost_total += borrow_cost_jpy
        turnover_entry += entry_notional / nav_start_jpy
        turnover_exit += exit_notional / nav_start_jpy

        order_side = "long" if weight > 0.0 else "short"
        entry_side = "buy" if qty > 0.0 else "sell_short"
        exit_side = "sell" if qty > 0.0 else "buy_to_cover"

        orders.append(
            OrderIntent(
                trade_date=trade_date,
                ticker=str(ticker),
                target_weight=float(weight),
                target_notional_jpy=signed_target_notional,
                side=order_side,
                entry_price=open_px,
                exit_price=close_px,
                expected_oc_return=expected_oc_return,
            )
        )
        fills.extend(
            [
                SimulatedFill(
                    trade_date=trade_date,
                    ticker=str(ticker),
                    leg="entry",
                    side=entry_side,
                    quantity=float(abs(qty)),
                    price=open_px,
                    notional_jpy=entry_notional,
                    cost_bps=entry_cost_bps,
                    cost_jpy=entry_cost_jpy,
                ),
                SimulatedFill(
                    trade_date=trade_date,
                    ticker=str(ticker),
                    leg="exit",
                    side=exit_side,
                    quantity=float(abs(qty)),
                    price=close_px,
                    notional_jpy=exit_notional,
                    cost_bps=exit_cost_bps,
                    cost_jpy=exit_cost_jpy,
                ),
            ]
        )
        positions.append(
            PositionSnapshot(
                trade_date=trade_date,
                ticker=str(ticker),
                weight=float(weight),
                quantity=float(qty),
                entry_price=open_px,
                exit_price=close_px,
                gross_pnl_jpy=gross_pnl_jpy,
                cost_jpy=total_cost_jpy,
                net_pnl_jpy=net_pnl_jpy,
                gross_return=gross_pnl_jpy / nav_start_jpy,
                net_return_contribution=net_pnl_jpy / nav_start_jpy,
                entry_cost_jpy=entry_cost_jpy,
                exit_cost_jpy=exit_cost_jpy,
                borrow_cost_jpy=borrow_cost_jpy,
                expected_oc_return=expected_oc_return,
            )
        )

    total_cost_jpy = execution_cost_total + borrow_cost_total
    net_pnl_total = gross_pnl_total - total_cost_jpy
    pnl = PnLBreakdown(
        trade_date=trade_date,
        nav_start_jpy=nav_start_jpy,
        nav_end_jpy=nav_start_jpy + net_pnl_total,
        gross_pnl_jpy=gross_pnl_total,
        cost_jpy=total_cost_jpy,
        borrow_cost_jpy=borrow_cost_total,
        net_pnl_jpy=net_pnl_total,
        gross_return=gross_pnl_total / nav_start_jpy,
        cost_return=-(total_cost_jpy / nav_start_jpy),
        net_return=net_pnl_total / nav_start_jpy,
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        turnover_entry=turnover_entry,
        turnover_exit=turnover_exit,
        n_positions=len(positions),
        execution_cost_jpy=execution_cost_total,
    )

    return SimulationResult(
        config=config,
        status="GO",
        order_intents=orders,
        fills=fills,
        positions=positions,
        pnl=pnl,
        diagnostics=diagnostics,
        notes=[],
    )


def simulation_result_frames(result: SimulationResult) -> dict[str, pd.DataFrame]:
    orders_df = pd.DataFrame([asdict(item) for item in result.order_intents]).reindex(columns=ORDER_COLUMNS)
    fills_df = pd.DataFrame([asdict(item) for item in result.fills]).reindex(columns=FILL_COLUMNS)
    positions_df = pd.DataFrame([asdict(item) for item in result.positions]).reindex(columns=POSITION_COLUMNS)
    pnl_row = asdict(result.pnl) if result.pnl is not None else {}
    pnl_row["status"] = result.status
    pnl_df = pd.DataFrame([pnl_row]).reindex(columns=PNL_COLUMNS)
    return {
        "orders": orders_df,
        "fills": fills_df,
        "positions": positions_df,
        "pnl": pnl_df,
    }


def simulation_result_payload(result: SimulationResult) -> dict[str, Any]:
    return {
        "config": asdict(result.config),
        "status": result.status,
        "orders": [asdict(item) for item in result.order_intents],
        "fills": [asdict(item) for item in result.fills],
        "positions": [asdict(item) for item in result.positions],
        "pnl": asdict(result.pnl) if result.pnl is not None else None,
        "diagnostics": result.diagnostics,
        "notes": result.notes,
    }
