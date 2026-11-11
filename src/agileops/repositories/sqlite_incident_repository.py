import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from agileops.database import connect, write_transaction
from agileops.domain.models import Incident


def _to_incident(row: sqlite3.Row) -> Incident:
    return Incident(
        incident_id=row["incident_id"],
        summary=row["summary"],
        reported_by=row["reported_by"],
        business_impact=row["business_impact"],
        affected_system=row["affected_system"],
    )


class SQLiteIncidentRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create(self, build_incident: Callable[[str], Incident]) -> Incident:
        with write_transaction(self.database_path) as connection:
            year = datetime.now(timezone.utc).year
            number = connection.execute(
                """
                SELECT COALESCE(MAX(number), 0) + 1
                FROM incidents
                WHERE report_year = ?
                """,
                (year,),
            ).fetchone()[0]
            incident = build_incident(f"INC {year % 100:02d}-{number:04d}")
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, report_year, number, summary,
                    reported_by, business_impact, affected_system
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.incident_id,
                    year,
                    number,
                    incident.summary,
                    incident.reported_by,
                    incident.business_impact,
                    incident.affected_system,
                ),
            )
        return incident

    def get_by_id(self, incident_id: str) -> Incident | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
            return _to_incident(row) if row is not None else None

    def list_all(self) -> list[Incident]:
        with connect(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM incidents ORDER BY report_year, number")
            return [_to_incident(row) for row in rows]
