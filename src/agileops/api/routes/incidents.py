from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agileops.schemas.incidents import (
    IncidentCreate,
    IncidentResponse,
    IncidentTicketCreate,
)
from agileops.schemas.tickets import TicketResponse
from agileops.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])


def get_incident_service(request: Request) -> IncidentService:
    return request.app.state.incident_service


IncidentServiceDependency = Annotated[IncidentService, Depends(get_incident_service)]


def _incident_not_found(incident_id: str) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found."
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_incident(
    incident_data: IncidentCreate, service: IncidentServiceDependency
) -> IncidentResponse:
    """Record a reported IT incident and its business impact."""
    return IncidentResponse.model_validate(service.create_incident(incident_data))


@router.get("")
def list_incidents(service: IncidentServiceDependency) -> list[IncidentResponse]:
    """List recorded incidents in ID sequence order."""
    return [
        IncidentResponse.model_validate(incident)
        for incident in service.list_incidents()
    ]


@router.get("/{incident_id}")
def get_incident(
    incident_id: str, service: IncidentServiceDependency
) -> IncidentResponse:
    """Retrieve the persisted incident."""
    incident = service.get_incident(incident_id)
    if incident is None:
        raise _incident_not_found(incident_id)
    return IncidentResponse.model_validate(incident)


@router.post("/{incident_id}/tickets", status_code=status.HTTP_201_CREATED)
def create_incident_ticket(
    incident_id: str,
    ticket_data: IncidentTicketCreate,
    service: IncidentServiceDependency,
) -> TicketResponse:
    """Create a NEW incident ticket with a durable relationship to its incident."""
    ticket = service.create_ticket(incident_id, ticket_data.priority)
    if ticket is None:
        raise _incident_not_found(incident_id)
    return TicketResponse.from_domain(ticket)


@router.get("/{incident_id}/tickets")
def list_incident_tickets(
    incident_id: str, service: IncidentServiceDependency
) -> list[TicketResponse]:
    """List tickets linked to the specified incident."""
    tickets = service.list_incident_tickets(incident_id)
    if tickets is None:
        raise _incident_not_found(incident_id)
    return [TicketResponse.from_domain(ticket) for ticket in tickets]
