from __future__ import annotations

from leadlag.broker.models import OrderIntent, OrderSide, OrderType, TimeInForce, dataclass_to_payload


def test_order_intent_serializes_enums() -> None:
    intent = OrderIntent(
        run_id="run-1",
        trade_date="2025-11-28",
        symbol="1619.T",
        market="JP",
        side=OrderSide.BUY,
        quantity=10.0,
        notional_jpy=100000.0,
        order_type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        strategy_id="PCA_SUB",
        source_packet_path="runs/example",
        metadata={"close_side": "SELL"},
    )

    payload = dataclass_to_payload(intent)
    assert payload["side"] == "BUY"
    assert payload["order_type"] == "MARKET"
    assert payload["tif"] == "DAY"
    assert payload["metadata"]["close_side"] == "SELL"
