"""Factories for business events."""

import random
from datetime import datetime

from ulid import ULID

from generator.models import (
    Customer,
    OrderCancelled,
    OrderCreated,
    OrderDelivered,
    OrderEvent,
    OrderItem,
    OrderPaid,
    OrderShipped,
)
from generator.state_machine import OrderState

EVENT_FOR_STATE: dict[OrderState, type[OrderEvent]] = {
    OrderState.CREATED: OrderCreated,
    OrderState.PAID: OrderPaid,
    OrderState.SHIPPED: OrderShipped,
    OrderState.DELIVERED: OrderDelivered,
    OrderState.CANCELLED: OrderCancelled,
}


def new_event_id(rng: random.Random, timestamp: datetime) -> str:
    """Build a ULID from the event time plus seeded randomness (reproducible)."""
    millis = int(timestamp.timestamp() * 1000)
    raw = millis.to_bytes(6, "big") + rng.randbytes(10)
    return str(ULID.from_bytes(raw))


def order_created(
    rng: random.Random,
    timestamp: datetime,
    order_id: str,
    customer: Customer,
    items: list[OrderItem],
) -> OrderCreated:
    return OrderCreated(
        event_id=new_event_id(rng, timestamp),
        event_timestamp=timestamp,
        order_id=order_id,
        customer_id=customer.customer_id,
        items=items,
    )


def order_transition(
    rng: random.Random,
    timestamp: datetime,
    state: OrderState,
    previous: OrderEvent,
) -> OrderEvent:
    """Derived event for an order entering `state`, reusing the order and customer."""
    return EVENT_FOR_STATE[state](
        event_id=new_event_id(rng, timestamp),
        event_timestamp=timestamp,
        order_id=previous.order_id,
        customer_id=previous.customer_id,
    )
