import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from agileops.database import connect, write_transaction
from agileops.domain.enums import TicketEventType, TicketPriority, TicketStatus, TicketType
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
    )


def _to_event(row: sqlite3.Row) -> TicketEvent:
    previous_status = row["previous_status"]
    return TicketEvent(
        event_id=row["event_id"],
        ticket_id=row["ticket_id"],
        event_type=TicketEventType(row["event_type"]),
        previous_status=TicketStatus(previous_status) if previous_status is not None else None,
        new_status=TicketStatus(row["new_status"]),
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
    )


def _append_event(
    connection: sqlite3.Connection,
    ticket: Ticket,
    event_type: TicketEventType,
    previous_status: TicketStatus | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO ticket_events (ticket_id, event_type, previous_status, new_status, occurred_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ticket.ticket_id,
            event_type.value,
            previous_status.value if previous_status is not None else None,
            ticket.status.value,
            datetime.now(timezone.utc).isoformat(),
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
                    business_impact, created_by, assigned_to, status, incident_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            _append_event(connection, ticket, TicketEventType.CREATED)
        return ticket

    def get_by_id(self, ticket_id: str) -> Ticket | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            return _to_ticket(row) if row is not None else None

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

    def change_status(self, ticket_id: str, new_status: TicketStatus) -> Ticket | None:
        with write_transaction(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if row is None:
                return None

            ticket = _to_ticket(row)
            previous_status = ticket.status
            ticket.change_status(new_status)
            connection.execute(
                "UPDATE tickets SET status = ? WHERE ticket_id = ?",
                (ticket.status.value, ticket_id),
            )
            _append_event(connection, ticket, TicketEventType.STATUS_CHANGED, previous_status)
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
