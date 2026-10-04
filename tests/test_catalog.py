import csv
import json
import random
from decimal import Decimal

import pytest

from generator.catalog import PRODUCTS_CSV, build_customers, load_products
from generator.generator import EventGenerator


def test_products_are_loaded_from_the_csv_in_file_order():
    with PRODUCTS_CSV.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    products = load_products()
    assert len(products) == 100
    assert [p.name for p in products] == [r["name"] for r in rows]
    assert [p.unit_price for p in products] == [Decimal(r["unit_price"]) for r in rows]
    assert products[0].product_id == "PROD-000001"
    assert products[-1].product_id == "PROD-000100"


def test_catalog_has_unique_names_and_several_categories():
    products = load_products()
    assert len({p.name for p in products}) == 100
    assert len({p.category for p in products}) >= 8
    assert all(p.unit_price > 0 for p in products)


def test_products_do_not_depend_on_the_seed():
    assert EventGenerator(seed=1).products == EventGenerator(seed=2).products


def test_duplicate_product_names_are_rejected(tmp_path):
    bad = tmp_path / "products.csv"
    bad.write_text("name,category,unit_price\nA,X,1.00\nA,X,2.00\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_products(bad)


def test_customers_are_reproducible_and_unique():
    a, b = EventGenerator(seed=5), EventGenerator(seed=5)
    assert a.customers == b.customers
    assert EventGenerator(seed=6).customers != a.customers
    assert len(a.customers) == 100
    assert len({c.name for c in a.customers}) == 100


def test_product_json_has_catalog_fields_and_numeric_price():
    data = json.loads(EventGenerator(seed=1).products[0].model_dump_json())
    assert set(data) == {"product_id", "name", "category", "unit_price"}
    assert isinstance(data["unit_price"], float)


def test_customer_json_has_catalog_fields():
    data = json.loads(EventGenerator(seed=1).customers[0].model_dump_json())
    assert set(data) == {"customer_id", "name", "country"}
    assert len(data["country"]) == 2


def test_customer_count_is_bounded():
    with pytest.raises(ValueError):
        build_customers(random.Random(1), n_customers=10_000)


def test_order_events_stay_lean():
    event = EventGenerator(seed=1).next_order_created()
    assert set(event.items[0].model_dump()) == {"product_id", "quantity", "unit_price"}
