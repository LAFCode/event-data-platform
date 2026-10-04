import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from generator.generator import EventGenerator
from generator.models import OrderCreated, OrderItem

FIXED = datetime(2026, 10, 4, 16, 50, tzinfo=UTC)


def make(seed=1, **kw):
    return EventGenerator(seed=seed, clock=lambda: FIXED, **kw)


def test_event_matches_contract():
    data = json.loads(make().next_order_created().model_dump_json())
    assert set(data) == {
        "event_id", "event_type", "event_version", "event_timestamp",
        "ingestion_timestamp", "order_id", "customer_id", "items",
    }  # fmt: skip
    assert data["event_type"] == "order_created"
    assert data["event_version"] == 1
    assert data["event_timestamp"] == "2026-10-04T16:50:00Z"
    assert data["ingestion_timestamp"] is None
    assert data["order_id"] == "ORD-000001"
    assert set(data["items"][0]) == {"product_id", "quantity", "unit_price"}
    assert isinstance(data["items"][0]["unit_price"], float)


def test_event_roundtrips_through_json():
    event = make().next_order_created()
    assert OrderCreated.model_validate_json(event.model_dump_json()) == event


def test_same_seed_is_reproducible():
    a = [e.model_dump_json() for e in make(seed=7).stream(20)]
    b = [e.model_dump_json() for e in make(seed=7).stream(20)]
    assert a == b


def test_different_seed_differs():
    assert make(seed=1).next_order_created() != make(seed=2).next_order_created()


@pytest.mark.parametrize("quantity,price", [(0, "10.00"), (-1, "10.00"), (1, "0"), (1, "-5")])
def test_invalid_items_are_rejected(quantity, price):
    with pytest.raises(ValidationError):
        OrderItem(product_id="PROD-000001", quantity=quantity, unit_price=price)


def test_orders_reference_existing_catalog():
    gen = make()
    customer_ids = {c.customer_id for c in gen.customers}
    prices = {p.product_id: p.unit_price for p in gen.products}
    for event in gen.stream(500):
        assert event.customer_id in customer_ids
        assert len({i.product_id for i in event.items}) == len(event.items)
        for item in event.items:
            assert prices[item.product_id] == item.unit_price


def test_order_ids_are_sequential_and_event_ids_unique():
    events = list(make().stream(200))
    assert [e.order_id for e in events] == [f"ORD-{i:06d}" for i in range(1, 201)]
    assert len({e.event_id for e in events}) == 200
