from collections.abc import Callable
from datetime import date
from typing import Protocol

from agileops.domain.enums import TicketStatus
from agileops.domain.models import Ticket, TicketEvent


class TicketRepository(Protocol):
    """Store tickets and their lifecycle events."""

    def create(self, build_ticket: Callable[[str], Ticket]) -> Ticket:
        """Allocate a public ID and atomically store the new ticket and its creation event."""
        ...

    def get_by_id(self, ticket_id: str) -> Ticket | None:
        ...

    def list_all(self) -> list[Ticket]:
        ...

    def list_by_incident(self, incident_id: str) -> list[Ticket] | None:
        """Return linked tickets in creation order, or None if the incident does not exist."""
        ...

    def change_status(
        self,
        ticket_id: str,
        new_status: TicketStatus,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> Ticket | None:
        """Apply a domain transition and atomically store the new status and its event."""
        ...

    def list_events(self, ticket_id: str) -> list[TicketEvent] | None:
        """Return history in write order, or None if the ticket does not exist."""
        ...

    def count_completions(self, start_date: date, end_date: date) -> int:
        """Count completed tickets from start_date through the day before end_date in UTC."""
        ...
