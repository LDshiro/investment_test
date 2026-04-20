from __future__ import annotations

from leadlag.broker.base import OrderIntent


class NullBroker:
    def submit(self, order: OrderIntent) -> dict:
        return {"status": "accepted_dryrun", "ticker": order.ticker, "qty": order.qty}

    def cancel_all(self) -> list[dict]:
        return []
