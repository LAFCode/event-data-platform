"""Reference data: products come from a CSV, customers are generated from a seed."""

import csv
import itertools
import random
from decimal import Decimal
from pathlib import Path

from generator.models import Customer, Product

PRODUCTS_CSV = Path(__file__).parent / "data" / "products.csv"

FIRST_NAMES = (
    "Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Gabriela", "Hugo",
    "Isabel", "Joao", "Karen", "Lucas", "Marina", "Nicolas", "Olivia", "Pedro",
    "Quirino", "Rafaela", "Sofia", "Tiago", "Ursula", "Victor", "Wendy", "Xavier",
    "Yara", "Zeca", "Alice", "Bento", "Clara", "Davi",
)  # fmt: skip
LAST_NAMES = (
    "Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Costa", "Ribeiro",
    "Almeida", "Gomes", "Martins", "Rocha", "Carvalho", "Araujo", "Melo", "Barbosa",
    "Cardoso", "Teixeira", "Moreira", "Nunes", "Smith", "Johnson", "Miller", "Garcia",
    "Martin", "Muller", "Rossi", "Tanaka", "Dubois", "Lopez",
)  # fmt: skip
COUNTRIES = ("BR", "US", "DE", "FR", "GB", "ES", "IT", "CA", "MX", "JP")


def load_products(path: Path = PRODUCTS_CSV) -> list[Product]:
    """Products in file order (`PROD-000001` is the first row); prices are in BRL."""
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    products = [
        Product(
            product_id=f"PROD-{i:06d}",
            name=row["name"],
            category=row["category"],
            unit_price=Decimal(row["unit_price"]),
        )
        for i, row in enumerate(rows, start=1)
    ]
    if len({p.name for p in products}) != len(products):
        raise ValueError(f"duplicate product names in {path.name}")
    return products


def build_customers(rng: random.Random, n_customers: int) -> list[Customer]:
    """Unique names drawn without repetition, so the same seed gives the same customers."""
    people = list(itertools.product(FIRST_NAMES, LAST_NAMES))
    if n_customers > len(people):
        raise ValueError(f"at most {len(people)} customers are supported")
    return [
        Customer(
            customer_id=f"CUS-{i:06d}",
            name=f"{first} {last}",
            country=rng.choice(COUNTRIES),
        )
        for i, (first, last) in enumerate(rng.sample(people, k=n_customers), start=1)
    ]
