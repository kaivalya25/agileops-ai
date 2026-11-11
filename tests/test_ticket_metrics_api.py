from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agileops.main import create_app
from agileops.repositories import sqlite_ticket_repository

TICKET_DATA = {
    "title": "Repair dashboard refresh",
    "description": "Investigate the broken dashboard refresh.",
    "ticket_type": "bug",
    "priority": "high",
    "business_impact": "Executive reporting is unavailable.",
    "created_by": "Operations",
}

WORKFLOW = ("investigating", "ready_for_dev", "in_progress", "qa")
THROUGHPUT_URL = "/tickets/metrics/throughput"


def create_ticket(client):
    response = client.post("/tickets", json=TICKET_DATA)
    assert response.status_code == 201
    return response.json()["ticket_id"]


def transition_ticket(client, ticket_id, statuses):
    for status in statuses:
        response = client.patch(f"/tickets/{ticket_id}/status", json={"status": status})
        assert response.status_code == 200


@pytest.fixture
def set_event_times(monkeypatch):
    def configure(timestamps):
        event_times = iter(timestamps)

        class EventClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return next(event_times).astimezone(tz)

        monkeypatch.setattr(sqlite_ticket_repository, "datetime", EventClock)

    return configure


def test_ticket_metrics_include_rework_and_completed_qa_visits(
    tmp_path, set_event_times
):
    path = tmp_path / "tickets.db"
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    set_event_times(
        start + timedelta(seconds=offset) for offset in (0, 2, 4, 8, 13, 17, 21, 30)
    )
    with TestClient(create_app(path)) as client:
        ticket_id = create_ticket(client)
        url = f"/tickets/{ticket_id}/metrics"
        assert client.get("/tickets/unknown/metrics").status_code == 404
        assert client.get(url).json() == {
            "ticket_id": ticket_id,
            "lead_time_seconds": None,
            "cycle_time_seconds": None,
            "qa_turnaround_seconds": 0.0,
            "qa_return_count": 0,
        }

        transition_ticket(client, ticket_id, (*WORKFLOW, "in_progress", "qa"))
        assert client.get(url).json() == {
            "ticket_id": ticket_id,
            "lead_time_seconds": None,
            "cycle_time_seconds": None,
            "qa_turnaround_seconds": 4.0,
            "qa_return_count": 1,
        }

        transition_ticket(client, ticket_id, ("done",))
        assert client.get(url).json() == {
            "ticket_id": ticket_id,
            "lead_time_seconds": 30.0,
            "cycle_time_seconds": 22.0,
            "qa_turnaround_seconds": 13.0,
            "qa_return_count": 1,
        }


def test_throughput_counts_completions_within_utc_date_boundaries(
    tmp_path, set_event_times
):
    path = tmp_path / "tickets.db"
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    with TestClient(create_app(path)) as client:
        for completed_at in (start - timedelta(microseconds=1), start, end):
            set_event_times(
                completed_at - timedelta(seconds=offset)
                for offset in (5, 4, 3, 2, 1, 0)
            )
            ticket_id = create_ticket(client)
            transition_ticket(client, ticket_id, (*WORKFLOW, "done"))
        set_event_times([start])
        create_ticket(client)

    with TestClient(create_app(path)) as client:
        dates = {"start_date": "2026-11-01", "end_date": "2026-11-02"}
        response = client.get(THROUGHPUT_URL, params=dates)
        assert response.status_code == 200
        assert response.json() == {**dates, "completed_tickets": 1}
        assert (
            client.get(
                THROUGHPUT_URL, params={**dates, "start_date": "2026-11-02"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                THROUGHPUT_URL, params={**dates, "start_date": "invalid"}
            ).status_code
            == 422
        )
