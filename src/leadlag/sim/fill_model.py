from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FillAssumption:
    open_side_cost_bps: float
    close_side_cost_bps: float
    price_source_open: str = "open"
    price_source_close: str = "close"
