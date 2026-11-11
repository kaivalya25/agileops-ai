import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path

from agileops.database import connect, write_transaction
from agileops.domain.models import Sprint


def _to_sprint(row: sqlite3.Row) -> Sprint:
    return Sprint(
        sprint_id=row["sprint_id"],
        name=row["name"],
        planned_start_date=date.fromisoformat(row["planned_start_date"]),
        planned_end_date=date.fromisoformat(row["planned_end_date"]),
    )


class SQLiteSprintRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create(self, build_sprint: Callable[[str], Sprint]) -> Sprint:
        with write_transaction(self.database_path) as connection:
            number = connection.execute(
                "SELECT COALESCE(MAX(number), 0) + 1 FROM sprints"
            ).fetchone()[0]
            sprint = build_sprint(f"SPRINT-{number:03d}")
            connection.execute(
                """
                INSERT INTO sprints (number, sprint_id, name, planned_start_date, planned_end_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    number,
                    sprint.sprint_id,
                    sprint.name,
                    sprint.planned_start_date.isoformat(),
                    sprint.planned_end_date.isoformat(),
                ),
            )
        return sprint

    def get_by_id(self, sprint_id: str) -> Sprint | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM sprints WHERE sprint_id = ?", (sprint_id,)
            ).fetchone()
            return _to_sprint(row) if row is not None else None

    def list_all(self) -> list[Sprint]:
        with connect(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM sprints ORDER BY number")
            return [_to_sprint(row) for row in rows]
