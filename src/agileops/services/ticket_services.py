from datetime import date

from agileops.domain.enums import TicketStatus
from agileops.domain.models import Ticket, TicketEvent
from agileops.domain.ticket_metrics import TicketMetrics, calculate_ticket_metrics
from agileops.repositories.ticket_repository import TicketRepository
from agileops.schemas.tickets import TicketCreate


class TicketService:
    def __init__(self, repository: TicketRepository) -> None:
        self.repository = repository

    def create_ticket(self, ticket_data: TicketCreate) -> Ticket:
        return self.repository.create(ticket_data.to_domain)

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self.repository.get_by_id(ticket_id)

    def list_tickets(self) -> list[Ticket]:
        return self.repository.list_all()

    def change_ticket_status(self, ticket_id: str, new_status: TicketStatus) -> Ticket | None:
        return self.repository.change_status(ticket_id, new_status)

    def list_ticket_events(self, ticket_id: str) -> list[TicketEvent] | None:
        return self.repository.list_events(ticket_id)

    def get_ticket_metrics(self, ticket_id: str) -> TicketMetrics | None:
        events = self.repository.list_events(ticket_id)
        if events is None:
            return None
        return calculate_ticket_metrics(ticket_id, events)

    def count_completed_tickets(self, start_date: date, end_date: date) -> int:
        return self.repository.count_completions(start_date, end_date)
