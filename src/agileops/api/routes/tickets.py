from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agileops.domain.exceptions import InvalidStatusTransitionError, SprintNotFoundError
from agileops.schemas.tickets import (
    TicketAssignmentUpdate,
    TicketCreate,
    TicketEventResponse,
    TicketMetricsResponse,
    TicketResponse,
    TicketSprintResponse,
    TicketSprintUpdate,
    TicketStatusUpdate,
    TicketThroughputResponse,
)
from agileops.services.ticket_services import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(request: Request) -> TicketService:
    return request.app.state.ticket_service


TicketServiceDependency = Annotated[TicketService, Depends(get_ticket_service)]


def _ticket_not_found(ticket_id: str) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, detail=f"Ticket {ticket_id} not found."
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket_data: TicketCreate, service: TicketServiceDependency
) -> TicketResponse:
    """Create a ticket in NEW and append its creation event."""
    return TicketResponse.from_domain(service.create_ticket(ticket_data))


@router.get("")
def list_tickets(service: TicketServiceDependency) -> list[TicketResponse]:
    """List all tickets in creation order."""
    return [TicketResponse.from_domain(ticket) for ticket in service.list_tickets()]


@router.get("/backlog")
def list_backlog(service: TicketServiceDependency) -> list[TicketResponse]:
    """List open tickets that do not belong to a sprint."""
    return [TicketResponse.from_domain(ticket) for ticket in service.list_backlog()]


@router.get("/metrics/throughput")
def get_ticket_throughput(
    start_date: date, end_date: date, service: TicketServiceDependency
) -> TicketThroughputResponse:
    """Count DONE events from the start UTC date through the day before the end date."""
    if start_date >= end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be before end_date.",
        )
    return TicketThroughputResponse(
        start_date=start_date,
        end_date=end_date,
        completed_tickets=service.count_completed_tickets(start_date, end_date),
    )


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, service: TicketServiceDependency) -> TicketResponse:
    """Retrieve the current ticket snapshot."""
    ticket = service.get_ticket(ticket_id)
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketResponse.from_domain(ticket)


@router.get("/{ticket_id}/sprint")
def get_ticket_sprint(
    ticket_id: str, service: TicketServiceDependency
) -> TicketSprintResponse:
    """Retrieve the ticket's current sprint membership."""
    ticket = service.get_ticket(ticket_id)
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketSprintResponse.model_validate(ticket)


@router.patch("/{ticket_id}/sprint")
def set_ticket_sprint(
    ticket_id: str, update: TicketSprintUpdate, service: TicketServiceDependency
) -> TicketSprintResponse:
    """Assign the ticket to a sprint or remove its sprint membership."""
    try:
        ticket = service.set_ticket_sprint(ticket_id, update.sprint_id)
    except SprintNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketSprintResponse.model_validate(ticket)


@router.patch("/{ticket_id}/assignment")
def set_ticket_assignee(
    ticket_id: str, update: TicketAssignmentUpdate, service: TicketServiceDependency
) -> TicketResponse:
    """Set or clear the ticket's assignee."""
    ticket = service.set_ticket_assignee(ticket_id, update.assigned_to)
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketResponse.from_domain(ticket)


@router.patch("/{ticket_id}/status")
def change_ticket_status(
    ticket_id: str, update: TicketStatusUpdate, service: TicketServiceDependency
) -> TicketResponse:
    """Apply an allowed transition and append its actor, reason and UTC timestamp."""
    try:
        ticket = service.change_ticket_status(
            ticket_id, update.status, actor=update.actor, reason=update.reason
        )
    except InvalidStatusTransitionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketResponse.from_domain(ticket)


@router.get("/{ticket_id}/events")
def list_ticket_events(
    ticket_id: str, service: TicketServiceDependency
) -> list[TicketEventResponse]:
    """Read immutable ticket events in write order."""
    events = service.list_ticket_events(ticket_id)
    if events is None:
        raise _ticket_not_found(ticket_id)
    return [TicketEventResponse.from_domain(event) for event in events]


@router.get("/{ticket_id}/metrics")
def get_ticket_metrics(
    ticket_id: str, service: TicketServiceDependency
) -> TicketMetricsResponse:
    """Calculate lead time, cycle time, completed QA time and QA returns."""
    metrics = service.get_ticket_metrics(ticket_id)
    if metrics is None:
        raise _ticket_not_found(ticket_id)
    return TicketMetricsResponse.model_validate(metrics)
