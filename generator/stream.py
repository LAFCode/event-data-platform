"""Real-time event stream: orders arrive over time and their events interleave."""

import heapq
import itertools
import time
from collections.abc import Callable, Iterator

from generator.generator import EventGenerator
from generator.models import OrderEvent

TICK_SECONDS = 0.01


def live_stream(
    gen: EventGenerator,
    rate: float,
    *,
    sleep: Callable[[float], None] = time.sleep,
    tick: float = TICK_SECONDS,
) -> Iterator[OrderEvent]:
    """Endless stream of events, released when their `event_timestamp` arrives.

    `rate` is the steady-state events per second: new orders arrive at
    `rate / expected_events_per_order`, and each order's later events are held back
    until their time. Events leave in non-decreasing `event_timestamp` order, and a
    startup phase (roughly `max_delay_seconds` per lifecycle step) emits fewer events
    than `rate`, since no order has progressed yet. Time comes from `gen.clock`, so
    tests drive it with a fake clock and a fake `sleep`.

    Work is batched per tick (~10 ms) instead of sleeping once per event, and falling
    behind is made up for in the next tick without drift.
    """
    if rate <= 0:
        raise ValueError("rate must be greater than 0")
    orders_per_second = rate / gen.config.expected_events_per_order()
    start = gen.clock()
    pending: list = []  # heap of (event_timestamp, sequence, event)
    sequence = itertools.count()
    orders = 0
    while True:
        now = gen.clock()
        due = int((now - start).total_seconds() * orders_per_second) + 1
        while orders < due:
            created = gen.next_order_created()
            orders += 1
            for event in (created, *gen.lifecycle(created)):
                heapq.heappush(pending, (event.event_timestamp, next(sequence), event))
        while pending and pending[0][0] <= now:
            yield heapq.heappop(pending)[2]
        sleep(tick)
