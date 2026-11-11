"""Persistent, approval-gated workflow for the reporting lab."""

import json
import os
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agileops.agents import EngineeringHandoff, analyze_business_needs, plan_delivery
from agileops.analytics import portfolio
from agileops.database import connect, write_transaction
from agileops.domain.enums import TicketPriority, TicketStatus
from agileops.engineering import (
    EngineeringPlan,
    apply_patch,
    approved_report_query,
    prepare_repository,
    propose_patch,
    review_patch,
    validate_patch,
)
from agileops.investigation import DiagnosticTools, investigate
from agileops.knowledge import KnowledgeBase
from agileops.lab import run_refresh
from agileops.local_model import OllamaModel
from agileops.repositories.sqlite_sprint_repository import SQLiteSprintRepository
from agileops.repositories.sqlite_ticket_repository import SQLiteTicketRepository

TOOL_PERMISSIONS = {
    "business_analyst": {"analyze_incident"},
    "investigator": {"investigate_incident"},
    "project_manager": {"plan_delivery"},
    "scrum_master": {"plan_sprint"},
    "engineer": {"inspect_repository", "apply_reporting_patch"},
    "security": {"review_patch"},
    "qa": {"validate_reporting_patch", "verify_reporting_recovery"},
    "bi": {"read_portfolio"},
}
MAX_TOOL_CALLS = 24
MAX_ENGINEERING_ATTEMPTS = 2


class WorkflowConflict(ValueError):
    pass


class WorkflowExecutionError(RuntimeError):
    def __init__(self, workflow_id: str, cause: Exception) -> None:
        super().__init__(type(cause).__name__)
        self.workflow_id = workflow_id


class WorkflowStart(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "incident_id": "INC 26-0001",
                    "priority": "high",
                    "use_model": False,
                }
            ]
        }
    )

    incident_id: str
    priority: TicketPriority = TicketPriority.HIGH
    correlation_id: str | None = None
    depends_on: list[str] = Field(default_factory=list, max_length=12)
    use_model: bool = False


class Approval(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "gate": "remediation",
                    "approved": True,
                    "actor": "Lab operator",
                    "reason": "Reviewed the controlled SQL plan.",
                }
            ]
        }
    )

    gate: Literal["priority_and_scope", "remediation", "release"]
    approved: bool
    actor: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)


class State(TypedDict, total=False):
    workflow_id: str
    incident_id: str
    correlation_id: str | None
    priority: str
    depends_on: list[str]
    use_model: bool
    status: str
    requirements: dict
    investigation: dict
    ticket_id: str
    delivery: dict
    plan: dict
    engineering: dict
    security: dict
    qa: dict
    attempts: int
    analytics: dict
    unresolved_dependencies: list[str]
    verify_reporting_recovery: bool
    reporting_recovery: dict


