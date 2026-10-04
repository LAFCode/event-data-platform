"""Coherent event generation on top of a customer/product catalog."""

import itertools
import random
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

from generator import events
from generator.catalog import build_customers, load_products
from generator.models import OrderCreated, OrderEvent, OrderItem
from generator.state_machine import TRANSITIONS, LifecycleConfig, OrderState

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(UTC)


class EventGenerator:
    def __init__(
        self,
        seed: int | None = None,
        clock: Clock = system_clock,
        n_customers: int = 100,
        config: LifecycleConfig | None = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.clock = clock
        self.config = config or LifecycleConfig()
        self.customers = build_customers(self.rng, n_customers)
        self.products = load_products()
        self._order_seq = 0

    def next_order_created(self) -> OrderCreated:
        self._order_seq += 1
        customer = self.rng.choice(self.customers)
        chosen = self.rng.sample(self.products, k=self.rng.randint(1, 3))
        items = [
            OrderItem(
                product_id=p.product_id,
                quantity=self.rng.randint(1, 5),
                unit_price=p.unit_price,
            )
            for p in chosen
        ]
        return events.order_created(
            self.rng, self.clock(), f"ORD-{self._order_seq:06d}", customer, items
        )

    def stream(self, count: int | None = None) -> Iterator[OrderCreated]:
        """`count` orders, or an endless stream when `count` is None."""
        for _ in range(count) if count is not None else itertools.count():
            yield self.next_order_created()

    def lifecycle(self, created: OrderCreated) -> list[OrderEvent]:
        """Walk the state machine from `created`; return the derived events in order.

        The whole lifecycle is planned up front, so derived events carry future timestamps;
        `live_stream` releases each one only when its time arrives. Delays come from the
        config, so timestamps strictly increase.
        """
        derived: list[OrderEvent] = []
        state = OrderState.CREATED
        previous: OrderEvent = created
        while next_state := self._pick_transition(state):
            delay = self.rng.randint(self.config.min_delay_seconds, self.config.max_delay_seconds)
            timestamp = previous.event_timestamp + timedelta(seconds=delay)
            previous = events.order_transition(self.rng, timestamp, next_state, previous)
            derived.append(previous)
            state = next_state
        return derived

    def _pick_transition(self, state: OrderState) -> OrderState | None:
        roll = self.rng.random()
        cumulative = 0.0
        for target in TRANSITIONS[state]:
            cumulative += self.config.probabilities[(state, target)]
            if roll < cumulative:
                return target
        return None
