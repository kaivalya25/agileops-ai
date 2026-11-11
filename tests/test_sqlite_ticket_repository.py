import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from agileops import database
from agileops.domain.enums import (
    TicketEventType,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from agileops.domain.exceptions import InvalidStatusTransitionError
from agileops.domain.models import Ticket
from agileops.repositories.sqlite_ticket_repository import SQLiteTicketRepository


def build_ticket(ticket_id):
    return Ticket(
        ticket_id=ticket_id,
        title="Fix dashboard",
        description="Repair sales dashboard refresh.",
        ticket_type=TicketType.INCIDENT,
        priority=TicketPriority.HIGH,
        business_impact="Executive reporting unavailable.",
        created_by="Finance Executive",
    )


def test_failed_migration_rolls_back_schema_and_version(database_path, monkeypatch):
    original_migrations = database.MIGRATIONS
    monkeypatch.setattr(
        database,
        "MIGRATIONS",
        original_migrations
        + (
            ("CREATE TABLE added_table (id INTEGER PRIMARY KEY)",),
            ("CREATE TABLE added_table (id INTEGER PRIMARY KEY)",),
        ),
    )

    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        database.migrate(database_path)

    with database.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == len(
            original_migrations
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'added_table'"
            ).fetchone()
            is None
        )


def test_failed_event_write_rolls_back_ticket_and_number(database_path):
    repository = SQLiteTicketRepository(database_path)
    with database.write_transaction(database_path) as connection:
        connection.execute("""
            CREATE TRIGGER reject_creation_event BEFORE INSERT ON ticket_events
            WHEN NEW.event_type = 'created'
            BEGIN
                SELECT RAISE(ABORT, 'creation event rejected');
            END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="creation event rejected"):
        repository.create(build_ticket)
    assert repository.list_all() == []
    assert repository.list_events("TASK-001") is None

    with database.write_transaction(database_path) as connection:
        connection.execute("DROP TRIGGER reject_creation_event")
    assert repository.create(build_ticket).ticket_id == "TASK-001"


def test_failed_event_write_rolls_back_status(database_path):
    repository = SQLiteTicketRepository(database_path)
    ticket = repository.create(build_ticket)
    with database.write_transaction(database_path) as connection:
        connection.execute("""
            CREATE TRIGGER reject_status_event BEFORE INSERT ON ticket_events
            WHEN NEW.event_type = 'status_changed'
            BEGIN
                SELECT RAISE(ABORT, 'status event rejected');
            END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="status event rejected"):
        repository.change_status(ticket.ticket_id, TicketStatus.INVESTIGATING)

    assert repository.get_by_id(ticket.ticket_id).status == TicketStatus.NEW
    events = repository.list_events(ticket.ticket_id)
    assert [event.event_type for event in events] == [TicketEventType.CREATED]


@pytest.mark.parametrize(
    ("statement", "error"),
    [
        ("UPDATE ticket_events SET reason = 'Rewritten'", "append-only"),
        ("DELETE FROM ticket_events", "append-only"),
        (
            """
            INSERT OR REPLACE INTO ticket_events (
                event_id, ticket_id, event_type, previous_status, new_status,
                occurred_at, actor, reason
            )
            SELECT event_id, ticket_id, event_type, previous_status, new_status,
                   occurred_at, actor, 'Replaced'
            FROM ticket_events
            """,
            "append-only",
        ),
        (
            """
            INSERT INTO ticket_events (
                ticket_id, event_type, previous_status, new_status, occurred_at
            )
            VALUES ('TASK-001', 'status_changed', 'new', 'investigating', '2026-11-11T18:00:00+00:00')
            """,
            "require an actor and reason",
        ),
    ],
)
def test_database_protects_ticket_event_history(database_path, statement, error):
    repository = SQLiteTicketRepository(database_path)
    ticket = repository.create(build_ticket)
    history = repository.list_events(ticket.ticket_id)

    with (
        pytest.raises(sqlite3.IntegrityError, match=error),
        database.write_transaction(database_path) as connection,
    ):
        connection.execute("PRAGMA recursive_triggers = OFF")
        connection.execute(statement)

    assert repository.list_events(ticket.ticket_id) == history


def test_concurrent_creation_allocates_unique_ordered_ids(database_path):
    repositories = [SQLiteTicketRepository(database_path) for _ in range(16)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        tickets = list(
            executor.map(
                lambda repository: repository.create(build_ticket), repositories
            )
        )

    repository = repositories[0]
    expected_ids = [f"TASK-{number:03d}" for number in range(1, 17)]
    assert {ticket.ticket_id for ticket in tickets} == set(expected_ids)
    assert [ticket.ticket_id for ticket in repository.list_all()] == expected_ids
    for ticket_id in expected_ids:
        assert [event.event_type for event in repository.list_events(ticket_id)] == [
            TicketEventType.CREATED
        ]


def test_concurrent_duplicate_transition_appends_one_event(database_path):
    first = SQLiteTicketRepository(database_path)
    second = SQLiteTicketRepository(database_path)
    ticket = first.create(build_ticket)

    def attempt_transition(repository):
        try:
            return repository.change_status(
                ticket.ticket_id, TicketStatus.INVESTIGATING
            ).status
        except InvalidStatusTransitionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt_transition, [first, second]))

    assert results.count(TicketStatus.INVESTIGATING) == 1
    assert results.count(None) == 1
    assert [event.new_status for event in first.list_events(ticket.ticket_id)] == [
        TicketStatus.NEW,
        TicketStatus.INVESTIGATING,
    ]
