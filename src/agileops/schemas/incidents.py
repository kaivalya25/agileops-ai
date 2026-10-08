from pydantic import BaseModel, Field

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

