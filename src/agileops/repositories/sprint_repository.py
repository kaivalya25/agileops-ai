from collections.abc import Callable
from typing import Protocol

from agileops.domain.models import Sprint


class SprintRepository(Protocol):
    def create(self, build_sprint: Callable[[str], Sprint]) -> Sprint: ...

    def get_by_id(self, sprint_id: str) -> Sprint | None: ...

    def list_all(self) -> list[Sprint]: ...
