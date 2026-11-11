from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from agileops import database
from agileops.main import create_app
from agileops.repositories import (
    sqlite_incident_repository,
    sqlite_sprint_repository,
    sqlite_ticket_repository,
)


@pytest.fixture
def database_path(tmp_path):
    path = tmp_path / "agileops.db"
    database.migrate(path)
    return path


@pytest.fixture
def client(database_path):
    with TestClient(create_app(database_path)) as client:
        yield client


@pytest.fixture
def repository_transaction(database_path, monkeypatch):
    """Run synchronous repository tests on one connection and roll back their writes."""

    @contextmanager
    def transaction_scope():
        with (
            database.connect(database_path) as connection,
            monkeypatch.context() as patch,
        ):
            connection.execute("BEGIN IMMEDIATE")

            @contextmanager
            def test_connection(path):
                assert path == database_path
                yield connection

            @contextmanager
            def test_write(path):
                with test_connection(path) as connection:
                    connection.execute("SAVEPOINT repository_write")
                    try:
                        yield connection
                    except BaseException:
                        connection.execute("ROLLBACK TO SAVEPOINT repository_write")
                        raise
                    finally:
                        connection.execute("RELEASE SAVEPOINT repository_write")

            for module in (
                sqlite_incident_repository,
                sqlite_sprint_repository,
                sqlite_ticket_repository,
            ):
                patch.setattr(module, "connect", test_connection)
                patch.setattr(module, "write_transaction", test_write)

            try:
                yield
            finally:
                connection.rollback()

    return transaction_scope()
