from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


def _fmt_ret(x: float | None) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return f"{x * 100.0:.2f}%"


def _fmt_list(rows: Iterable[tuple[str, float]]) -> str:
    items = []
    for ticker, value in rows:
        items.append(f"- {ticker}: {value:.4f}")
    return "\n".join(items) if items else "- none"


def build_daily_summary(
    status: str,
    alerts: list[dict],
    expected_cost_bps: float,
    **kwargs,
) -> str:
    run_name = kwargs.get("run_name")
    strategy = kwargs.get("strategy")
    trade_date = kwargs.get("trade_date")
    us_date = kwargs.get("us_date")
    tradable_names = kwargs.get("tradable_names")
    selected_names = kwargs.get("selected_names")
    gross_exposure = kwargs.get("gross_exposure")
    net_exposure = kwargs.get("net_exposure")
    shadow_nav_jpy = kwargs.get("shadow_nav_jpy")
    realized_gross_return = kwargs.get("realized_gross_return")
    realized_net_return = kwargs.get("realized_net_return")
    paper_counterfactual_return = kwargs.get("paper_counterfactual_return")
    prev_trade_date = kwargs.get("prev_trade_date")
    changed_names = kwargs.get("changed_names")
    signal_spread = kwargs.get("signal_spread")
    prev_signal_spread = kwargs.get("prev_signal_spread")
    top_longs = kwargs.get("top_longs") or []
    top_shorts = kwargs.get("top_shorts") or []

    lines = [f"# {run_name or 'Daily summary'}", ""]
    lines.append(f"Status: **{status}**")
    if strategy:
        lines.append(f"Strategy: **{strategy}**")
    if trade_date is not None:
        lines.append(f"Trade date (JP): **{pd.Timestamp(trade_date).date()}**")
    if us_date is not None:
        lines.append(f"As-of U.S. date: **{pd.Timestamp(us_date).date()}**")
    if shadow_nav_jpy is not None:
        lines.append(f"Shadow NAV: **JPY {shadow_nav_jpy:,.0f}**")
    lines.append("")
    lines.append("## Core diagnostics")
    lines.append("")
    if tradable_names is not None:
        lines.append(f"- tradable names: {tradable_names}")
    if selected_names is not None:
        lines.append(f"- selected names: {selected_names}")
    if gross_exposure is not None:
        lines.append(f"- gross exposure: {gross_exposure:.4f}")
    if net_exposure is not None:
        lines.append(f"- net exposure: {net_exposure:.4f}")
    lines.append(f"- expected round-trip cost: {expected_cost_bps:.2f} bps")
    lines.append(f"- realized gross return: {_fmt_ret(realized_gross_return)}")
    lines.append(f"- realized net return: {_fmt_ret(realized_net_return)}")
    lines.append(f"- paper counterfactual return: {_fmt_ret(paper_counterfactual_return)}")
    lines.append("")
    lines.append("## Today vs previous trade date")
    lines.append("")
    if prev_trade_date is not None:
        lines.append(f"- previous trade date: {pd.Timestamp(prev_trade_date).date()}")
    else:
        lines.append("- previous trade date: n/a")
    if changed_names is not None:
        lines.append(f"- changed selected names: {changed_names}")
    if signal_spread is not None and math.isfinite(signal_spread):
        if prev_signal_spread is not None and math.isfinite(prev_signal_spread):
            lines.append(f"- signal spread: {signal_spread:.4f} (prev {prev_signal_spread:.4f}, delta {signal_spread - prev_signal_spread:+.4f})")
        else:
            lines.append(f"- signal spread: {signal_spread:.4f}")
    lines.append("")
    lines.append("## Top longs by signal")
    lines.append("")
    lines.append(_fmt_list(top_longs))
    lines.append("")
    lines.append("## Bottom names by signal")
    lines.append("")
    lines.append(_fmt_list(top_shorts))
    lines.append("")
    lines.append("## Alerts")
    lines.append("")
    if alerts:
        for alert in alerts[:10]:
            lines.append(f"- [{alert.get('severity', 'info')}] {alert.get('code', 'unknown')}: {alert.get('message', '')}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
