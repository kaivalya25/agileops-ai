import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI

from agileops.api.routes.automation import router as automation_router
from agileops.api.routes.incidents import router as incidents_router
from agileops.api.routes.sprints import router as sprints_router
from agileops.api.routes.tickets import router as tickets_router
from agileops.database import migrate
from agileops.repositories.sqlite_incident_repository import SQLiteIncidentRepository
from agileops.repositories.sqlite_sprint_repository import SQLiteSprintRepository
from agileops.repositories.sqlite_ticket_repository import SQLiteTicketRepository
from agileops.services.incident_service import IncidentService
from agileops.services.sprint_service import SprintService
from agileops.services.ticket_services import TicketService
from agileops.workflow import WorkflowRuntime

PROJECT_NAME = "AgileOps AI"


def get_project_name() -> str:
    return PROJECT_NAME


def create_app(database_path: str | Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configured_path = os.environ.get("AGILEOPS_DB_PATH", "agileops.db")
        path = Path(
            configured_path if database_path is None else database_path
        ).resolve()
        migrate(path)
        tickets = SQLiteTicketRepository(path)
        app.state.ticket_service = TicketService(tickets)
        app.state.incident_service = IncidentService(
            SQLiteIncidentRepository(path), tickets
        )
        app.state.sprint_service = SprintService(SQLiteSprintRepository(path), tickets)
        app.state.workflow = WorkflowRuntime(path)
        yield

    app = FastAPI(
        title=PROJECT_NAME,
        version=version("agileops-ai"),
        description=(
            "Manage incidents, tickets and sprints. Investigate reporting failures, "
            "review approval-gated workflows and query verified portfolio metrics."
        ),
        lifespan=lifespan,
    )
    app.include_router(tickets_router)
    app.include_router(incidents_router)
    app.include_router(sprints_router)
    app.include_router(automation_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    print(f"Starting the Project {get_project_name()}!")


if __name__ == "__main__":
    main()
