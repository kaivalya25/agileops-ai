"""Connect a reported incident to a synthetic reporting failure and its workflow."""

from datetime import date, timedelta
from enum import Enum

from agileops.domain.enums import TicketPriority
from agileops.lab import read_report, run_refresh
from agileops.repositories.sqlite_incident_repository import SQLiteIncidentRepository
from agileops.repositories.sqlite_sprint_repository import SQLiteSprintRepository
from agileops.schemas.incidents import IncidentCreate, IncidentResponse
from agileops.schemas.sprints import SprintCreate
from agileops.workflow import WorkflowRuntime, WorkflowStart


class LabScenario(str, Enum):
    MISSING_COLUMN = "missing_column"
    SCHEMA_MISMATCH = "schema_mismatch"
    BAD_SQL = "bad_sql"
    INVALID_CONFIG = "invalid_config"
    DUPLICATE_DATA = "duplicate_data"


class LabIncidentCreate(IncidentCreate):
    scenario: LabScenario = LabScenario.MISSING_COLUMN
    priority: TicketPriority = TicketPriority.HIGH
    use_model: bool = False


def submit_lab_incident(runtime: WorkflowRuntime, data: LabIncidentCreate) -> dict:
    sprints = SQLiteSprintRepository(runtime.database_path)
    today = date.today()
    sprints.create_if_empty(
        SprintCreate(
            name="Reporting reliability",
            planned_start_date=today,
            planned_end_date=today + timedelta(days=13),
        ).to_domain
    )
    if not read_report(runtime.lab_path):
        run_refresh(runtime.lab_path)
    incident = SQLiteIncidentRepository(runtime.database_path).create(data.to_domain)
    failed = run_refresh(
        runtime.lab_path, scenario=data.scenario.value, incident_id=incident.incident_id
    )
    state = runtime.start(
        WorkflowStart(
            incident_id=incident.incident_id,
            correlation_id=failed["correlation_id"],
            priority=data.priority,
            use_model=data.use_model,
        ),
        verify_reporting_recovery=True,
    )
    return {
        "incident": IncidentResponse.model_validate(incident).model_dump(mode="json"),
        "failed_refresh": failed,
        "workflow": state,
    }
