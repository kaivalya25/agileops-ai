from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from agileops.main import create_app

TICKET_DATA = {
    "title": "Fix dashboard refresh",
    "description": "Repair the broken sales dashboard refresh.",
    "ticket_type": "incident",
    "priority": "high",
    "business_impact": "Executive reporting unavailable.",
    "created_by": "Finance Executive",
}


def test_day_four_ticket_api(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/tickets").json() == []
    assert client.get("/tickets/TASK-999").status_code == 404
    assert (
        client.post("/tickets", json={**TICKET_DATA, "priority": "banana"}).status_code
        == 422
    )
    assert (
        client.post("/tickets", json={**TICKET_DATA, "title": "short"}).status_code
        == 422
    )

    response = client.post(
        "/tickets", json={**TICKET_DATA, "status": "done", "ticket_id": "custom"}
    )
    assert response.status_code == 201
    ticket = {
        **TICKET_DATA,
        "ticket_id": "TASK-001",
        "ticket_type": "INCIDENT",
        "priority": "HIGH",
        "status": "NEW",
        "assigned_to": None,
    }
    assert response.json() == ticket
    assert client.get("/tickets/TASK-001").json() == ticket
    assert client.get("/tickets").json() == [ticket]


def test_status_workflow_and_ordered_history(client):
    client.post("/tickets", json=TICKET_DATA)
    client.post("/tickets", json=TICKET_DATA)
    status_url = "/tickets/TASK-001/status"
    events_url = "/tickets/TASK-001/events"

    assert (
        client.patch(
            "/tickets/TASK-999/status", json={"status": "investigating"}
        ).status_code
        == 404
    )
    assert client.get("/tickets/TASK-999/events").status_code == 404
    assert client.patch(status_url, json={"status": "unknown"}).status_code == 422
    assert (
        client.patch(
            status_url, json={"status": "investigating", "actor": " "}
        ).status_code
        == 422
    )
    assert client.patch(status_url, json={"status": "done"}).status_code == 409

    workflow = [
        "new",
        "investigating",
        "ready_for_dev",
        "in_progress",
        "qa",
        "in_progress",
        "qa",
        "done",
    ]
    for next_status in workflow[1:]:
        response = client.patch(status_url, json={"status": next_status})
        assert response.status_code == 200
        assert response.json()["status"] == next_status.upper()

    assert client.patch(status_url, json={"status": "in_progress"}).status_code == 409
    assert client.get("/tickets/TASK-001").json()["status"] == "DONE"
    events = client.get(events_url).json()
    assert [event["event_type"] for event in events] == ["created"] + [
        "status_changed"
    ] * 7
    assert [event["previous_status"] for event in events] == [None] + [
        status.upper() for status in workflow[:-1]
    ]
    assert [event["new_status"] for event in events] == [
        status.upper() for status in workflow
    ]
    assert (events[0]["actor"], events[0]["reason"]) == (
        TICKET_DATA["created_by"],
        "Ticket created",
    )
    assert {(event["actor"], event["reason"]) for event in events[1:]} == {
        ("unspecified", "No reason provided")
    }
    assert [event["event_id"] for event in events] == [1, 3, 4, 5, 6, 7, 8, 9]
    assert {event["ticket_id"] for event in events} == {"TASK-001"}
    assert all(
        datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")).utcoffset()
        == timedelta(0)
        for event in events
    )
    assert [
        event["event_type"] for event in client.get("/tickets/TASK-002/events").json()
    ] == ["created"]


def test_ticket_and_history_survive_app_restart(tmp_path, monkeypatch):
    path = tmp_path / "configured.db"
    monkeypatch.setenv("AGILEOPS_DB_PATH", str(path))
    with TestClient(create_app()) as client:
        response = client.post(
            "/tickets", json={**TICKET_DATA, "assigned_to": "Operations"}
        )
        assert response.status_code == 201
        ticket_url = "/tickets/TASK-001"
        response = client.patch(
            f"{ticket_url}/status",
            json={
                "status": "investigating",
                "actor": "On-call engineer",
                "reason": "Confirmed the dashboard failure.",
            },
        )
        assert response.status_code == 200
        ticket = response.json()
        history = client.get(f"{ticket_url}/events").json()
        assert ticket["assigned_to"] == "Operations"
        assert ticket["status"] == "INVESTIGATING"
        assert len(history) == 2
        assert history[1]["actor"] == "On-call engineer"
        assert history[1]["reason"] == "Confirmed the dashboard failure."

    with TestClient(create_app()) as client:
        assert client.get(ticket_url).json() == ticket
        assert client.get(f"{ticket_url}/events").json() == history
        assert (
            client.post("/tickets", json=TICKET_DATA).json()["ticket_id"] == "TASK-002"
        )
        assert [ticket["ticket_id"] for ticket in client.get("/tickets").json()] == [
            "TASK-001",
            "TASK-002",
        ]
