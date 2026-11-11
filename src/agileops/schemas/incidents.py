from pydantic import BaseModel, ConfigDict, Field

from agileops.domain.enums import TicketPriority
from agileops.domain.models import Incident


class IncidentCreate(BaseModel):
    summary: str = Field(
        min_length = 10,
        max_length = 200,
    )

    reported_by: str = Field(
        min_length = 2,
        max_length = 50,
    )

    business_impact: str = Field(
        min_length = 10,
        max_length = 100,
    )

    affected_system: str|None = None

    def to_domain(self, incident_id: str) -> Incident:
        return Incident(
            incident_id=incident_id,
            summary=self.summary,
            reported_by=self.reported_by,
            business_impact=self.business_impact,
            affected_system=self.affected_system,
        )


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: str
    summary: str
    reported_by: str
    business_impact: str
    affected_system: str | None


class IncidentTicketCreate(BaseModel):
    priority: TicketPriority

