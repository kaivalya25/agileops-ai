import pytest

from agileops.domain.enums import (
    TicketPriority,
    TicketStatus,
    TicketType,
)
from agileops.domain.exceptions import InvalidStatusTransitionError
from agileops.domain.models import Ticket


def create_sample_ticket() -> Ticket:
    return Ticket(
        ticket_id="TASK-001",
        title="Fix dashboard",
        description="Repair sales dashboard refresh.",
        ticket_type=TicketType.INCIDENT,
        priority=TicketPriority.HIGH,
        business_impact="Executive reporting unavailable.",
        created_by="Finance Executive",
    )


def test_new_ticket_start_as_new():
    ticket = create_sample_ticket()

    assert ticket.status == TicketStatus.NEW


def test_valid_status_transition():
    ticket = create_sample_ticket()
    ticket.change_status(TicketStatus.INVESTIGATING)
    assert ticket.status == TicketStatus.INVESTIGATING


def test_invalid_status_transition_is_rejected():
    ticket = create_sample_ticket()
    with pytest.raises(InvalidStatusTransitionError):
        ticket.change_status(TicketStatus.DONE)
