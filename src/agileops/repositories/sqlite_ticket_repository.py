import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from agileops.database import connect, write_transaction
from agileops.domain.enums import (
    TicketEventType,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from agileops.domain.exceptions import SprintNotFoundError
from agileops.domain.models import Ticket, TicketEvent


def _to_ticket(row: sqlite3.Row) -> Ticket:
    return Ticket(
        ticket_id=row["ticket_id"],
        title=row["title"],
        description=row["description"],
        ticket_type=TicketType(row["ticket_type"]),
        priority=TicketPriority(row["priority"]),
        business_impact=row["business_impact"],
        created_by=row["created_by"],
        assigned_to=row["assigned_to"],
        status=TicketStatus(row["status"]),
        incident_id=row["incident_id"],
        sprint_id=row["sprint_id"],
    )


def _get_ticket(connection: sqlite3.Connection, ticket_id: str) -> Ticket | None:
    row = connection.execute(
        "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
    ).fetchone()
    return _to_ticket(row) if row is not None else None


def _to_event(row: sqlite3.Row) -> TicketEvent:
    previous_status = row["previous_status"]
    return TicketEvent(
        event_id=row["event_id"],
        ticket_id=row["ticket_id"],
        event_type=TicketEventType(row["event_type"]),
        previous_status=TicketStatus(previous_status)
        if previous_status is not None
        else None,
        new_status=TicketStatus(row["new_status"]),
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        actor=row["actor"],
        reason=row["reason"],
    )


def _append_event(
    connection: sqlite3.Connection,
    ticket: Ticket,
    event_type: TicketEventType,
    *,
    actor: str | None,
    reason: str | None,
    previous_status: TicketStatus | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO ticket_events (
            ticket_id, event_type, previous_status, new_status, occurred_at, actor, reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticket.ticket_id,
            event_type.value,
            previous_status.value if previous_status is not None else None,
            ticket.status.value,
            datetime.now(timezone.utc).isoformat(),
            (actor or "").strip() or "unspecified",
            (reason or "").strip() or "No reason provided",
        ),
    )


class SQLiteTicketRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create(self, build_ticket: Callable[[str], Ticket]) -> Ticket:
        with write_transaction(self.database_path) as connection:
            number = connection.execute(
                "SELECT next_number FROM ticket_number_sequence WHERE singleton = 1"
            ).fetchone()["next_number"]
            ticket = build_ticket(f"TASK-{number:03d}")
            connection.execute(
                "UPDATE ticket_number_sequence SET next_number = next_number + 1 WHERE singleton = 1"
            )
            connection.execute(
                """
                INSERT INTO tickets (
                    number, ticket_id, title, description, ticket_type, priority,
                    business_impact, created_by, assigned_to, status, incident_id, sprint_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    number,
                    ticket.ticket_id,
                    ticket.title,
                    ticket.description,
                    ticket.ticket_type.value,
                    ticket.priority.value,
                    ticket.business_impact,
                    ticket.created_by,
                    ticket.assigned_to,
                    ticket.status.value,
                    ticket.incident_id,
                    ticket.sprint_id,
                ),
            )
            _append_event(
                connection,
                ticket,
                TicketEventType.CREATED,
                actor=ticket.created_by,
                reason="Ticket created",
            )
        return ticket

    def get_by_id(self, ticket_id: str) -> Ticket | None:
        with connect(self.database_path) as connection:
            return _get_ticket(connection, ticket_id)

    def list_all(self) -> list[Ticket]:
        with connect(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM tickets ORDER BY number")
            return [_to_ticket(row) for row in rows]

    def list_by_incident(self, incident_id: str) -> list[Ticket] | None:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT tickets.*
                FROM incidents LEFT JOIN tickets USING (incident_id)
                WHERE incidents.incident_id = ?
                ORDER BY tickets.number
                """,
                (incident_id,),
            ).fetchall()
            if not rows:
                return None
            return [_to_ticket(row) for row in rows if row["ticket_id"] is not None]

    def list_by_sprint(self, sprint_id: str) -> list[Ticket] | None:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT tickets.*
                FROM sprints LEFT JOIN tickets USING (sprint_id)
                WHERE sprints.sprint_id = ?
                ORDER BY tickets.number
                """,
                (sprint_id,),
            ).fetchall()
            if not rows:
                return None
            return [_to_ticket(row) for row in rows if row["ticket_id"] is not None]

    def list_backlog(self) -> list[Ticket]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM tickets WHERE sprint_id IS NULL AND status <> ? ORDER BY number",
                (TicketStatus.DONE.value,),
            )
            return [_to_ticket(row) for row in rows]

    def set_sprint(self, ticket_id: str, sprint_id: str | None) -> Ticket | None:
        with write_transaction(self.database_path) as connection:
            ticket = _get_ticket(connection, ticket_id)
            if ticket is None:
                return None

            if sprint_id is not None:
                sprint = connection.execute(
                    "SELECT 1 FROM sprints WHERE sprint_id = ?", (sprint_id,)
                ).fetchone()
                if sprint is None:
                    raise SprintNotFoundError(f"Sprint {sprint_id} not found.")

            connection.execute(
                "UPDATE tickets SET sprint_id = ? WHERE ticket_id = ?",
                (sprint_id, ticket_id),
            )
            ticket.sprint_id = sprint_id
        return ticket

    def set_assignee(self, ticket_id: str, assigned_to: str | None) -> Ticket | None:
        with write_transaction(self.database_path) as connection:
            connection.execute(
                "UPDATE tickets SET assigned_to = ? WHERE ticket_id = ?",
                (assigned_to, ticket_id),
            )
            return _get_ticket(connection, ticket_id)

    def change_status(
        self,
        ticket_id: str,
        new_status: TicketStatus,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> Ticket | None:
        with write_transaction(self.database_path) as connection:
            ticket = _get_ticket(connection, ticket_id)
            if ticket is None:
                return None

            previous_status = ticket.status
            ticket.change_status(new_status)
            connection.execute(
                "UPDATE tickets SET status = ? WHERE ticket_id = ?",
                (ticket.status.value, ticket_id),
            )
            _append_event(
                connection,
                ticket,
                TicketEventType.STATUS_CHANGED,
                actor=actor,
                reason=reason,
                previous_status=previous_status,
            )
        return ticket

    def list_events(self, ticket_id: str) -> list[TicketEvent] | None:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT ticket_events.*
                FROM tickets LEFT JOIN ticket_events USING (ticket_id)
                WHERE tickets.ticket_id = ?
                ORDER BY ticket_events.event_id
                """,
                (ticket_id,),
            ).fetchall()
            if not rows:
                return None
            return [_to_event(row) for row in rows if row["event_id"] is not None]

    def count_completions(self, start_date: date, end_date: date) -> int:
        # Stored event timestamps start with their ISO-formatted UTC date.
        with connect(self.database_path) as connection:
            return connection.execute(
                """
                SELECT COUNT(*) FROM ticket_events
                WHERE event_type = 'status_changed' AND new_status = 'done'
                  AND occurred_at >= ? AND occurred_at < ?
                """,
                (start_date.isoformat(), end_date.isoformat()),
            ).fetchone()[0]
