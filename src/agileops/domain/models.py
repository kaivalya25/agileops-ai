from dataclasses import dataclass
from agileops.domain.enums import(
    TicketPriority,
    TicketStatus,
    TicketType
)

from agileops.domain.exceptions import InvalidStatusTransitionError

def build_ticket_title(
        incident_id: str, #"INC 26-0001" incident to be written in "INC YY-XXXX"
        description: str, #"Report is not refreshing since this morning"
) -> str:
    return f"{incident_id}: {description}"

ALLOWED_STATUS_TRANSITIONS: dict[
    TicketStatus, set[TicketStatus],
] = {
    TicketStatus.NEW:{TicketStatus.INVESTIGATING,},
    TicketStatus.INVESTIGATING:{TicketStatus.READY_FOR_DEV,},
    TicketStatus.READY_FOR_DEV:{TicketStatus.IN_PROGRESS,},
    TicketStatus.IN_PROGRESS:{TicketStatus.QA,},
    TicketStatus.QA:{TicketStatus.DONE,TicketStatus.IN_PROGRESS,},
    TicketStatus.DONE:set(),
}

@dataclass
class Ticket:
    ticket_id: str
    title: str
    description: str
    ticket_type: TicketType
    priority: TicketPriority
    business_impact: str
    created_by: str
    assigned_to: str|None = None
    status: TicketStatus = TicketStatus.NEW

    def change_status(self, new_status: TicketStatus) -> None:
        if new_status not in ALLOWED_STATUS_TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(
                f"Cannot transition from {self.status} to {new_status}."
            )
        self.status = new_status

    def to_dict(self) -> dict[str, str|None]:
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "description": self.description,
            "ticket_type": self.ticket_type.name,
            "priority": self.priority.name,
            "business_impact": self.business_impact,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "status": self.status.name,
        }
@dataclass
class Incident:
    incident_id: str
    summary: str
    reported_by: str
    business_impact: str
    affected_system: str| None = None

    def create_ticket_from_incident(
            incident: "Incident",
            ticket_id: str,
            priority: TicketPriority,
    ) -> Ticket:
        title = build_ticket_title(incident.incident_id, incident.summary)
        return Ticket(
            ticket_id=ticket_id,
            title=title,
            description=incident.summary,
            ticket_type=TicketType.INCIDENT,
            priority=priority,
            business_impact=incident.business_impact,
            created_by=incident.reported_by,
        )

incident = Incident(
    incident_id = "INC 26-0002",
    summary="Sales dashboard refresh failed.",
    reported_by="Sales Manager",
    business_impact="High",
    affected_system= None
)

ticket = Incident.create_ticket_from_incident(
    incident=incident,
    ticket_id="TASK 26-0002",
    priority=TicketPriority.HIGH
)

print(ticket)
print(ticket.to_dict())