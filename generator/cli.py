"""Command line interface: `python -m generator`."""

import argparse
import errno
import itertools
import os
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from generator.generator import EventGenerator
from generator.models import TIMESTAMP_FORMAT, OrderEvent
from generator.stream import live_stream

SCENARIOS = ("normal", "high-load", "duplicate", "out-of-order")
IMPLEMENTED_SCENARIOS = frozenset({"normal"})


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m generator",
        description="Generate a stream of coherent order events.",
    )
    parser.add_argument(
        "--rate",
        type=positive_float,
        default=10.0,
        help="steady-state events per second (default: 10); the first minutes emit "
        "less, while the first orders have not progressed yet",
    )
    parser.add_argument("--seed", type=int, help="seed for reproducible output")
    parser.add_argument(
        "--count",
        type=non_negative_int,
        help="number of events to emit, then stop (default: run until interrupted)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="text: one readable line per event; json: NDJSON (default: text)",
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="normal",
        help="traffic scenario; only 'normal' is implemented so far (default: normal)",
    )
    parser.add_argument(
        "--dump-catalog",
        choices=("customers", "products"),
        help="print that reference data as NDJSON and exit (requires --seed, so it "
        "matches the events generated with the same seed)",
    )
    return parser


def format_event(event: OrderEvent, output_format: str) -> str:
    if output_format == "json":
        return event.model_dump_json()
    timestamp = event.event_timestamp.strftime(TIMESTAMP_FORMAT)
    return f"{timestamp} {event.event_type} {event.order_id}"


def main(
    argv: Sequence[str] | None = None,
    *,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # product names are accented; NDJSON is UTF-8
    if args.dump_catalog and args.seed is None:
        parser.error("--dump-catalog requires --seed")
    if args.scenario not in IMPLEMENTED_SCENARIOS:
        print(f"scenario '{args.scenario}' is not implemented yet", file=sys.stderr)
        return 2

    started, base = monotonic(), datetime.now(UTC)

    def clock() -> datetime:  # wall-clock start, advanced by the monotonic clock
        return base + timedelta(seconds=monotonic() - started)

    generator = EventGenerator(seed=args.seed, clock=clock)
    if args.dump_catalog:
        for entity in getattr(generator, args.dump_catalog):
            print(entity.model_dump_json())
        return 0

    events = live_stream(generator, args.rate, sleep=sleep)
    if args.count is not None:
        events = itertools.islice(events, args.count)
    try:
        for event in events:
            print(format_event(event, args.format), flush=True)
    except KeyboardInterrupt:
        return 130
    except OSError as error:
        # Reader closed the pipe (e.g. `| head`); Windows reports it as EINVAL.
        if not isinstance(error, BrokenPipeError) and error.errno != errno.EINVAL:
            raise
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())  # silence exit flush
    return 0
