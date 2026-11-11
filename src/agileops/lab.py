"""A reproducible reporting service and synthetic failure scenarios."""

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from uuid import uuid4

from agileops.database import connect, write_transaction

SOURCE = """order_id,region,amount
SO-1001,Central,120.00
SO-1002,East,55.25
SO-1003,Central,79.95
"""
SCENARIOS = {
    "schema_mismatch": "SOURCE_SCHEMA_MISMATCH",
    "bad_sql": "SQL_SYNTAX_ERROR",
    "invalid_config": "SOURCE_AUTH_FAILED",
    "missing_column": "REPORT_COLUMN_MISSING",
    "duplicate_data": "DUPLICATE_ORDER_ID",
}
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS reporting_orders (
        order_id TEXT PRIMARY KEY, region TEXT NOT NULL, amount_cents INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS reporting_summary (
        region TEXT PRIMARY KEY, order_count INTEGER NOT NULL, total_cents INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS reporting_diagnostics (
        event_id INTEGER PRIMARY KEY, correlation_id TEXT NOT NULL, incident_id TEXT,
        occurred_at TEXT NOT NULL, level TEXT NOT NULL, event TEXT NOT NULL,
        detail TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS reporting_diagnostics_incident
       ON reporting_diagnostics (incident_id, event_id)""",
)


class RefreshError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


def _extract(source: str) -> list[tuple[str, str, int]]:
    reader = csv.DictReader(StringIO(source))
    if reader.fieldnames != ["order_id", "region", "amount"]:
        raise RefreshError(
            "SOURCE_SCHEMA_MISMATCH", "Expected CSV columns order_id, region, amount."
        )

    rows = []
    for line, row in enumerate(reader, start=2):
        try:
            order_id, region = row["order_id"].strip(), row["region"].strip()
            cents = Decimal(row["amount"]) * 100
            if None in row or not order_id or not region or not cents.is_finite():
                raise ValueError
            if cents != cents.to_integral_value() or not -(2**63) <= cents < 2**63:
                raise ValueError
        except (AttributeError, TypeError, ValueError, InvalidOperation):
            raise RefreshError(
                "INVALID_SOURCE_ROW", f"Invalid order on CSV line {line}."
            ) from None
        rows.append((order_id, region, int(cents)))
    return rows


def _refresh(
    connection: sqlite3.Connection, scenario: str, source: str, token: str
) -> int:
    if scenario == "invalid_config" or token != "demo-read-only":
        raise RefreshError(
            "SOURCE_AUTH_FAILED", "The reporting connector rejected its credentials."
        )
    if scenario == "schema_mismatch":
        source = source.replace("order_id,region,amount", "order_id,region,total", 1)
    if scenario == "duplicate_data":
        source = source.rstrip() + "\nSO-1001,Central,120.00\n"
    orders = _extract(source)

    connection.execute("DELETE FROM reporting_orders")
    try:
        connection.executemany("INSERT INTO reporting_orders VALUES (?, ?, ?)", orders)
    except sqlite3.IntegrityError as error:
        raise RefreshError("DUPLICATE_ORDER_ID", str(error)) from error

    summary_sql = "SELECT region, COUNT(*), SUM(amount_cents) FROM reporting_orders GROUP BY region"
    if scenario == "bad_sql":
        summary_sql += " WHERE"
    if scenario == "missing_column":
        summary_sql = summary_sql.replace("amount_cents", "gross_cents")
    try:
        connection.execute("DELETE FROM reporting_summary")
        connection.execute(f"INSERT INTO reporting_summary {summary_sql}")
    except sqlite3.OperationalError as error:
        raise RefreshError(
            SCENARIOS.get(scenario, "REPORT_QUERY_FAILED"), str(error)
        ) from error
    return len(orders)


def run_refresh(
    path: Path,
    *,
    scenario: str = "healthy",
    incident_id: str | None = None,
    source: str = SOURCE,
    token: str = "demo-read-only",
) -> dict:
    if scenario not in {"healthy", *SCENARIOS}:
        raise ValueError(f"Unknown reporting scenario {scenario!r}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    correlation_id = uuid4().hex
    with write_transaction(path) as connection:
        for statement in SCHEMA:
            connection.execute(statement)

        def record(level: str, event: str, detail: str) -> None:
            connection.execute(
                """INSERT INTO reporting_diagnostics
                   (correlation_id, incident_id, occurred_at, level, event, detail)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    correlation_id,
                    incident_id,
                    datetime.now(timezone.utc).isoformat(),
                    level,
                    event,
                    detail,
                ),
            )

        record("INFO", "REFRESH_STARTED", f"Starting reporting refresh ({scenario}).")
        connection.execute("SAVEPOINT refresh")
        try:
            count = _refresh(connection, scenario, source, token)
        except RefreshError as error:
            connection.execute("ROLLBACK TO SAVEPOINT refresh")
            record("ERROR", error.code, str(error))
            result = {"status": "failed", "event": error.code}
        else:
            record("INFO", "REFRESH_COMPLETED", f"Loaded {count} orders.")
            result = {"status": "completed", "rows_loaded": count}
        connection.execute("RELEASE SAVEPOINT refresh")
    return {"correlation_id": correlation_id, **result}


def read_report(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with connect(path) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM reporting_summary ORDER BY region"
            )
        ]


def query_logs(
    path: Path,
    *,
    incident_id: str | None = None,
    correlation_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if not path.is_file():
        return []
    if not 1 <= limit <= 500:
        raise ValueError("Log limit must be between 1 and 500.")
    with connect(path) as connection:
        rows = connection.execute(
            """SELECT * FROM reporting_diagnostics
               WHERE (? IS NULL OR incident_id = ?) AND (? IS NULL OR correlation_id = ?)
               ORDER BY event_id DESC LIMIT ?""",
            (incident_id, incident_id, correlation_id, correlation_id, limit),
        )
        return [dict(row) for row in rows][::-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("tmp/reporting-lab.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--scenario", choices=["healthy", *SCENARIOS], default="healthy")
    run.add_argument("--incident-id")
    run.add_argument("--source", type=Path)
    commands.add_parser("report")
    logs = commands.add_parser("logs")
    logs.add_argument("--incident-id")
    logs.add_argument("--correlation-id")
    args = parser.parse_args()
    if args.command == "run":
        source = args.source.read_text(encoding="utf-8-sig") if args.source else SOURCE
        result = run_refresh(
            args.database,
            scenario=args.scenario,
            incident_id=args.incident_id,
            source=source,
        )
        print(json.dumps(result))
        raise SystemExit(1 if result["status"] == "failed" else 0)
    if args.command == "report":
        print(json.dumps(read_report(args.database), indent=2))
    else:
        for event in query_logs(
            args.database,
            incident_id=args.incident_id,
            correlation_id=args.correlation_id,
        ):
            print(json.dumps(event))


if __name__ == "__main__":
    main()
