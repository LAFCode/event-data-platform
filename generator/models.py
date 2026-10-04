"""Domain entities and event schemas."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Customer(BaseModel):
    """Reference data, exported with `--dump-catalog customers`; not part of order events."""

    model_config = ConfigDict(frozen=True)

    customer_id: str = Field(pattern=r"^CUS-\d{6}$")
    name: str = Field(min_length=1)
    country: str = Field(pattern=r"^[A-Z]{2}$")


class Product(BaseModel):
    """Reference data, exported with `--dump-catalog products`; not part of order events."""

    model_config = ConfigDict(frozen=True)

    product_id: str = Field(pattern=r"^PROD-\d{6}$")
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    unit_price: Decimal = Field(gt=0, decimal_places=2)

    @field_serializer("unit_price", when_used="json")
    def _serialize_price(self, value: Decimal) -> float:
        return float(value)


class OrderItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str = Field(pattern=r"^PROD-\d{6}$")
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, decimal_places=2)

    @field_serializer("unit_price", when_used="json")
    def _serialize_price(self, value: Decimal) -> float:
        return float(value)


class Event(BaseModel):
    """Envelope shared by every event.

    `event_timestamp` is when the event happened at the source.
    `ingestion_timestamp` is filled later by the pipeline, which enables
    late-arriving event, ordering and latency analysis.
    """

    event_id: str = Field(pattern=r"^[0-9A-HJKMNP-TV-Z]{26}$")
    event_type: str
    event_version: int = 1
    event_timestamp: datetime
    ingestion_timestamp: datetime | None = None

    @field_serializer("event_timestamp", "ingestion_timestamp", when_used="json")
    def _serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).strftime(TIMESTAMP_FORMAT)


class OrderEvent(Event):
    order_id: str = Field(pattern=r"^ORD-\d{6}$")
    customer_id: str = Field(pattern=r"^CUS-\d{6}$")


class OrderCreated(OrderEvent):
    event_type: Literal["order_created"] = "order_created"
    items: list[OrderItem] = Field(min_length=1)


class OrderPaid(OrderEvent):
    event_type: Literal["order_paid"] = "order_paid"


class OrderShipped(OrderEvent):
    event_type: Literal["order_shipped"] = "order_shipped"


class OrderDelivered(OrderEvent):
    event_type: Literal["order_delivered"] = "order_delivered"


class OrderCancelled(OrderEvent):
    event_type: Literal["order_cancelled"] = "order_cancelled"
