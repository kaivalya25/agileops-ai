from collections.abc import Callable
from typing import Protocol

from agileops.domain.models import Incident


class IncidentRepository(Protocol):
    def create(self, build_incident: Callable[[str], Incident]) -> Incident:
        """Allocate a public ID and persist the incident."""
        ...

    def get_by_id(self, incident_id: str) -> Incident | None:
        ...

    def list_all(self) -> list[Incident]:
        ...
