from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class OrderIntent:
    ticker: str
    side: str
    qty: float
    order_type: str = "market"


class BrokerAdapter(Protocol):
    def submit(self, order: OrderIntent) -> dict: ...
    def cancel_all(self) -> list[dict]: ...
