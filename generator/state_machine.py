"""Order lifecycle: legal states, transitions and the odds of taking each one."""

from dataclasses import dataclass, field
from enum import StrEnum


class OrderState(StrEnum):
    CREATED = "created"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Single source of truth for legal transitions (used by the generator and the tests).
TRANSITIONS: dict[OrderState, tuple[OrderState, ...]] = {
    OrderState.CREATED: (OrderState.PAID, OrderState.CANCELLED),
    OrderState.PAID: (OrderState.SHIPPED, OrderState.CANCELLED),
    OrderState.SHIPPED: (OrderState.DELIVERED,),
    OrderState.DELIVERED: (),
    OrderState.CANCELLED: (),
}


def _default_probabilities() -> dict[tuple[OrderState, OrderState], float]:
    return {
        (OrderState.CREATED, OrderState.PAID): 0.85,
        (OrderState.CREATED, OrderState.CANCELLED): 0.10,
        (OrderState.PAID, OrderState.SHIPPED): 0.85,
        (OrderState.PAID, OrderState.CANCELLED): 0.05,
        (OrderState.SHIPPED, OrderState.DELIVERED): 0.90,
    }


@dataclass(frozen=True)
class LifecycleConfig:
    """Probability of each transition (the remainder means the order stays in its state)
    and the delay range, in seconds, between two consecutive events of an order."""

    probabilities: dict[tuple[OrderState, OrderState], float] = field(
        default_factory=_default_probabilities
    )
    min_delay_seconds: int = 1
    max_delay_seconds: int = 60

    def expected_events_per_order(self) -> float:
        """Mean number of events one order produces over its whole lifecycle."""
        reach = dict.fromkeys(OrderState, 0.0)
        reach[OrderState.CREATED] = 1.0
        for src, dsts in TRANSITIONS.items():  # declared in topological order
            for dst in dsts:
                reach[dst] += reach[src] * self.probabilities[(src, dst)]
        return sum(reach.values())

    def __post_init__(self) -> None:
        if not 1 <= self.min_delay_seconds <= self.max_delay_seconds:
            raise ValueError("delays must satisfy 1 <= min_delay_seconds <= max_delay_seconds")
        legal = {(src, dst) for src, dsts in TRANSITIONS.items() for dst in dsts}
        if set(self.probabilities) != legal:
            raise ValueError("probabilities must cover exactly the legal transitions")
        for src, dsts in TRANSITIONS.items():
            total = sum(self.probabilities[(src, dst)] for dst in dsts)
            if any(self.probabilities[(src, dst)] < 0 for dst in dsts) or total > 1:
                raise ValueError(f"invalid probabilities out of state {src.value}")
