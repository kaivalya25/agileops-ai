import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from agileops.database import connect
from agileops.domain.enums import TicketStatus
from agileops.main import create_app
from agileops.repositories.sqlite_sprint_repository import SQLiteSprintRepository
from agileops.repositories.sqlite_ticket_repository import SQLiteTicketRepository
from agileops.schemas.sprints import SprintCreate
from agileops.schemas.tickets import TicketCreate

SPRINT_DATA = {
    "name": "Reporting reliability",
    "planned_start_date": "2026-11-16",
    "planned_end_date": "2026-11-27",
}

TICKET_DATA = {
    "title": "Repair dashboard refresh",
    "description": "Investigate and restore the dashboard refresh.",
    "ticket_type": "bug",
    "priority": "high",
    "business_impact": "Executive reporting is unavailable.",
    "created_by": "Operations",
}


def test_sprint_api_validates_dates_and_lists_persisted_sprints(client):
    assert client.get("/sprints").json() == []
    assert client.get("/sprints/missing").status_code == 404
    assert client.get("/sprints/missing/tickets").status_code == 404

    invalid = client.post(
        "/sprints", json={**SPRINT_DATA, "planned_end_date": "2026-11-15"}
    )
    assert invalid.status_code == 422
    created = client.post("/sprints", json=SPRINT_DATA)
    assert created.status_code == 201
    sprint = {"sprint_id": "SPRINT-001", **SPRINT_DATA}
    assert created.json() == sprint
    assert client.get("/sprints").json() == [sprint]
    assert client.get("/sprints/SPRINT-001").json() == sprint
    assert client.get("/sprints/SPRINT-001/tickets").json() == []


def test_membership_backlog_and_assignee_survive_restart(database_path):
    with TestClient(create_app(database_path)) as client:
        first = client.post("/sprints", json=SPRINT_DATA).json()
        second = client.post(
            "/sprints", json={**SPRINT_DATA, "name": "Follow-up"}
        ).json()
        created = client.post("/tickets", json=TICKET_DATA)
        assert created.status_code == 201
        ticket = created.json()
        ticket_url = f"/tickets/{ticket['ticket_id']}"
        membership_url = f"{ticket_url}/sprint"
        first_sprint = first["sprint_id"]
        second_sprint = second["sprint_id"]

        assert client.get("/tickets/backlog").json() == [ticket]
        assert (
            client.patch(membership_url, json={"sprint_id": first_sprint}).status_code
            == 200
        )
        assert client.get("/tickets/backlog").json() == []
        assert client.get(f"/sprints/{first_sprint}/tickets").json() == [ticket]
        assert (
            client.patch(membership_url, json={"sprint_id": "missing"}).status_code
            == 404
        )
        assert client.get(membership_url).json()["sprint_id"] == first_sprint
        assert (
            client.patch(membership_url, json={"sprint_id": second_sprint}).status_code
            == 200
        )
        assert client.get(f"/sprints/{first_sprint}/tickets").json() == []

        assigned = client.patch(
            f"{ticket_url}/assignment", json={"assigned_to": "On-call engineer"}
        )
        assert assigned.status_code == 200
        assert assigned.json() == {**ticket, "assigned_to": "On-call engineer"}

    with TestClient(create_app(database_path)) as client:
        assert client.get(f"/sprints/{second_sprint}").json() == second
        assert client.get(membership_url).json() == {
            "ticket_id": ticket["ticket_id"],
            "sprint_id": second_sprint,
        }
        assert client.get(f"/sprints/{second_sprint}/tickets").json() == [
            assigned.json()
        ]
        assert client.patch(membership_url, json={"sprint_id": None}).status_code == 200
        assert client.get(f"/sprints/{second_sprint}/tickets").json() == []
        assert client.get("/tickets/backlog").json() == [assigned.json()]
        assert (
            client.patch(f"{ticket_url}/assignment", json={"assigned_to": None}).json()
            == ticket
        )


def test_repository_savepoints_and_transaction_cleanup(
    database_path, repository_transaction
):
    sprints = SQLiteSprintRepository(database_path)
    tickets = SQLiteTicketRepository(database_path)
    ticket_data = TicketCreate.model_validate(TICKET_DATA)

    with repository_transaction:
        sprint = sprints.create(SprintCreate.model_validate(SPRINT_DATA).to_domain)
        assert sprints.get_by_id(sprint.sprint_id) == sprint
        with pytest.raises(
            sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"
        ):
            tickets.create(
                lambda ticket_id: replace(
                    ticket_data.to_domain(ticket_id), sprint_id="missing"
                )
            )

        ticket = tickets.create(ticket_data.to_domain)
        assert ticket.ticket_id == "TASK-001"
        assert tickets.list_backlog() == [ticket]
        scheduled = tickets.set_sprint(ticket.ticket_id, sprint.sprint_id)
        assert tickets.list_by_sprint(sprint.sprint_id) == [scheduled]
        assigned = tickets.set_assignee(ticket.ticket_id, "Operations")
        assert tickets.get_by_id(ticket.ticket_id) == assigned
        assert assigned.sprint_id == sprint.sprint_id
        assert tickets.list_backlog() == []

        tickets.set_sprint(ticket.ticket_id, None)
        for next_status in (
            TicketStatus.INVESTIGATING,
            TicketStatus.READY_FOR_DEV,
            TicketStatus.IN_PROGRESS,
            TicketStatus.QA,
            TicketStatus.DONE,
        ):
            tickets.change_status(ticket.ticket_id, next_status)
        assert tickets.list_backlog() == []
        assert len(tickets.list_events(ticket.ticket_id)) == 6

    assert sprints.list_all() == []
    assert tickets.list_all() == []
    with connect(database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM ticket_events").fetchone()[0] == 0
        )
        assert (
            connection.execute(
                "SELECT next_number FROM ticket_number_sequence WHERE singleton = 1"
            ).fetchone()[0]
            == 1
        )
