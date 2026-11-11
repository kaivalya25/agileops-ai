from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agileops.domain.enums import (
    TicketEventType,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from agileops.domain.models import Ticket, TicketEvent


class TicketCreate(BaseModel):
    title: str = Field(
        min_length=10,
        max_length=200,
    )

    description: str = Field(
        min_length=10,
        max_length=1000,
    )

    ticket_type: TicketType

    priority: TicketPriority

    business_impact: str = Field(
        min_length=10,
        max_length=100,
    )

    created_by: str = Field(
        min_length=2,
        max_length=50,
    )

    assigned_to: str | None = None

    def to_domain(self, ticket_id: str) -> Ticket:
        return Ticket(
            ticket_id=ticket_id,
            title=self.title,
            description=self.description,
            ticket_type=self.ticket_type,
            priority=self.priority,
            business_impact=self.business_impact,
            created_by=self.created_by,
            assigned_to=self.assigned_to,
        )


class TicketResponse(BaseModel):
    ticket_id: str
    title: str
    description: str
    ticket_type: str
    priority: str
    business_impact: str
    created_by: str
    assigned_to: str | None
    status: str

    @classmethod
    def from_domain(cls, ticket: Ticket) -> "TicketResponse":
        return cls.model_validate(ticket.to_dict())


class TicketStatusUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "investigating",
                    "actor": "Reporting operations",
                    "reason": "Confirmed the refresh failure.",
                }
            ]
        }
    )

    status: TicketStatus
    actor: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    ) = None
    reason: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    ) = None


class TicketSprintUpdate(BaseModel):
    sprint_id: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    )


class TicketSprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    sprint_id: str | None


class TicketAssignmentUpdate(BaseModel):
    assigned_to: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    )


class TicketEventResponse(BaseModel):
    event_id: int
    ticket_id: str
    event_type: TicketEventType
    previous_status: str | None
    new_status: str
    occurred_at: datetime
    actor: str | None
    reason: str | None

    @classmethod
    def from_domain(cls, event: TicketEvent) -> "TicketEventResponse":
        return cls(
            event_id=event.event_id,
            ticket_id=event.ticket_id,
            event_type=event.event_type,
            previous_status=event.previous_status.name
            if event.previous_status is not None
            else None,
            new_status=event.new_status.name,
            occurred_at=event.occurred_at,
            actor=event.actor,
            reason=event.reason,
        )


class TicketMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    lead_time_seconds: float | None
    cycle_time_seconds: float | None
    qa_turnaround_seconds: float
    qa_return_count: int


class TicketThroughputResponse(BaseModel):
    start_date: date
    end_date: date
    completed_tickets: int
