import pytest

from agileops.lab import SCENARIOS, query_logs, read_report, run_refresh


@pytest.mark.parametrize(("scenario", "code"), SCENARIOS.items())
def test_reporting_failure_retains_last_successful_report(tmp_path, scenario, code):
    path = tmp_path / "reporting.db"
    result = run_refresh(path)
    assert result["rows_loaded"] == 3
    report = read_report(path)
    assert report == [
        {"region": "Central", "order_count": 2, "total_cents": 19995},
        {"region": "East", "order_count": 1, "total_cents": 5525},
    ]

    result = run_refresh(path, scenario=scenario, incident_id="INC 26-0001")
    assert result["event"] == code
    assert read_report(path) == report
    logs = query_logs(path, incident_id="INC 26-0001")
    assert [event["event"] for event in logs] == ["REFRESH_STARTED", code]
    assert {event["correlation_id"] for event in logs} == {result["correlation_id"]}
    assert query_logs(path, correlation_id=result["correlation_id"]) == logs
    assert run_refresh(path)["status"] == "completed"
