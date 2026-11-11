import pytest
from fastapi.testclient import TestClient

from agileops import workflow
from agileops.lab import query_logs, read_report
from agileops.main import create_app


@pytest.fixture
def lab_client(database_path, tmp_path, monkeypatch):
    monkeypatch.setenv("AGILEOPS_WORKFLOW_DIR", str(tmp_path / "workflows"))
    monkeypatch.setenv("AGILEOPS_LAB_DB", str(tmp_path / "reporting.db"))
    monkeypatch.setenv("AGILEOPS_KNOWLEDGE_DB", str(tmp_path / "unused.db"))
    monkeypatch.setenv("AGILEOPS_APPROVAL_TOKEN", "integration-token")
    with TestClient(create_app(database_path)) as client:
        yield client


@pytest.mark.parametrize("recovery_failure", [False, True])
def test_lab_intake_runs_approved_patch_before_closing_ticket(
    lab_client, monkeypatch, recovery_failure
):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    client = lab_client
    lab = client.app.state.workflow
    headers = {"X-AgileOps-Approval-Token": "integration-token"}
    payload = {
        "summary": "Regional reporting broke following the column change.",
        "reported_by": "Local operator",
        "business_impact": "Operations cannot reconcile the daily sales report.",
        "affected_system": "Regional dashboard",
        "scenario": "missing_column",
        "priority": "critical",
    }
    assert client.post("/lab/incidents", json=payload).status_code == 403
    assert client.get("/incidents").json() == []
    submission = client.post("/lab/incidents", json=payload, headers=headers)
    assert submission.status_code == 201
    data = submission.json()
    incident_id = data["incident"]["incident_id"]
    assert data["incident"]["summary"] == payload["summary"]
    assert data["failed_refresh"]["event"] == "REPORT_COLUMN_MISSING"
    assert (
        data["workflow"]["investigation"]["diagnosis_code"] == "REPORT_COLUMN_MISSING"
    )
    original_report = read_report(lab.lab_path)
    url = f"/workflows/{data['workflow']['workflow_id']}"

    for gate in ("priority_and_scope", "remediation", "release"):
        assert client.get(url).json()["pending_approval"]["gate"] == gate
        if recovery_failure and gate == "release":
            monkeypatch.setattr(
                workflow,
                "approved_report_query",
                lambda *_: "SELECT unavailable FROM reporting_orders",
            )
        decision = client.post(
            f"{url}/approve",
            json={
                "gate": gate,
                "approved": True,
                "actor": "Local operator",
                "reason": "Reviewed the lab evidence.",
            },
            headers=headers,
        )
        assert decision.status_code == 200
    final = decision.json()
    assert final["qa"]["passed"]
    ticket = client.get(f"/tickets/{final['ticket_id']}").json()
    assert ticket["priority"] == "CRITICAL"
    recovery = final["reporting_recovery"]
    logs = query_logs(lab.lab_path, incident_id=incident_id)
    assert logs[-2]["detail"] == "Starting reporting refresh (approved worktree query)."
    assert logs[-1]["correlation_id"] == recovery["correlation_id"]
    assert read_report(lab.lab_path) == original_report
    if recovery_failure:
        assert final["status"] == "recovery_failed"
        assert ticket["status"] == "QA"
        assert recovery["event"] == "REPORT_QUERY_FAILED"
    else:
        assert final["status"] == "completed"
        assert ticket["status"] == "DONE"
        assert recovery["rows_loaded"] == 3
        assert recovery["report"] == original_report
        assert client.get("/bi/portfolio").json()["throughput"] == 1
