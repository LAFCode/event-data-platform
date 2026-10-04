import json
from collections import Counter, defaultdict
from datetime import UTC, datetime

import pytest

from generator.generator import EventGenerator
from generator.state_machine import TRANSITIONS, LifecycleConfig, OrderState

FIXED = datetime(2026, 10, 4, 16, 50, tzinfo=UTC)
STATE_OF = {f"order_{s.value}": s for s in OrderState}


def make(seed=1, **kw):
    return EventGenerator(seed=seed, clock=lambda: FIXED, **kw)


def lifecycles(gen, count):
    """`count` orders, each followed by its derived events (grouped per order)."""
    for created in gen.stream(count):
        yield created
        yield from gen.lifecycle(created)


def by_order(events):
    grouped = defaultdict(list)
    for e in events:
        grouped[e.order_id].append(e)
    return grouped


def test_only_legal_transitions_over_10k_events():
    events = list(lifecycles(make(), 4_000))
    assert len(events) >= 10_000
    for order_events in by_order(events).values():
        states = [STATE_OF[e.event_type] for e in order_events]
        assert states[0] is OrderState.CREATED
        for src, dst in zip(states, states[1:], strict=False):
            assert dst in TRANSITIONS[src]


def test_derived_events_reuse_order_and_have_later_timestamps():
    events = list(lifecycles(make(), 500))
    for order_events in by_order(events).values():
        assert len({e.customer_id for e in order_events}) == 1
        stamps = [e.event_timestamp for e in order_events]
        assert all(a < b for a, b in zip(stamps, stamps[1:], strict=False))


def test_event_ids_are_unique():
    events = list(lifecycles(make(), 500))
    assert len({e.event_id for e in events}) == len(events)


def test_derived_event_matches_envelope_contract():
    paid = next(e for e in lifecycles(make(), 50) if e.event_type == "order_paid")
    data = json.loads(paid.model_dump_json())
    assert set(data) == {
        "event_id", "event_type", "event_version", "event_timestamp",
        "ingestion_timestamp", "order_id", "customer_id",
    }  # fmt: skip
    assert data["ingestion_timestamp"] is None


def test_default_probabilities_are_roughly_respected():
    firsts = Counter()
    for order_events in by_order(lifecycles(make(), 4_000)).values():
        if len(order_events) > 1:
            firsts[order_events[1].event_type] += 1
        else:
            firsts["stayed"] += 1
    assert 0.80 < firsts["order_paid"] / 4_000 < 0.90
    assert 0.07 < firsts["order_cancelled"] / 4_000 < 0.13


def test_same_seed_is_reproducible():
    a = [e.model_dump_json() for e in lifecycles(make(seed=7), 100)]
    b = [e.model_dump_json() for e in lifecycles(make(seed=7), 100)]
    assert a == b


def test_config_can_force_every_order_to_deliver():
    probs = {
        (OrderState.CREATED, OrderState.PAID): 1.0,
        (OrderState.CREATED, OrderState.CANCELLED): 0.0,
        (OrderState.PAID, OrderState.SHIPPED): 1.0,
        (OrderState.PAID, OrderState.CANCELLED): 0.0,
        (OrderState.SHIPPED, OrderState.DELIVERED): 1.0,
    }
    gen = make(config=LifecycleConfig(probs))
    for order_events in by_order(lifecycles(gen, 20)).values():
        assert [e.event_type for e in order_events] == [
            "order_created", "order_paid", "order_shipped", "order_delivered",
        ]  # fmt: skip


def test_config_rejects_invalid_probabilities():
    with pytest.raises(ValueError):
        LifecycleConfig({(OrderState.CREATED, OrderState.PAID): 1.0})
    probs = LifecycleConfig().probabilities | {(OrderState.CREATED, OrderState.PAID): 0.95}
    with pytest.raises(ValueError):
        LifecycleConfig(probs)


def test_expected_events_per_order_matches_the_simulation():
    expected = LifecycleConfig().expected_events_per_order()
    assert expected == pytest.approx(3.36525)
    simulated = len(list(lifecycles(make(), 4_000))) / 4_000
    assert simulated == pytest.approx(expected, rel=0.03)


def test_delays_follow_the_config():
    gen = make(config=LifecycleConfig(min_delay_seconds=5, max_delay_seconds=7))
    for order_events in by_order(lifecycles(gen, 300)).values():
        stamps = [e.event_timestamp for e in order_events]
        assert all(
            5 <= (b - a).total_seconds() <= 7 for a, b in zip(stamps, stamps[1:], strict=False)
        )


@pytest.mark.parametrize("low,high", [(0, 5), (10, 5)])
def test_config_rejects_invalid_delays(low, high):
    with pytest.raises(ValueError):
        LifecycleConfig(min_delay_seconds=low, max_delay_seconds=high)
