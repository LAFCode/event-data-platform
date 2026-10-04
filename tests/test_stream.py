from datetime import UTC, datetime, timedelta

import pytest

from generator.generator import EventGenerator
from generator.state_machine import LifecycleConfig
from generator.stream import live_stream

BASE = datetime(2026, 10, 4, 16, 50, tzinfo=UTC)


def run(fake_time, rate, seconds, seed=1, config=None):
    """Drive the stream on virtual time; return (event, release_time) pairs."""
    gen = EventGenerator(
        seed=seed,
        clock=lambda: BASE + timedelta(seconds=fake_time.now),
        config=config,
    )
    out = []
    for event in live_stream(gen, rate, sleep=fake_time.sleep):
        if fake_time.now >= seconds:
            return out
        out.append((event, BASE + timedelta(seconds=fake_time.now)))
    return out


def test_events_are_never_released_before_their_timestamp(fake_time):
    for event, released_at in run(fake_time, rate=50, seconds=120):
        assert event.event_timestamp <= released_at


def test_events_leave_in_non_decreasing_timestamp_order(fake_time):
    stamps = [e.event_timestamp for e, _ in run(fake_time, rate=50, seconds=200)]
    assert stamps == sorted(stamps)


def test_orders_interleave(fake_time):
    order_ids = [e.order_id for e, _ in run(fake_time, rate=50, seconds=120)]
    seen_closed = set()
    interleaved = False
    for previous, current in zip(order_ids, order_ids[1:], strict=False):
        if current != previous:
            if current in seen_closed:
                interleaved = True
            seen_closed.add(previous)
    assert interleaved


def test_steady_state_rate_matches_target(fake_time):
    # delays are at most 60 s per step, so the stream is in steady state after ~3 min
    events = run(fake_time, rate=50, seconds=400)
    start = BASE + timedelta(seconds=200)
    in_window = [e for e, at in events if start <= at < start + timedelta(seconds=200)]
    assert len(in_window) / 200 == pytest.approx(50, rel=0.1)


def test_first_events_are_order_created_only(fake_time):
    events = run(fake_time, rate=50, seconds=0.5)
    assert events
    assert {e.event_type for e, _ in events} == {"order_created"}


def test_lifecycles_complete_for_old_orders(fake_time):
    config = LifecycleConfig(min_delay_seconds=1, max_delay_seconds=2)
    events = run(fake_time, rate=20, seconds=60, config=config)
    types = {e.event_type for e, _ in events}
    assert {"order_paid", "order_shipped", "order_delivered", "order_cancelled"} <= types


def test_same_seed_is_reproducible(fake_time):
    a = [e.model_dump_json() for e, _ in run(fake_time, rate=20, seconds=30, seed=3)]
    fake_time.now = 0
    b = [e.model_dump_json() for e, _ in run(fake_time, rate=20, seconds=30, seed=3)]
    assert a == b


def test_work_is_batched_in_ticks(fake_time):
    run(fake_time, rate=1000, seconds=5)
    assert set(fake_time.sleeps) == {0.01}
    assert len(fake_time.sleeps) <= 520  # one sleep per tick, never one per event


def test_rejects_non_positive_rate():
    with pytest.raises(ValueError):
        next(live_stream(EventGenerator(seed=1), 0))
