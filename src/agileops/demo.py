"""Seed and run the synthetic dashboard refresh incident."""

import argparse
import json
from pathlib import Path

from agileops.database import migrate
from agileops.lab import read_report
from agileops.lab_intake import LabIncidentCreate, submit_lab_incident
from agileops.workflow import Approval, WorkflowRuntime


def run_demo(
    workspace: Path, *, approve_lab: bool = False, use_model: bool = False
) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    database_path = workspace / "agileops.db"
    migrate(database_path)
    runtime = WorkflowRuntime(database_path, workspace / "workflows")
    runtime.lab_path = workspace / "reporting.db"
    runtime.knowledge_path = workspace / "knowledge.db"
    submitted = submit_lab_incident(
        runtime,
        LabIncidentCreate(
            summary="Sales dashboard refresh failed after a reporting schema change.",
            reported_by="Reporting operations",
            business_impact="Executive regional sales totals are stale.",
            affected_system="Sales dashboard",
            use_model=use_model,
        ),
    )
    state = submitted["workflow"]
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
    return {
        "database": str(database_path.resolve()),
        "reporting_database": str(runtime.lab_path.resolve()),
        "workflow_directory": str(runtime.root),
        "incident_id": submitted["incident"]["incident_id"],
        "failed_refresh": submitted["failed_refresh"],
        "recovery": state.get("reporting_recovery"),
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
