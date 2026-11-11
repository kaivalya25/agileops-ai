from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

from agileops.domain.enums import TicketEventType, TicketStatus
from agileops.domain.models import TicketEvent


@dataclass(frozen=True)
class TicketMetrics:
    ticket_id: str
    lead_time_seconds: float | None
    cycle_time_seconds: float | None
    qa_turnaround_seconds: float
    qa_return_count: int


def _elapsed_seconds(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def calculate_ticket_metrics(ticket_id: str, events: Sequence[TicketEvent]) -> TicketMetrics:
    """Calculate lifecycle metrics from one ticket's events in write order."""
    created_at = next(
        (event.occurred_at for event in events if event.event_type == TicketEventType.CREATED),
        None,
    )
    started_at = next(
        (event.occurred_at for event in events if event.new_status == TicketStatus.IN_PROGRESS),
        None,
    )
    completed_at = next(
        (event.occurred_at for event in events if event.new_status == TicketStatus.DONE),
        None,
    )

    qa_time = timedelta()
    qa_return_count = 0
    for entry, exit_event in pairwise(events):
        if entry.new_status == TicketStatus.QA and exit_event.previous_status == TicketStatus.QA:
            qa_time += exit_event.occurred_at - entry.occurred_at
            if exit_event.new_status == TicketStatus.IN_PROGRESS:
                qa_return_count += 1

    return TicketMetrics(
        ticket_id=ticket_id,
        lead_time_seconds=_elapsed_seconds(created_at, completed_at),
        cycle_time_seconds=_elapsed_seconds(started_at, completed_at),
        qa_turnaround_seconds=qa_time.total_seconds(),
        qa_return_count=qa_return_count,
    )
