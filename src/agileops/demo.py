"""Seed and run the synthetic dashboard refresh incident."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from agileops.database import migrate
from agileops.lab import read_report, run_refresh
from agileops.repositories.sqlite_incident_repository import SQLiteIncidentRepository
from agileops.repositories.sqlite_sprint_repository import SQLiteSprintRepository
from agileops.schemas.incidents import IncidentCreate
from agileops.schemas.sprints import SprintCreate
from agileops.workflow import Approval, WorkflowRuntime, WorkflowStart


def run_demo(
    workspace: Path, *, approve_lab: bool = False, use_model: bool = False
) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    database_path = workspace / "agileops.db"
    migrate(database_path)
    runtime = WorkflowRuntime(database_path, workspace / "workflows")
    runtime.lab_path = workspace / "reporting.db"
    runtime.knowledge_path = workspace / "knowledge.db"
    today = date.today()
    sprints = SQLiteSprintRepository(database_path)
    if not sprints.list_all():
        sprints.create(
            SprintCreate(
                name="Reporting reliability",
                planned_start_date=today,
                planned_end_date=today + timedelta(days=13),
            ).to_domain
        )
    incident = SQLiteIncidentRepository(database_path).create(
        IncidentCreate(
            summary="Sales dashboard refresh failed after a reporting schema change.",
            reported_by="Reporting operations",
            business_impact="Executive regional sales totals are stale.",
            affected_system="Sales dashboard",
        ).to_domain
    )
    run_refresh(runtime.lab_path)
    failed = run_refresh(
        runtime.lab_path, scenario="missing_column", incident_id=incident.incident_id
    )
    state = runtime.start(
        WorkflowStart(
            incident_id=incident.incident_id,
            correlation_id=failed["correlation_id"],
            use_model=use_model,
        )
    )
    if approve_lab:
        while state["pending_approval"]:
            state = runtime.resume(
                state["workflow_id"],
                Approval(
                    gate=state["pending_approval"]["gate"],
                    approved=True,
                    actor="Lab demo operator",
                    reason="Approved for the synthetic reporting lab.",
                ),
            )
    recovery = (
        run_refresh(runtime.lab_path, incident_id=incident.incident_id)
        if state["status"] == "completed"
        else None
    )
    return {
        "database": str(database_path.resolve()),
        "reporting_database": str(runtime.lab_path.resolve()),
        "workflow_directory": str(runtime.root),
        "incident_id": incident.incident_id,
        "failed_refresh": failed,
        "recovery": recovery,
        "report": read_report(runtime.lab_path),
        "workflow": state,
        "audit": runtime.audit(state["workflow_id"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("tmp/demo"))
    parser.add_argument("--approve-lab", action="store_true")
    parser.add_argument("--use-model", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_demo(
                args.workspace, approve_lab=args.approve_lab, use_model=args.use_model
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
