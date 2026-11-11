import hmac
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agileops.analytics import (
    QueryPlan,
    ask_analytics,
    portfolio,
    query_analytics,
    record_block,
)
from agileops.grounding import Evidence, GroundedAnswer, answer
from agileops.investigation import DiagnosticTools, InvestigationReport, investigate
from agileops.knowledge import KnowledgeBase, Reranker, SearchFilters
from agileops.lab_intake import LabIncidentCreate, submit_lab_incident
from agileops.local_model import ModelError, OllamaModel
from agileops.workflow import (
    Approval,
    WorkflowConflict,
    WorkflowExecutionError,
    WorkflowRuntime,
    WorkflowStart,
)

router = APIRouter(tags=["automation"])
DASHBOARD = Path(__file__).parents[2] / "assets" / "dashboard.html"
REVIEW = DASHBOARD.with_name("workflow.html")
INTAKE = DASHBOARD.with_name("intake.html")
ApprovalToken = Annotated[str | None, Header(alias="X-AgileOps-Approval-Token")]


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class KnowledgeQuestion(Question):
    filters: SearchFilters | None = None
    k: int = Field(default=3, ge=1, le=10)
    rerank: bool = False


class BlockUpdate(BaseModel):
    blocked: bool
    actor: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)


def _approval_authorized(token: str | None) -> None:
    expected = os.getenv("AGILEOPS_APPROVAL_TOKEN")
    if not expected:
        raise HTTPException(
            503, "Configure AGILEOPS_APPROVAL_TOKEN to enable approval endpoints."
        )
    if token is None or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(403, "Approval token is invalid.")


def _available(action):
    try:
        return action()
    except WorkflowExecutionError as error:
        raise HTTPException(
            503, {"workflow_id": error.workflow_id, "error": str(error)}
        ) from error
    except (ModelError, FileNotFoundError, ImportError) as error:
        raise HTTPException(503, str(error)) from error
    except WorkflowConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def _found(result, description: str):
    if result is None:
        raise HTTPException(404, f"{description} not found.")
    return result


@router.post("/knowledge/ask")
def ask_knowledge(question: KnowledgeQuestion, request: Request) -> GroundedAnswer:
    """Retrieve relevant sources and return verified excerpts from the local model."""

    def run():
        knowledge = KnowledgeBase(request.app.state.workflow.knowledge_path)
        hits = knowledge.search(
            question.question,
            k=question.k,
            filters=question.filters,
            reranker=Reranker() if question.rerank else None,
        )
        evidence = [
            Evidence(id=hit.chunk.id, source=hit.chunk.source, text=hit.chunk.text)
            for hit in hits
        ]
        return answer(question.question, evidence, OllamaModel())

    return _available(run)


@router.get("/incidents/{incident_id}/investigation")
def investigate_incident(
    incident_id: str,
    request: Request,
    correlation_id: str | None = None,
    use_model: bool = False,
) -> InvestigationReport:
    """Inspect current incident diagnostics and return a grounded hypothesis or abstention."""
    runtime: WorkflowRuntime = request.app.state.workflow

    def run():
        knowledge = (
            KnowledgeBase(runtime.knowledge_path)
            if runtime.knowledge_path.is_file()
            else None
        )
        return investigate(
            incident_id,
            DiagnosticTools(runtime.database_path, runtime.lab_path, knowledge),
            correlation_id=correlation_id,
            model=OllamaModel() if use_model else None,
        )

    return _found(_available(run), "Incident")


@router.post("/workflows", status_code=201)
def start_workflow(payload: WorkflowStart, request: Request) -> dict:
    """Run intake and investigation to the first operator approval."""
    return _found(
        _available(lambda: request.app.state.workflow.start(payload)), "Incident"
    )


@router.post("/lab/incidents", status_code=201)
def submit_reporting_incident(
    payload: LabIncidentCreate, request: Request, token: ApprovalToken = None
) -> dict:
    """Record a synthetic reporting failure and start its incident workflow."""
    _approval_authorized(token)
    return _available(lambda: submit_lab_incident(request.app.state.workflow, payload))


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, request: Request) -> dict:
    """Read the latest checkpoint, pending approval and current workflow state."""
    return _found(
        _available(lambda: request.app.state.workflow.get(workflow_id)), "Workflow"
    )