class WorkflowRuntime:
    def __init__(self, database_path: Path, root: Path | None = None) -> None:
        self.database_path = database_path
        self.root = (
            root or Path(os.getenv("AGILEOPS_WORKFLOW_DIR", "tmp/workflows"))
        ).resolve()
        self.checkpoints = self.root / "checkpoints.db"
        self.audit_path = self.root / "audit.db"
        self.lab_path = Path(os.getenv("AGILEOPS_LAB_DB", "tmp/reporting-lab.db"))
        self.knowledge_path = Path(
            os.getenv("AGILEOPS_KNOWLEDGE_DB", "tmp/knowledge.db")
        )
        self.tickets = SQLiteTicketRepository(database_path)

    def _audit(self, workflow_id: str, category: str, actor: str, **detail) -> None:
        with write_transaction(self.audit_path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS workflow_audit (
                    event_id INTEGER PRIMARY KEY, workflow_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, category TEXT NOT NULL, actor TEXT NOT NULL,
                    detail TEXT NOT NULL
                )"""
            )
            for operation in ("UPDATE", "DELETE"):
                connection.execute(
                    f"""CREATE TRIGGER IF NOT EXISTS workflow_audit_no_{operation.lower()}
                        BEFORE {operation} ON workflow_audit BEGIN
                        SELECT RAISE(ABORT, 'workflow audit is append-only'); END"""
                )
            connection.execute(
                """CREATE TRIGGER IF NOT EXISTS workflow_audit_no_replace
                   BEFORE INSERT ON workflow_audit
                   WHEN EXISTS (SELECT 1 FROM workflow_audit WHERE event_id = NEW.event_id)
                   BEGIN SELECT RAISE(ABORT, 'workflow audit is append-only'); END"""
            )
            connection.execute(
                """INSERT INTO workflow_audit (workflow_id, occurred_at, category, actor, detail)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    workflow_id,
                    datetime.now(timezone.utc).isoformat(),
                    category,
                    actor,
                    json.dumps(detail, default=str),
                ),
            )

    def audit(self, workflow_id: str) -> list[dict]:
        if not self.audit_path.is_file():
            return []
        with connect(self.audit_path) as connection:
            rows = connection.execute(
                "SELECT * FROM workflow_audit WHERE workflow_id = ? ORDER BY event_id",
                (workflow_id,),
            )
            return [{**dict(row), "detail": json.loads(row["detail"])} for row in rows]

    def _tool(self, state: State, agent: str, tool: str, action: Callable, **inputs):
        workflow_id = state["workflow_id"]
        if tool not in TOOL_PERMISSIONS.get(agent, set()):
            self._audit(workflow_id, "tool_denied", agent, tool=tool)
            raise PermissionError(f"{agent} cannot call {tool}.")
        calls = sum(
            event["category"] == "tool_started" for event in self.audit(workflow_id)
        )
        if calls >= MAX_TOOL_CALLS:
            raise WorkflowConflict("The workflow tool budget has been exhausted.")
        self._audit(workflow_id, "tool_started", agent, tool=tool, inputs=inputs)
        start = monotonic()
        try:
            output = action()
        except Exception as error:
            self._audit(
                workflow_id,
                "tool_failed",
                agent,
                tool=tool,
                error=type(error).__name__,
                latency_seconds=monotonic() - start,
            )
            raise
        if isinstance(output, BaseModel):
            output = output.model_dump(mode="json")
        self._audit(
            workflow_id,
            "tool_completed",
            agent,
            tool=tool,
            output=output,
            latency_seconds=monotonic() - start,
        )
        return output

    def _tools(self) -> DiagnosticTools:
        knowledge = (
            KnowledgeBase(self.knowledge_path)
            if self.knowledge_path.is_file()
            else None
        )
        return DiagnosticTools(self.database_path, self.lab_path, knowledge)

    def _model(self, state: State, agent: str):
        if not state.get("use_model"):
            return None
        return OllamaModel(
            observe=lambda **detail: self._audit(
                state["workflow_id"], "model_call", agent, **detail
            )
        )

    def _transition(self, state: State, target: TicketStatus, reason: str) -> None:
        ticket = self.tickets.get_by_id(state["ticket_id"])
        if ticket and ticket.status != target:
            self.tickets.change_status(
                ticket.ticket_id, target, actor="agileops-workflow", reason=reason
            )
            self._audit(
                state["workflow_id"],
                "transition",
                "agileops-workflow",
                ticket_id=ticket.ticket_id,
                status=target.value,
                reason=reason,
            )

    def _approval_node(self, gate: str, data: Callable):
        from langgraph.types import interrupt

        def wait_for_approval(state: State) -> dict:
            approval = Approval.model_validate(interrupt({"gate": gate, **data(state)}))
            if approval.gate != gate:
                raise WorkflowConflict("The approval gate does not match.")
            return {"status": "running" if approval.approved else "rejected"}

        return wait_for_approval

    def _graph(self, saver):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(State)

        def analyze(state: State) -> dict:
            tools = self._tools()
            incident = tools.get_incident(state["incident_id"])
            requirements = self._tool(
                state,
                "business_analyst",
                "analyze_incident",
                lambda: analyze_business_needs(
                    incident, tools.knowledge, self._model(state, "business_analyst")
                ),
                incident_id=state["incident_id"],
            )
            return {"requirements": requirements, "status": "running"}

        def investigate_incident(state: State) -> dict:
            report = self._tool(
                state,
                "investigator",
                "investigate_incident",
                lambda: investigate(
                    state["incident_id"],
                    self._tools(),
                    correlation_id=state.get("correlation_id"),
                    model=self._model(state, "investigator"),
                ),
                incident_id=state["incident_id"],
                correlation_id=state.get("correlation_id"),
            )
            status = (
                "running"
                if report["status"] == "hypothesis"
                else "insufficient_evidence"
            )
            return {"investigation": report, "status": status}

        def schedule(state: State) -> dict:
            incident = self._tools().get_incident(state["incident_id"])
            linked = self.tickets.list_by_incident(incident.incident_id) or []
            priority = TicketPriority(state["priority"])
            ticket = next(
                (
                    item
                    for item in linked
                    if item.status != TicketStatus.DONE and item.priority == priority
                ),
                None,
            )
            if ticket is None:
                ticket = self.tickets.create(
                    lambda ticket_id: incident.create_ticket_from_incident(
                        ticket_id, priority
                    )
                )
            unresolved = []
            for key in state.get("depends_on", []):
                dependency = self.tickets.get_by_id(key)
                if dependency is None or dependency.status != TicketStatus.DONE:
                    unresolved.append(key)
            delivery = self._tool(
                state,
                "project_manager",
                "plan_delivery",
                lambda: plan_delivery(
                    ticket,
                    SQLiteSprintRepository(self.database_path).list_all(),
                    date.today(),
                ),
                ticket_id=ticket.ticket_id,
                depends_on=state.get("depends_on", []),
            )
            if unresolved:
                return {
                    "ticket_id": ticket.ticket_id,
                    "delivery": delivery,
                    "unresolved_dependencies": unresolved,
                    "status": "awaiting_dependencies",
                }
            sprint_id = delivery["sprint_id"]
            if sprint_id and ticket.sprint_id != sprint_id:
                self._tool(
                    state,
                    "scrum_master",
                    "plan_sprint",
                    lambda: self.tickets.set_sprint(
                        ticket.ticket_id, sprint_id
                    ).to_dict(),
                    ticket_id=ticket.ticket_id,
                    sprint_id=sprint_id,
                )
            scheduled = {**state, "ticket_id": ticket.ticket_id}
            if ticket.status == TicketStatus.NEW:
                self._transition(
                    scheduled, TicketStatus.INVESTIGATING, "Investigation recorded."
                )
            if (
                self.tickets.get_by_id(ticket.ticket_id).status
                == TicketStatus.INVESTIGATING
            ):
                self._transition(
                    scheduled,
                    TicketStatus.READY_FOR_DEV,
                    "Priority and scope approved.",
                )
            return {
                "ticket_id": ticket.ticket_id,
                "delivery": delivery,
                "unresolved_dependencies": [],
            }

        def plan_patch(state: State) -> dict:
            handoff = EngineeringHandoff.model_validate(
                {
                    "ticket_id": state["ticket_id"],
                    "requirements": state["requirements"],
                    "investigation": state["investigation"],
                }
            )
            plan = self._tool(
                state,
                "engineer",
                "inspect_repository",
                lambda: propose_patch(prepare_repository(self.root), handoff),
                ticket_id=state["ticket_id"],
                diagnosis=handoff.investigation.diagnosis_code,
            )
            return {"plan": plan} if plan else {"status": "manual_review"}

        def engineer(state: State) -> dict:
            ticket = self.tickets.get_by_id(state["ticket_id"])
            if ticket.status in {TicketStatus.READY_FOR_DEV, TicketStatus.QA}:
                self._transition(
                    state, TicketStatus.IN_PROGRESS, "Approved lab remediation started."
                )
            result = self._tool(
                state,
                "engineer",
                "apply_reporting_patch",
                lambda: apply_patch(
                    self.root,
                    prepare_repository(self.root),
                    state["workflow_id"],
                    EngineeringPlan.model_validate(state["plan"]),
                ),
                plan=state["plan"],
            )
            if (
                self.tickets.get_by_id(state["ticket_id"]).status
                == TicketStatus.IN_PROGRESS
            ):
                self._transition(
                    state, TicketStatus.QA, "Lab patch submitted for independent QA."
                )
            return {"engineering": result, "attempts": state.get("attempts", 0) + 1}

        def qa(state: State) -> dict:
            security = self._tool(
                state,
                "security",
                "review_patch",
                lambda: review_patch(self.root, state["workflow_id"]),
                ticket_id=state["ticket_id"],
            )
            if not security["passed"]:
                return {"security": security, "qa": security, "status": "qa_failed"}
            result = self._tool(
                state,
                "qa",
                "validate_reporting_patch",
                lambda: validate_patch(self.root, state["workflow_id"]),
                ticket_id=state["ticket_id"],
                workspace=state["engineering"]["workspace"],
            )
            if result["passed"]:
                return {"qa": result, "security": security, "status": "running"}
            status = (
                "retry_engineering"
                if state["attempts"] < MAX_ENGINEERING_ATTEMPTS
                else "qa_failed"
            )
            return {"qa": result, "security": security, "status": status}

        def finish(state: State) -> dict:
            result = self._tool(
                state,
                "qa",
                "validate_reporting_patch",
                lambda: validate_patch(self.root, state["workflow_id"]),
                ticket_id=state["ticket_id"],
                checkpoint="release",
            )
            if not result["passed"]:
                return {"qa": result, "status": "qa_failed"}
            recovery = {}
            if state.get("verify_reporting_recovery"):
                refresh = self._tool(
                    state,
                    "qa",
                    "verify_reporting_recovery",
                    lambda: run_refresh(
                        self.lab_path,
                        incident_id=state["incident_id"],
                        report_sql=approved_report_query(
                            self.root, state["workflow_id"]
                        ),
                    ),
                    incident_id=state["incident_id"],
                )
                recovery["reporting_recovery"] = refresh
                if refresh["status"] != "completed":
                    return {**recovery, "status": "recovery_failed"}
            self._transition(
                state,
                TicketStatus.DONE,
                "Independent QA and human release approval recorded.",
            )
            analytics = self._tool(
                state, "bi", "read_portfolio", lambda: portfolio(self.database_path)
            )
            return {**recovery, "analytics": analytics, "status": "completed"}

        graph.add_node("business_analyst", analyze)
        graph.add_node("investigator", investigate_incident)
        graph.add_node(
            "approve_scope",
            self._approval_node(
                "priority_and_scope",
                lambda state: {
                    "requirements": state["requirements"],
                    "priority": state["priority"],
                },
            ),
        )
        graph.add_node("schedule", schedule)
        graph.add_node("engineering_plan", plan_patch)
        graph.add_node(
            "approve_remediation",
            self._approval_node(
                "remediation",
                lambda state: {"plan": state["plan"]},
            ),
        )
        graph.add_node("engineer", engineer)
        graph.add_node("qa", qa)
        graph.add_node(
            "approve_release",
            self._approval_node(
                "release",
                lambda state: {
                    "qa": state["qa"],
                    "patch": state["engineering"]["patch"],
                },
            ),
        )
        graph.add_node("finish", finish)
        graph.add_edge(START, "business_analyst")
        graph.add_edge("business_analyst", "investigator")
        for source, target in (
            ("investigator", "approve_scope"),
            ("approve_scope", "schedule"),
            ("schedule", "engineering_plan"),
            ("engineering_plan", "approve_remediation"),
            ("approve_remediation", "engineer"),
            ("approve_release", "finish"),
        ):
            graph.add_conditional_edges(
                source,
                lambda state: state["status"] == "running",
                {True: target, False: END},
            )
        graph.add_edge("engineer", "qa")
        graph.add_conditional_edges(
            "qa",
            lambda state: state["status"],
            {
                "running": "approve_release",
                "retry_engineering": "engineer",
                "qa_failed": END,
            },
        )
        graph.add_edge("finish", END)
        return graph.compile(checkpointer=saver)

    @staticmethod
    def _config(workflow_id: str) -> dict:
        return {"configurable": {"thread_id": workflow_id}, "recursion_limit": 24}

    @staticmethod
    def _snapshot(graph, config: dict) -> dict | None:
        state = graph.get_state(config)
        if not state.values:
            return None
        pending = state.interrupts[0].value if state.interrupts else None
        return {
            **state.values,
            "pending_approval": pending,
            "status": "awaiting_approval" if pending else state.values.get("status"),
            "next": list(state.next),
        }

    def start(
        self, request: WorkflowStart, *, verify_reporting_recovery: bool = False
    ) -> dict | None:
        from langgraph.checkpoint.sqlite import SqliteSaver

        if self._tools().get_incident(request.incident_id) is None:
            return None
        self.root.mkdir(parents=True, exist_ok=True)
        workflow_id = uuid4().hex
        config = self._config(workflow_id)
        with (
            write_transaction(self.root / "workflow-lock.db"),
            SqliteSaver.from_conn_string(str(self.checkpoints)) as saver,
        ):
            graph = self._graph(saver)
            self._audit(
                workflow_id, "started", "user", inputs=request.model_dump(mode="json")
            )
            self._invoke(
                graph,
                {
                    **request.model_dump(mode="json"),
                    "workflow_id": workflow_id,
                    "verify_reporting_recovery": verify_reporting_recovery,
                },
                config,
            )
            return self._snapshot(graph, config)

    def _invoke(self, graph, value, config: dict) -> None:
        workflow_id = config["configurable"]["thread_id"]
        try:
            graph.invoke(value, config)
        except Exception as error:
            self._audit(workflow_id, "failed", "workflow", error=type(error).__name__)
            raise WorkflowExecutionError(workflow_id, error) from error
        snapshot = self._snapshot(graph, config)
        self._audit(
            workflow_id,
            "checkpoint",
            "workflow",
            status=snapshot["status"],
            pending=snapshot["pending_approval"]["gate"]
            if snapshot["pending_approval"]
            else None,
        )

    def get(self, workflow_id: str) -> dict | None:
        from langgraph.checkpoint.sqlite import SqliteSaver

        if not self.checkpoints.is_file():
            return None
        with SqliteSaver.from_conn_string(str(self.checkpoints)) as saver:
            return self._snapshot(self._graph(saver), self._config(workflow_id))

    def resume(self, workflow_id: str, approval: Approval | None) -> dict | None:
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.types import Command

        if not self.checkpoints.is_file():
            return None
        config = self._config(workflow_id)
        with (
            write_transaction(self.root / "workflow-lock.db"),
            SqliteSaver.from_conn_string(str(self.checkpoints)) as saver,
        ):
            graph = self._graph(saver)
            current = self._snapshot(graph, config)
            if current is None:
                return None
            pending = current["pending_approval"]
            if approval is None:
                if current["status"] == "awaiting_dependencies":
                    graph.update_state(
                        config, {"status": "running"}, as_node="approve_scope"
                    )
                elif pending or not current["next"]:
                    raise WorkflowConflict("This workflow cannot be retried.")
                self._invoke(graph, None, config)
            else:
                if not pending or pending["gate"] != approval.gate:
                    raise WorkflowConflict(
                        "The workflow is waiting for a different action."
                    )
                self._audit(
                    workflow_id,
                    "approval",
                    approval.actor,
                    gate=approval.gate,
                    approved=approval.approved,
                    reason=approval.reason,
                )
                self._invoke(graph, Command(resume=approval.model_dump()), config)
            return self._snapshot(graph, config)
