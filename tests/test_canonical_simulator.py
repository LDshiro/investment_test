from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from leadlag.config.loader import load_app_config
from leadlag.sim.canonical import build_zero_trade_result, simulate_intraday_open_close, simulation_result_frames


def test_one_long_position_zero_cost_matches_weighted_oc_return() -> None:
    result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": 0.25}),
        open_prices=pd.Series({"1617.T": 100.0}),
        close_prices=pd.Series({"1617.T": 110.0}),
        nav_start_jpy=1000.0,
        entry_cost_bps=0.0,
        exit_cost_bps=0.0,
    )
    assert result.status == "GO"
    assert result.pnl is not None
    assert result.pnl.net_return == pytest.approx(0.025)
    assert result.positions[0].net_return_contribution == pytest.approx(0.025)


def test_one_short_position_zero_cost_matches_negative_oc_return_times_abs_weight() -> None:
    result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": -0.25}),
        open_prices=pd.Series({"1617.T": 100.0}),
        close_prices=pd.Series({"1617.T": 90.0}),
        nav_start_jpy=1000.0,
        entry_cost_bps=0.0,
        exit_cost_bps=0.0,
    )
    assert result.pnl is not None
    assert result.pnl.net_return == pytest.approx(0.025)


def test_entry_and_exit_costs_reduce_net_pnl_by_expected_bps() -> None:
    result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": 1.0}),
        open_prices=pd.Series({"1617.T": 100.0}),
        close_prices=pd.Series({"1617.T": 100.0}),
        nav_start_jpy=1000.0,
        entry_cost_bps=10.0,
        exit_cost_bps=20.0,
    )
    assert result.pnl is not None
    assert result.pnl.cost_jpy == pytest.approx(3.0)
    assert result.pnl.net_pnl_jpy == pytest.approx(-3.0)
    assert result.pnl.net_return == pytest.approx(-0.003)


def test_borrow_fee_applies_only_to_short_positions() -> None:
    short_result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": -1.0}),
        open_prices=pd.Series({"1617.T": 100.0}),
        close_prices=pd.Series({"1617.T": 100.0}),
        nav_start_jpy=1000.0,
        entry_cost_bps=0.0,
        exit_cost_bps=0.0,
        borrow_fee_bps_annual=252.0,
        annualization_days=252,
    )
    long_result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": 1.0}),
        open_prices=pd.Series({"1617.T": 100.0}),
        close_prices=pd.Series({"1617.T": 100.0}),
        nav_start_jpy=1000.0,
        entry_cost_bps=0.0,
        exit_cost_bps=0.0,
        borrow_fee_bps_annual=252.0,
        annualization_days=252,
    )
    assert short_result.pnl is not None
    assert long_result.pnl is not None
    assert short_result.pnl.borrow_cost_jpy == pytest.approx(0.1)
    assert long_result.pnl.borrow_cost_jpy == pytest.approx(0.0)


def test_multiple_positions_aggregate_correctly() -> None:
    result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": 0.5, "1618.T": -0.25}),
        open_prices=pd.Series({"1617.T": 100.0, "1618.T": 100.0}),
        close_prices=pd.Series({"1617.T": 110.0, "1618.T": 90.0}),
        nav_start_jpy=1000.0,
        entry_cost_bps=0.0,
        exit_cost_bps=0.0,
    )
    assert result.pnl is not None
    assert result.pnl.n_positions == 2
    assert result.pnl.gross_exposure == pytest.approx(0.75)
    assert result.pnl.net_exposure == pytest.approx(0.25)
    assert result.pnl.net_return == pytest.approx(0.075)


def test_stop_no_trade_result_has_zero_trade_frames() -> None:
    result = build_zero_trade_result(trade_date="2025-11-28", nav_start_jpy=1000.0, status="STOP")
    frames = simulation_result_frames(result)
    assert result.status == "STOP"
    assert result.pnl is not None
    assert result.pnl.net_return == 0.0
    assert list(frames["orders"].columns) == [
        "trade_date",
        "ticker",
        "target_weight",
        "target_notional_jpy",
        "side",
        "entry_price",
        "exit_price",
        "expected_oc_return",
    ]
    assert frames["orders"].empty
    assert frames["pnl"].iloc[0]["status"] == "STOP"


def test_missing_selected_prices_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Missing or invalid open/close prices"):
        simulate_intraday_open_close(
            trade_date="2025-11-28",
            weights=pd.Series({"1617.T": 1.0}),
            open_prices=pd.Series({"1617.T": float("nan")}),
            close_prices=pd.Series({"1617.T": 100.0}),
            nav_start_jpy=1000.0,
            entry_cost_bps=0.0,
            exit_cost_bps=0.0,
        )


def test_non_fractional_mode_records_rounding_difference() -> None:
    result = simulate_intraday_open_close(
        trade_date="2025-11-28",
        weights=pd.Series({"1617.T": 0.25}),
        open_prices=pd.Series({"1617.T": 3.0}),
        close_prices=pd.Series({"1617.T": 3.3}),
        nav_start_jpy=1000.0,
        entry_cost_bps=0.0,
        exit_cost_bps=0.0,
        allow_fractional_quantity=False,
    )
    assert result.positions[0].quantity == pytest.approx(83.0)
    assert "1617.T" in result.diagnostics["rounded_quantity_tickers"]
    assert result.diagnostics["rounding_residual_notional_jpy"]["1617.T"] == pytest.approx(1.0)


def test_default_and_canonical_profiles_validate() -> None:
    default_cfg = load_app_config(Path("configs/profiles/shadow_corrected_local.yaml"))
    canonical_cfg = load_app_config(Path("configs/profiles/shadow_corrected_canonical_local.yaml"))
    assert default_cfg.simulator.enabled is False
    assert canonical_cfg.simulator.enabled is True
    assert canonical_cfg.simulator.write_canonical_artifacts is True
