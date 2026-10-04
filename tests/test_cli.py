import json
import re

import pytest

from generator.cli import main
from generator.models import OrderCreated

TEXT_LINE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z order_\w+ ORD-\d{6}$")


@pytest.fixture
def run(capsys, fake_time):
    """Run the CLI on the virtual clock so tests never really sleep."""

    def _run(*argv):
        assert main(list(argv), monotonic=fake_time.monotonic, sleep=fake_time.sleep) == 0
        return capsys.readouterr().out.splitlines()

    return _run


def test_text_format(run):
    lines = run("--count", "20", "--seed", "1")
    assert len(lines) == 20
    assert all(TEXT_LINE.match(line) for line in lines)
    assert lines[0].split()[1:] == ["order_created", "ORD-000001"]


def test_json_format_is_ndjson(run):
    lines = run("--count", "10", "--seed", "1", "--format", "json")
    assert len(lines) == 10
    assert OrderCreated.model_validate_json(lines[0]).order_id == "ORD-000001"
    assert all(json.loads(line)["ingestion_timestamp"] is None for line in lines)


def test_count_zero_emits_nothing(run):
    assert run("--count", "0") == []


def test_same_seed_same_output_apart_from_clock(run):
    def ids(*argv):
        return [json.loads(line)["event_id"][10:] for line in run(*argv)]

    args = ("--count", "15", "--seed", "3", "--format", "json")
    assert ids(*args) == ids(*args)


def test_output_is_paced_on_the_clock(run, fake_time):
    run("--count", "50", "--rate", "100")
    assert fake_time.now > 0
    assert set(fake_time.sleeps) == {0.01}


def test_events_of_different_orders_interleave(run):
    order_ids = [line.split()[2] for line in run("--count", "200", "--rate", "50", "--seed", "1")]
    first_order = order_ids[0]
    assert any(o != first_order for o in order_ids[: order_ids.index(first_order) + 50])
    assert len(set(order_ids)) > 3


def test_dump_catalog_products_matches_the_event_stream(run):
    products = {
        p["product_id"]: p
        for p in map(json.loads, run("--dump-catalog", "products", "--seed", "1"))
    }
    assert len(products) == 100
    assert set(next(iter(products.values()))) == {"product_id", "name", "category", "unit_price"}
    created = [
        json.loads(line)
        for line in run("--count", "40", "--seed", "1", "--format", "json")
        if '"order_created"' in line
    ]
    assert created
    for event in created:
        for item in event["items"]:
            assert products[item["product_id"]]["unit_price"] == item["unit_price"]


def test_dump_catalog_customers(run):
    customers = list(map(json.loads, run("--dump-catalog", "customers", "--seed", "1")))
    assert len(customers) == 100
    assert set(customers[0]) == {"customer_id", "name", "country"}


def test_dump_catalog_requires_a_seed():
    with pytest.raises(SystemExit):
        main(["--dump-catalog", "products"])


def test_normal_scenario_is_the_default(run):
    assert run("--count", "10", "--seed", "1", "--scenario", "normal") == run(
        "--count", "10", "--seed", "1"
    )


@pytest.mark.parametrize("scenario", ["high-load", "duplicate", "out-of-order"])
def test_unimplemented_scenarios_report_it(scenario, capsys, fake_time):
    code = main(
        ["--scenario", scenario, "--count", "5"],
        monotonic=fake_time.monotonic,
        sleep=fake_time.sleep,
    )
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert f"scenario '{scenario}' is not implemented yet" in err


@pytest.mark.parametrize(
    "bad", [["--rate", "0"], ["--count", "-1"], ["--format", "xml"], ["--scenario", "bogus"]]
)
def test_invalid_arguments_are_rejected(bad):
    with pytest.raises(SystemExit):
        main(bad)
