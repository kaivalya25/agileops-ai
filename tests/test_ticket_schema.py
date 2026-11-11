import pytest
from pydantic import ValidationError

from agileops.schemas.tickets import TicketCreate


def test_invalid_priority_is_rejected():
    with pytest.raises(ValidationError):
        TicketCreate(
            title="Fix dashboard",
            description="Repair dashboard refresh failure.",
            ticket_type="incident",
            priority="banana",
            business_impact="Executive reporting unavailable.",
            created_by="Finance Executive",
        )