@router.get("/workflows/{workflow_id}/audit")
def read_audit(workflow_id: str, request: Request) -> list[dict]:
    """List immutable workflow audit events in write order."""
    get_workflow(workflow_id, request)
    return request.app.state.workflow.audit(workflow_id)


@router.post("/workflows/{workflow_id}/approve")
def approve_workflow(
    workflow_id: str,
    approval: Approval,
    request: Request,
    token: ApprovalToken = None,
) -> dict:
    """Apply an operator decision to the matching pending gate."""
    _approval_authorized(token)
    result = _available(
        lambda: request.app.state.workflow.resume(workflow_id, approval)
    )
    return _found(result, "Workflow")


@router.post("/workflows/{workflow_id}/retry")
def retry_workflow(
    workflow_id: str, request: Request, token: ApprovalToken = None
) -> dict:
    """Resume a failed checkpoint or recheck unresolved dependencies."""
    _approval_authorized(token)
    result = _available(lambda: request.app.state.workflow.resume(workflow_id, None))
    return _found(result, "Workflow")


@router.patch("/tickets/{ticket_id}/blocked")
def update_block(ticket_id: str, update: BlockUpdate, request: Request) -> dict:
    """Start or end a blocked interval for a ticket."""
    blocked = _available(
        lambda: record_block(
            request.app.state.workflow.database_path,
            ticket_id,
            update.blocked,
            update.actor,
            update.reason,
        )
    )
    return {"ticket_id": ticket_id, "blocked": _found(blocked, "Ticket")}


@router.get("/bi/portfolio")
def get_portfolio(request: Request) -> dict:
    """Calculate sprint and ticket metrics from one database snapshot."""
    return portfolio(request.app.state.workflow.database_path)


@router.get("/sprints/{sprint_id}/review")
def get_sprint_review(sprint_id: str, request: Request) -> dict:
    """Summarize sprint progress, blocked tickets and retrospective metrics."""
    report = get_portfolio(request)
    sprint = _found(
        next(
            (item for item in report["sprints"] if item["sprint_id"] == sprint_id), None
        ),
        "Sprint",
    )
    tickets = [
        ticket for ticket in report["tickets"] if ticket["sprint_id"] == sprint_id
    ]
    return {
        "sprint": sprint,
        "standup": {
            "done": [
                ticket["ticket_id"] for ticket in tickets if ticket["status"] == "done"
            ],
            "open": [
                ticket["ticket_id"] for ticket in tickets if ticket["status"] != "done"
            ],
            "blocked": [ticket["ticket_id"] for ticket in tickets if ticket["blocked"]],
        },
        "retrospective": {
            "returns_from_qa": sum(ticket["qa_return_count"] for ticket in tickets),
            "blocked_seconds": sum(ticket["blocked_seconds"] for ticket in tickets),
        },
    }


@router.post("/bi/query")
def run_query(plan: QueryPlan, request: Request) -> dict:
    """Compile and execute a parameterized SELECT over one authorized analytical view."""
    return _available(
        lambda: query_analytics(request.app.state.workflow.database_path, plan)
    )


@router.post("/bi/ask")
def ask_bi(question: Question, request: Request) -> dict:
    """Translate a natural language question to a restricted query and explain the verified rows."""
    return _available(
        lambda: ask_analytics(
            request.app.state.workflow.database_path, question.question, OllamaModel()
        )
    )


@router.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD, media_type="text/html")


@router.get("/", include_in_schema=False)
def incident_intake() -> FileResponse:
    return FileResponse(INTAKE, media_type="text/html")


@router.get("/workflows/{workflow_id}/review", include_in_schema=False)
def workflow_review(workflow_id: str) -> FileResponse:
    return FileResponse(REVIEW, media_type="text/html")
