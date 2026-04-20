from __future__ import annotations

import pytest

from leadlag.broker import BrokerMode, NullBrokerAdapter, OrderIntent, OrderSide
from leadlag.broker.validation import BrokerValidationError


def _intent(*, allow_live_submission: bool = False) -> OrderIntent:
    return OrderIntent(
        run_id="run-1",
        trade_date="2025-11-28",
        symbol="1619.T",
        market="JP",
        side=OrderSide.BUY,
        quantity=10.0,
        notional_jpy=100000.0,
        strategy_id="PCA_SUB",
        source_packet_path="runs/example_packet",
        allow_live_submission=allow_live_submission,
        metadata={"close_side": "SELL"},
    )


def test_null_adapter_rejects_live_and_paper_modes() -> None:
    with pytest.raises(ValueError):
        NullBrokerAdapter(mode=BrokerMode.LIVE)
    with pytest.raises(ValueError):
        NullBrokerAdapter(mode=BrokerMode.PAPER)


def test_allow_live_submission_is_rejected() -> None:
    adapter = NullBrokerAdapter(mode=BrokerMode.DRY_RUN)
    with pytest.raises(BrokerValidationError):
        adapter.prepare_order_payload(_intent(allow_live_submission=True))


def test_fake_broker_order_ids_are_deterministic() -> None:
    adapter = NullBrokerAdapter(mode=BrokerMode.DRY_RUN)
    ack1 = adapter.dry_run_order(_intent())
    ack2 = adapter.dry_run_order(_intent())
    assert ack1.broker_order_id == ack2.broker_order_id
    assert ack1.client_order_id == ack2.client_order_id
    assert ack1.payload_checksum == ack2.payload_checksum


def test_null_adapter_requires_no_credentials() -> None:
    adapter = NullBrokerAdapter(mode=BrokerMode.DRY_RUN)
    diagnostics = adapter.validate_environment()
    assert diagnostics
    assert any(item.code == "null_adapter_no_network" for item in diagnostics)
