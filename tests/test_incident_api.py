import re
from urllib.parse import quote

from fastapi.testclient import TestClient

from agileops import database
from agileops.main import create_app


INCIDENT_DATA = {
    "summary": "Sales dashboard refresh failed.",
    "reported_by": "Operations",
    "business_impact": "Executive reporting unavailable.",
}


def test_create_list_and_retrieve_incidents(tmp_path):
    with TestClient(create_app(tmp_path / "incidents.db")) as client:
        assert client.get("/incidents").json() == []
        assert client.get("/incidents/unknown").status_code == 404
        assert client.post("/incidents", json={**INCIDENT_DATA, "summary": "short"}).status_code == 422

        response = client.post("/incidents", json={**INCIDENT_DATA, "incident_id": "custom"})
        assert response.status_code == 201
        incident = response.json()
        incident_id = incident["incident_id"]
        assert re.fullmatch(r"INC \d{2}-0001", incident_id)
        assert incident == {**INCIDENT_DATA, "incident_id": incident_id, "affected_system": None}
        assert client.get(f"/incidents/{quote(incident_id)}").json() == incident

        second = client.post("/incidents", json={**INCIDENT_DATA, "affected_system": "Reporting"})
        assert second.status_code == 201
        assert second.json()["affected_system"] == "Reporting"
        assert client.get("/incidents").json() == [incident, second.json()]


def test_incident_tickets_keep_the_ticket_contract_and_history(tmp_path):
    path = tmp_path / "incidents.db"
    with TestClient(create_app(path)) as client:
        incident = client.post("/incidents", json=INCIDENT_DATA).json()
        other = client.post("/incidents", json=INCIDENT_DATA).json()
        url = f"/incidents/{quote(incident['incident_id'])}/tickets"
        other_url = f"/incidents/{quote(other['incident_id'])}/tickets"
        assert client.get(url).json() == []
        assert client.get("/incidents/unknown/tickets").status_code == 404
        assert client.post("/incidents/unknown/tickets", json={"priority": "high"}).status_code == 404
        assert client.post(url, json={"priority": "urgent"}).status_code == 422

        response = client.post(url, json={"priority": "high"})
        assert response.status_code == 201
        ticket = response.json()
        assert ticket == {
            "ticket_id": "TASK-001",
            "title": f"{incident['incident_id']}: {INCIDENT_DATA['summary']}",
            "description": INCIDENT_DATA["summary"],
            "ticket_type": "INCIDENT",
            "priority": "HIGH",
            "business_impact": INCIDENT_DATA["business_impact"],
            "created_by": INCIDENT_DATA["reported_by"],
            "assigned_to": None,
            "status": "NEW",
        }
        assert client.get("/tickets/TASK-001").json() == ticket
        assert client.get("/tickets").json() == [ticket]
        assert client.get(url).json() == [ticket]
        assert client.get(other_url).json() == []

        transition = client.patch("/tickets/TASK-001/status", json={"status": "investigating"})
        assert transition.status_code == 200
        second = client.post(url, json={"priority": "medium"})
        assert second.status_code == 201
        assert second.json()["ticket_id"] == "TASK-002"
        assert client.get(url).json() == [transition.json(), second.json()]

    with TestClient(create_app(path)) as client:
        assert client.get(f"/incidents/{quote(incident['incident_id'])}").json() == incident
        assert client.get(url).json() == [transition.json(), second.json()]
        history = client.get("/tickets/TASK-001/events").json()
        assert [event["event_type"] for event in history] == ["created", "status_changed"]
        assert [event["new_status"] for event in history] == ["NEW", "INVESTIGATING"]
        assert [(event["actor"], event["reason"]) for event in history] == [
            (INCIDENT_DATA["reported_by"], "Ticket created"),
            ("unspecified", "No reason provided"),
        ]


def test_upgrade_day_five_database_preserves_tickets_and_history(tmp_path, monkeypatch):
    path = tmp_path / "day-five.db"
    with monkeypatch.context() as before_upgrade:
        before_upgrade.setattr(database, "MIGRATIONS", database.MIGRATIONS[:1])
        database.migrate(path)

    with database.write_transaction(path) as connection:
        connection.execute("""
            INSERT INTO tickets (
                number, ticket_id, title, description, ticket_type, priority,
                business_impact, created_by, status
            )
            VALUES (
                1, 'TASK-001', 'Fix dashboard', 'Restore dashboard refresh.', 'bug', 'high',
                'Reporting unavailable.', 'Operations', 'investigating'
            )
        """)
        connection.execute("""
            INSERT INTO ticket_events (
                ticket_id, event_type, previous_status, new_status, occurred_at
            )
            VALUES
                ('TASK-001', 'created', NULL, 'new', '2026-01-01T10:00:00+00:00'),
                ('TASK-001', 'status_changed', 'new', 'investigating', '2026-01-01T10:05:00+00:00')
        """)
        connection.execute("UPDATE ticket_number_sequence SET next_number = 2")

    with TestClient(create_app(path)) as client:
        existing = client.get("/tickets/TASK-001")
        assert existing.status_code == 200
        assert existing.json()["status"] == "INVESTIGATING"
        history = client.get("/tickets/TASK-001/events").json()
        assert [event["event_id"] for event in history] == [1, 2]
        assert [event["new_status"] for event in history] == ["NEW", "INVESTIGATING"]
        assert [(event["actor"], event["reason"]) for event in history] == [(None, None), (None, None)]

        incident_id = client.post("/incidents", json=INCIDENT_DATA).json()["incident_id"]
        url = f"/incidents/{quote(incident_id)}/tickets"
        response = client.post(url, json={"priority": "high"})
        assert response.status_code == 201
        assert response.json()["ticket_id"] == "TASK-002"
        assert client.get(url).json() == [response.json()]

    with database.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == len(database.MIGRATIONS)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        rows = connection.execute("SELECT incident_id FROM tickets ORDER BY number")
        assert [row["incident_id"] for row in rows] == [None, incident_id]
