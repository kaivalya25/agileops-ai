from pydantic import BaseModel, Field
from agileops.domain.models import Ticket
from agileops.domain.enums import (
    TicketPriority,
    TicketType,
)

class TicketCreate(BaseModel):
    title: str = Field(
        min_length = 10,
        max_length = 200,
    )

    description: str = Field(
        min_length = 10,
        max_length = 1000,
    )

    ticket_type: TicketType

    priority: TicketPriority

    business_impact: str = Field(
        min_length = 10,
        max_length = 100,
    )

    created_by: str = Field(
        min_length = 2,
        max_length = 50,
    )

    assigned_to: str|None = None

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

# status is not created as anyone can pass status = "done"
ticket_request = TicketCreate(
    title="Repair dashboard refresh",
    description="Investigate and repair the dashboard refresh failure.",
    ticket_type="incident",
    priority="high",
    business_impact="Executive reporting is unavailable.",
    created_by="Finance Executive",
)
print(ticket_request.model_dump_json(indent=2))