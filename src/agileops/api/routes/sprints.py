from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agileops.schemas.sprints import SprintCreate, SprintResponse
from agileops.schemas.tickets import TicketResponse
from agileops.services.sprint_service import SprintService

router = APIRouter(prefix="/sprints", tags=["sprints"])


def get_sprint_service(request: Request) -> SprintService:
    return request.app.state.sprint_service


SprintServiceDependency = Annotated[SprintService, Depends(get_sprint_service)]


def _sprint_not_found(sprint_id: str) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, detail=f"Sprint {sprint_id} not found."
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_sprint(
    sprint_data: SprintCreate, service: SprintServiceDependency
) -> SprintResponse:
    """Create a sprint with a name and an ordered pair of planned dates."""
    return SprintResponse.model_validate(service.create_sprint(sprint_data))


@router.get("")
def list_sprints(service: SprintServiceDependency) -> list[SprintResponse]:
    """List sprints in creation order."""
    return [SprintResponse.model_validate(sprint) for sprint in service.list_sprints()]


@router.get("/{sprint_id}")
def get_sprint(sprint_id: str, service: SprintServiceDependency) -> SprintResponse:
    """Retrieve a sprint and its planned dates."""
    sprint = service.get_sprint(sprint_id)
    if sprint is None:
        raise _sprint_not_found(sprint_id)
    return SprintResponse.model_validate(sprint)


@router.get("/{sprint_id}/tickets")
def list_sprint_tickets(
    sprint_id: str, service: SprintServiceDependency
) -> list[TicketResponse]:
    """List the tickets currently scheduled for this sprint."""
    tickets = service.list_sprint_tickets(sprint_id)
    if tickets is None:
        raise _sprint_not_found(sprint_id)
    return [TicketResponse.from_domain(ticket) for ticket in tickets]
