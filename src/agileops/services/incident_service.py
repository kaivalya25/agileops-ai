from functools import partial

from agileops.domain.enums import TicketPriority
from agileops.domain.models import Incident, Ticket
from agileops.repositories.incident_repository import IncidentRepository
from agileops.repositories.ticket_repository import TicketRepository
from agileops.schemas.incidents import IncidentCreate


class IncidentService:
    def __init__(
        self, incidents: IncidentRepository, tickets: TicketRepository
    ) -> None:
        self.incidents = incidents
        self.tickets = tickets

    def create_incident(self, incident_data: IncidentCreate) -> Incident:
        return self.incidents.create(incident_data.to_domain)

    def get_incident(self, incident_id: str) -> Incident | None:
        return self.incidents.get_by_id(incident_id)

    def list_incidents(self) -> list[Incident]:
        return self.incidents.list_all()

    def create_ticket(
        self, incident_id: str, priority: TicketPriority
    ) -> Ticket | None:
        incident = self.incidents.get_by_id(incident_id)
        if incident is None:
            return None

        return self.tickets.create(
            partial(incident.create_ticket_from_incident, priority=priority)
        )

    def list_incident_tickets(self, incident_id: str) -> list[Ticket] | None:
        return self.tickets.list_by_incident(incident_id)
