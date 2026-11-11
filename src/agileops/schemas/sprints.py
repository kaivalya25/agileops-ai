from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from agileops.domain.models import Sprint


class SprintCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Reporting reliability",
                    "planned_start_date": "2026-11-16",
                    "planned_end_date": "2026-11-27",
                }
            ]
        }
    )

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    planned_start_date: date
    planned_end_date: date

    @model_validator(mode="after")
    def validate_planned_dates(self) -> "SprintCreate":
        if self.planned_end_date < self.planned_start_date:
            raise ValueError("planned_end_date must be on or after planned_start_date.")
        return self

    def to_domain(self, sprint_id: str) -> Sprint:
        return Sprint(
            sprint_id=sprint_id,
            name=self.name,
            planned_start_date=self.planned_start_date,
            planned_end_date=self.planned_end_date,
        )


class SprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sprint_id: str
    name: str
    planned_start_date: date
    planned_end_date: date
