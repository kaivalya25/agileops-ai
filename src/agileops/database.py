import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

# Each entry is one schema version. Append new migrations in application order.
MIGRATIONS = (
    (
        """
        CREATE TABLE ticket_number_sequence (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            next_number INTEGER NOT NULL CHECK (next_number > 0)
        )
        """,
        "INSERT INTO ticket_number_sequence (singleton, next_number) VALUES (1, 1)",
        """
        CREATE TABLE tickets (
            number INTEGER PRIMARY KEY,
            ticket_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            ticket_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            business_impact TEXT NOT NULL,
            created_by TEXT NOT NULL,
            assigned_to TEXT,
            status TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE ticket_events (
            event_id INTEGER PRIMARY KEY,
            ticket_id TEXT NOT NULL REFERENCES tickets (ticket_id),
            event_type TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            CHECK (
                (event_type = 'created' AND previous_status IS NULL AND new_status = 'new')
                OR
                (event_type = 'status_changed' AND previous_status IS NOT NULL
                 AND previous_status <> new_status)
            )
        )
        """,
        "CREATE INDEX ticket_events_by_ticket ON ticket_events (ticket_id, event_id)",
    ),
    (
        """
        CREATE TABLE incidents (
            incident_id TEXT NOT NULL PRIMARY KEY,
            report_year INTEGER NOT NULL,
            number INTEGER NOT NULL,
            summary TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            business_impact TEXT NOT NULL,
            affected_system TEXT,
            UNIQUE (report_year, number)
        )
        """,
        "ALTER TABLE tickets ADD COLUMN incident_id TEXT REFERENCES incidents (incident_id)",
        "CREATE INDEX tickets_by_incident ON tickets (incident_id, number)",
    ),
    (
        """
        CREATE INDEX ticket_completions_by_time ON ticket_events (occurred_at)
        WHERE event_type = 'status_changed' AND new_status = 'done'
        """,
    ),
    (
        "ALTER TABLE ticket_events ADD COLUMN actor TEXT",
        "ALTER TABLE ticket_events ADD COLUMN reason TEXT",
        # REPLACE can skip delete triggers when recursive triggers are disabled.
        """
        CREATE TRIGGER ticket_events_guard_insert
        BEFORE INSERT ON ticket_events
        BEGIN
            SELECT RAISE(ABORT, 'ticket_events is append-only')
            WHERE EXISTS (SELECT 1 FROM ticket_events WHERE event_id = NEW.event_id);

            SELECT RAISE(ABORT, 'ticket events require an actor and reason')
            WHERE NEW.actor IS NULL OR length(trim(NEW.actor)) = 0
               OR NEW.reason IS NULL OR length(trim(NEW.reason)) = 0;
        END
        """,
        """
        CREATE TRIGGER ticket_events_prevent_update
        BEFORE UPDATE ON ticket_events
        BEGIN
            SELECT RAISE(ABORT, 'ticket_events is append-only');
        END
        """,
        """
        CREATE TRIGGER ticket_events_prevent_delete
        BEFORE DELETE ON ticket_events
        BEGIN
            SELECT RAISE(ABORT, 'ticket_events is append-only');
        END
        """,
    ),
    (
        """
        CREATE TABLE sprints (
            number INTEGER PRIMARY KEY,
            sprint_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            planned_start_date TEXT NOT NULL,
            planned_end_date TEXT NOT NULL,
            CHECK (planned_start_date <= planned_end_date)
        )
        """,
        "ALTER TABLE tickets ADD COLUMN sprint_id TEXT REFERENCES sprints (sprint_id)",
        "CREATE INDEX tickets_by_sprint ON tickets (sprint_id, number)",
    ),
    (
        """
        CREATE TABLE ticket_block_events (
            event_id INTEGER PRIMARY KEY,
            ticket_id TEXT NOT NULL REFERENCES tickets (ticket_id),
            blocked INTEGER NOT NULL CHECK (blocked IN (0, 1)),
            actor TEXT NOT NULL, reason TEXT NOT NULL, occurred_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX ticket_blocks_by_ticket ON ticket_block_events (ticket_id, event_id)",
        """
        CREATE VIEW bi_tickets AS
        SELECT ticket_id, ticket_type, priority, status, sprint_id, assigned_to, incident_id
        FROM tickets
        """,
        """
        CREATE VIEW bi_sprints AS
        SELECT sprint_id, name, planned_start_date, planned_end_date FROM sprints
        """,
        """
        CREATE VIEW bi_events AS
        SELECT ticket_id, event_type, previous_status, new_status, occurred_at FROM ticket_events
        """,
    ),
)


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(database_path, timeout=10.0)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection


@contextmanager
def write_transaction(database_path: Path) -> Iterator[sqlite3.Connection]:
    with connect(database_path) as connection, connection:
        # Acquire the write lock before reading a ticket or the number sequence.
        connection.execute("BEGIN IMMEDIATE")
        yield connection


def migrate(database_path: Path) -> None:
    with write_transaction(database_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if not 0 <= version <= len(MIGRATIONS):
            raise RuntimeError(f"Unsupported database schema version {version}.")

        for next_version, statements in enumerate(
            MIGRATIONS[version:], start=version + 1
        ):
            for statement in statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {next_version}")
