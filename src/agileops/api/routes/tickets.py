from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agileops.domain.exceptions import InvalidStatusTransitionError
from agileops.schemas.tickets import (
    TicketCreate,
    TicketEventResponse,
    TicketResponse,
    TicketStatusUpdate,
)
from agileops.services.ticket_services import TicketService


router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(request: Request) -> TicketService:
    return request.app.state.ticket_service


TicketServiceDependency = Annotated[TicketService, Depends(get_ticket_service)]


def _ticket_not_found(ticket_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Ticket {ticket_id} not found.")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(ticket_data: TicketCreate, service: TicketServiceDependency) -> TicketResponse:
    return TicketResponse.from_domain(service.create_ticket(ticket_data))


@router.get("")
def list_tickets(service: TicketServiceDependency) -> list[TicketResponse]:
    return [TicketResponse.from_domain(ticket) for ticket in service.list_tickets()]


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, service: TicketServiceDependency) -> TicketResponse:
    ticket = service.get_ticket(ticket_id)
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketResponse.from_domain(ticket)


@router.patch("/{ticket_id}/status")
def change_ticket_status(
    ticket_id: str, update: TicketStatusUpdate, service: TicketServiceDependency
) -> TicketResponse:
    try:
        ticket = service.change_ticket_status(ticket_id, update.status)
    except InvalidStatusTransitionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    if ticket is None:
        raise _ticket_not_found(ticket_id)
    return TicketResponse.from_domain(ticket)


@router.get("/{ticket_id}/events")
def list_ticket_events(
    ticket_id: str, service: TicketServiceDependency
) -> list[TicketEventResponse]:
    events = service.list_ticket_events(ticket_id)
    if events is None:
        raise _ticket_not_found(ticket_id)
    return [TicketEventResponse.from_domain(event) for event in events]
