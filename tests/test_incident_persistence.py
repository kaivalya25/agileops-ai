import sqlite3
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import pytest

from agileops.database import migrate
from agileops.domain.enums import TicketPriority
from agileops.domain.models import Incident
from agileops.repositories.sqlite_incident_repository import SQLiteIncidentRepository
from agileops.repositories.sqlite_ticket_repository import SQLiteTicketRepository


def build_incident(incident_id):
    return Incident(
        incident_id=incident_id,
        summary="Sales dashboard refresh failed.",
        reported_by="Operations",
        business_impact="Executive reporting unavailable.",
    )


def test_concurrent_incident_creation_allocates_unique_ids(tmp_path):
    path = tmp_path / "incidents.db"
    migrate(path)

    def create_incident(_):
        return SQLiteIncidentRepository(path).create(build_incident)

    with ThreadPoolExecutor(max_workers=4) as executor:
        incidents = list(executor.map(create_incident, range(8)))

    incident_ids = {incident.incident_id for incident in incidents}
    assert len(incident_ids) == 8
    stored = SQLiteIncidentRepository(path).list_all()
    assert {incident.incident_id for incident in stored} == incident_ids


def test_ticket_repository_rejects_missing_incident_link(tmp_path):
    path = tmp_path / "incidents.db"
    migrate(path)
    tickets = SQLiteTicketRepository(path)
    missing_incident = build_incident("INC 26-9999")

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        tickets.create(
            partial(
                missing_incident.create_ticket_from_incident,
                priority=TicketPriority.HIGH,
            )
        )
    assert tickets.list_all() == []
    assert tickets.list_events("TASK-001") is None

    incident = SQLiteIncidentRepository(path).create(build_incident)
    ticket = tickets.create(
        partial(incident.create_ticket_from_incident, priority=TicketPriority.HIGH)
    )
    assert ticket.ticket_id == "TASK-001"
    assert tickets.list_by_incident(incident.incident_id) == [ticket]
