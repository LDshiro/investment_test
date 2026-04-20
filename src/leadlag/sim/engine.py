from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from leadlag.config.models import AppConfig


@dataclass(slots=True)
class BacktestStubResult:
    returns: pd.Series
    weights: pd.DataFrame
    diagnostics: dict


def run_backtest_stub(cfg: AppConfig) -> BacktestStubResult:
    dates = pd.date_range("2025-01-01", periods=5, freq="B")
    returns = pd.Series(0.0, index=dates, name="net_return")
    weights = pd.DataFrame(index=dates)
    diagnostics = {"status": "stub"}
    return BacktestStubResult(returns=returns, weights=weights, diagnostics=diagnostics)
