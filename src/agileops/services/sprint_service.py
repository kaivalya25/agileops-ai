from agileops.domain.models import Sprint, Ticket
from agileops.repositories.sprint_repository import SprintRepository
from agileops.repositories.ticket_repository import TicketRepository
from agileops.schemas.sprints import SprintCreate


class SprintService:
    def __init__(self, sprints: SprintRepository, tickets: TicketRepository) -> None:
        self.sprints = sprints
        self.tickets = tickets

    def create_sprint(self, sprint_data: SprintCreate) -> Sprint:
        return self.sprints.create(sprint_data.to_domain)

    def get_sprint(self, sprint_id: str) -> Sprint | None:
        return self.sprints.get_by_id(sprint_id)

    def list_sprints(self) -> list[Sprint]:
        return self.sprints.list_all()

    def list_sprint_tickets(self, sprint_id: str) -> list[Ticket] | None:
        return self.tickets.list_by_sprint(sprint_id)
