"""Tests for SessionCleanupMiddleware.

Verifies that the middleware rolls back poisoned SQLAlchemy sessions
so that subsequent requests on the same thread don't fail with
PendingRollbackError.
"""
import unittest.mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import PendingRollbackError


def _make_app():
    """Create a minimal FastAPI app with the session cleanup middleware.

    Uses dedicated test endpoints so we don't depend on the full ARM
    router registration or endpoint function names.
    """
    from arm.app import SessionCleanupMiddleware
    from arm.database import db

    app = FastAPI()
    app.add_middleware(SessionCleanupMiddleware)

    @app.get("/test/ok")
    def ok_endpoint():
        """Simple endpoint that succeeds."""
        return {"status": "ok"}

    @app.get("/test/db-read")
    def db_read_endpoint():
        """Endpoint that reads from the DB."""
        result = db.session.execute(db.text("SELECT 1")).scalar()
        return {"result": result}

    @app.get("/test/poison")
    def poison_endpoint():
        """Endpoint that poisons the session with a bad query."""
        db.session.execute(db.text("INSERT INTO nonexistent_table VALUES (1)"))

    @app.get("/test/pending-rollback")
    def pending_rollback_endpoint():
        """Endpoint that raises PendingRollbackError."""
        raise PendingRollbackError(
            "This Session's transaction has been rolled back",
            None, None, False
        )

    return app


@pytest.fixture
def test_client(app_context):
    """Create a TestClient with the minimal test app."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestSessionCleanupMiddleware:
    """Verify middleware clears poisoned sessions after failed requests."""

    def test_successful_request_unaffected(self, test_client):
        """Normal requests should work and return valid responses."""
        resp = test_client.get("/test/ok")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_consecutive_successful_requests(self, test_client):
        """Multiple successful requests should all work."""
        for _ in range(5):
            resp = test_client.get("/test/ok")
            assert resp.status_code == 200

    def test_db_read_works(self, test_client):
        """Endpoint that reads from DB should succeed."""
        resp = test_client.get("/test/db-read")
        assert resp.status_code == 200
        assert resp.json() == {"result": 1}

    def test_session_recovers_after_pending_rollback(self, test_client):
        """After PendingRollbackError, the next request should succeed.

        This is the core test: simulates the exact scenario where a
        DB-locked flush poisons the session, and verifies the middleware's
        rollback clears it so subsequent requests work.
        """
        # First request: triggers PendingRollbackError
        resp = test_client.get("/test/pending-rollback")
        assert resp.status_code == 500

        # Second request: must succeed — middleware should have rolled back
        resp = test_client.get("/test/db-read")
        assert resp.status_code == 200
        assert resp.json() == {"result": 1}

    def test_session_recovers_after_bad_sql(self, test_client):
        """After a bad SQL query poisons the session, next request works."""
        # First request: bad SQL causes OperationalError
        resp = test_client.get("/test/poison")
        assert resp.status_code == 500

        # Second request: should succeed
        resp = test_client.get("/test/db-read")
        assert resp.status_code == 200
        assert resp.json() == {"result": 1}

    def test_multiple_failures_then_recovery(self, test_client):
        """Multiple consecutive failures should not compound — recovery still works."""
        for _ in range(3):
            resp = test_client.get("/test/pending-rollback")
            assert resp.status_code == 500

        # Should still recover
        resp = test_client.get("/test/db-read")
        assert resp.status_code == 200
        assert resp.json() == {"result": 1}

    def test_interleaved_success_and_failure(self, test_client):
        """Alternating success and failure should all work correctly."""
        for i in range(5):
            if i % 2 == 0:
                resp = test_client.get("/test/db-read")
                assert resp.status_code == 200
            else:
                resp = test_client.get("/test/poison")
                assert resp.status_code == 500

        # Final request should succeed
        resp = test_client.get("/test/db-read")
        assert resp.status_code == 200

    def test_rollback_called_on_every_request(self, app_context):
        """Verify rollback() is called after every request, not just errors."""
        from arm.database import db

        app = _make_app()
        with unittest.mock.patch.object(db.session, "rollback") as mock_rb, \
             unittest.mock.patch.object(db.session, "remove") as mock_rm:
            with TestClient(app, raise_server_exceptions=False) as c:
                c.get("/test/ok")

            assert mock_rb.called, "rollback() should be called after every request"
            assert mock_rm.called, "remove() should be called after every request"

    def test_rollback_exception_does_not_prevent_remove(self, app_context):
        """If rollback() itself raises, remove() should still be called."""
        from arm.database import db

        app = _make_app()
        with unittest.mock.patch.object(
            db.session, "rollback", side_effect=Exception("rollback failed")
        ), unittest.mock.patch.object(db.session, "remove") as mock_rm:
            with TestClient(app, raise_server_exceptions=False) as c:
                c.get("/test/ok")

            assert mock_rm.called, "remove() must be called even if rollback() fails"
