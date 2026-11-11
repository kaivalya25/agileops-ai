"""Verified metrics and restricted analytical queries."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agileops.database import connect, write_transaction
from agileops.domain.enums import TicketStatus
from agileops.domain.ticket_metrics import calculate_ticket_metrics
from agileops.grounding import Evidence, GroundedAnswer, answer
from agileops.local_model import StructuredModel
from agileops.repositories.sqlite_ticket_repository import _to_event

FIELDS = {
    "bi_tickets": {
        "ticket_id",
        "ticket_type",
        "priority",
        "status",
        "sprint_id",
        "assigned_to",
        "incident_id",
    },
    "bi_sprints": {"sprint_id", "name", "planned_start_date", "planned_end_date"},
    "bi_events": {
        "ticket_id",
        "event_type",
        "previous_status",
        "new_status",
        "occurred_at",
    },
}


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    value: str | None


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: Literal["bi_tickets", "bi_sprints", "bi_events"]
    columns: list[str] = Field(default_factory=list, max_length=8)
    count: bool = False
    filters: list[QueryFilter] = Field(default_factory=list, max_length=8)
    limit: int = Field(default=25, ge=1, le=100)


def compile_query(plan: QueryPlan) -> tuple[str, tuple]:
    allowed = FIELDS[plan.dataset]
    if any(column not in allowed for column in plan.columns):
        raise ValueError("Requested output column is outside the analytical dataset.")
    if any(predicate.column not in allowed for predicate in plan.filters):
        raise ValueError("Requested filter is outside the analytical dataset.")
    columns = list(dict.fromkeys(plan.columns))
    projection = ", ".join(columns)
    if plan.count:
        projection = ", ".join([*columns, "COUNT(*) AS total"])
    if not projection:
        raise ValueError("Choose analytical columns or request a count.")
    predicates = [f"{predicate.column} IS ?" for predicate in plan.filters]
    sql = f"SELECT {projection} FROM {plan.dataset}"
    if predicates:
        sql += " WHERE " + " AND ".join(predicates)
    if plan.count and columns:
        sql += " GROUP BY " + ", ".join(columns)
    if columns:
        sql += " ORDER BY " + ", ".join(columns)
    return sql + " LIMIT ?", (
        *(predicate.value for predicate in plan.filters),
        plan.limit,
    )


def query_analytics(path: Path, plan: QueryPlan) -> dict:
    sql, parameters = compile_query(plan)
    with connect(path) as connection:
        connection.execute("PRAGMA query_only = ON")
        rows = [dict(row) for row in connection.execute(sql, parameters)]
    return {"sql": sql, "parameters": parameters, "rows": rows}


def ask_analytics(path: Path, question: str, model: StructuredModel) -> dict:
    plan = model.invoke(
        "Translate the user's analytical question into the given query plan schema. "
        "Use only the supplied datasets and columns. Only read-only reporting is supported.",
        {
            "question": question,
            "datasets": {view: sorted(fields) for view, fields in FIELDS.items()},
        },
        QueryPlan,
    )
    result = query_analytics(path, plan)
    evidence = [
        Evidence(id=f"row:{index}", source=plan.dataset, text=str(row))
        for index, row in enumerate(result["rows"], start=1)
    ]
    narrative = (
        answer(question, evidence, model)
        if evidence
        else GroundedAnswer(
            status="insufficient_evidence", answer="The query returned no rows."
        )
    )
    return {**result, "narrative": narrative.model_dump()}


def record_block(
    path: Path, ticket_id: str, blocked: bool, actor: str, reason: str
) -> bool | None:
    with write_transaction(path) as connection:
        ticket = connection.execute(
            "SELECT status FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if ticket is None:
            return None
        if blocked and ticket["status"] == TicketStatus.DONE.value:
            raise ValueError("A completed ticket cannot be blocked.")
        previous = connection.execute(
            "SELECT blocked FROM ticket_block_events WHERE ticket_id = ? ORDER BY event_id DESC LIMIT 1",
            (ticket_id,),
        ).fetchone()
        if bool(previous and previous["blocked"]) != blocked:
            connection.execute(
                """INSERT INTO ticket_block_events (ticket_id, blocked, actor, reason, occurred_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    ticket_id,
                    blocked,
                    actor,
                    reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return blocked


def _blocked_seconds(
    connection: sqlite3.Connection,
    ticket_id: str,
    until: datetime,
) -> tuple[float, bool]:
    rows = connection.execute(
        "SELECT blocked, occurred_at FROM ticket_block_events WHERE ticket_id = ? ORDER BY event_id",
        (ticket_id,),
    )
    start = None
    elapsed = 0.0
    for row in rows:
        timestamp = datetime.fromisoformat(row["occurred_at"])
        if timestamp > until:
            break
        if row["blocked"]:
            start = timestamp
        elif start is not None:
            elapsed += max(0.0, (timestamp - start).total_seconds())
            start = None
    return elapsed + (
        max(0.0, (until - start).total_seconds()) if start else 0
    ), start is not None


def portfolio(path: Path) -> dict:
    # Read a consistent SQLite snapshot while assembling the verified report.
    now = datetime.now(timezone.utc)
    with connect(path) as connection:
        connection.execute("BEGIN")
        tickets = [
            dict(row)
            for row in connection.execute("SELECT * FROM bi_tickets ORDER BY ticket_id")
        ]
        sprints = [
            dict(row)
            for row in connection.execute("SELECT * FROM bi_sprints ORDER BY sprint_id")
        ]
        summary = []
        for ticket in tickets:
            ticket_id = ticket["ticket_id"]
            events = [
                _to_event(row)
                for row in connection.execute(
                    "SELECT * FROM ticket_events WHERE ticket_id = ? ORDER BY event_id",
                    (ticket_id,),
                )
            ]
            metrics = calculate_ticket_metrics(ticket_id, events)
            finished = next(
                (
                    event.occurred_at
                    for event in reversed(events)
                    if event.new_status == TicketStatus.DONE
                ),
                None,
            )
            end = finished or now
            blocked, open_block = _blocked_seconds(connection, ticket_id, end)
            age = (
                max(0.0, (end - events[0].occurred_at).total_seconds())
                if events
                else None
            )
            summary.append(
                {
                    **ticket,
                    **vars(metrics),
                    "blocked_seconds": blocked,
                    "blocked": open_block and finished is None,
                    "age_seconds": age,
                    "reopened": any(
                        event.previous_status == TicketStatus.DONE for event in events
                    ),
                }
            )
    completed = sum(ticket["status"] == "done" for ticket in summary)
    completed_or_reopened = sum(
        ticket["status"] == "done" or ticket["reopened"] for ticket in summary
    )
    cycle_times = [
        ticket["cycle_time_seconds"]
        for ticket in summary
        if ticket["cycle_time_seconds"] is not None
    ]
    statuses = sorted({ticket["status"] for ticket in summary})
    return {
        "throughput": completed,
        "mean_cycle_time_seconds": sum(cycle_times) / len(cycle_times)
        if cycle_times
        else None,
        "reopen_rate": sum(ticket["reopened"] for ticket in summary)
        / completed_or_reopened
        if completed_or_reopened
        else None,
        "bottlenecks": {
            status: sum(ticket["status"] == status for ticket in summary)
            for status in statuses
        },
        "sprints": [
            {
                **sprint,
                "tickets": sum(
                    ticket["sprint_id"] == sprint["sprint_id"] for ticket in summary
                ),
                "completed": sum(
                    ticket["sprint_id"] == sprint["sprint_id"]
                    and ticket["status"] == "done"
                    for ticket in summary
                ),
            }
            for sprint in sprints
        ],
        "tickets": summary,
    }
