from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    name: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)
