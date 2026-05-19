"""Tests for the notification channels API.

Routes:
- GET    /api/v1/notifications/channels
- GET    /api/v1/notifications/channels/{id}
- POST   /api/v1/notifications/channels
- PATCH  /api/v1/notifications/channels/{id}
- DELETE /api/v1/notifications/channels/{id}
- POST   /api/v1/notifications/channels/{id}/test
- GET    /api/v1/notifications/dispatch/{dispatch_id}
- GET    /api/v1/notifications/dispatches
- GET    /api/v1/notifications/services
- POST   /api/v1/notifications/services/{id}/compose-url
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_test_send_cooldown():
    """Clear the per-channel test-send cooldown map between tests.

    The in-memory DB resets per test, so channel IDs collide across
    tests (typically id=1). Without clearing the cooldown dict, the
    first POST in a later test trips the cooldown from a prior test.
    """
    from arm.api.v1 import notifications as notif_routes
    notif_routes._test_send_last.clear()
    yield
    notif_routes._test_send_last.clear()


@pytest.fixture
def client(db_session):
    """FastAPI test client wired against the in-memory DB."""
    from arm.app import app
    return TestClient(app)


def test_create_channel_apprise(client):
    body = {
        "type": "apprise",
        "name": "Family Discord",
        "config": {"type": "apprise", "url": "discord://1/2"},
        "subscribed_events": ["job.started"],
    }
    resp = client.post("/api/v1/notifications/channels", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["type"] == "apprise"
    assert data["enabled"] is True
    assert data["config"]["url"] == "discord://1/2"


def test_create_channel_rejects_bad_apprise_url(client):
    body = {
        "type": "apprise",
        "name": "X",
        "config": {"type": "apprise", "url": "totally-not-a-scheme"},
        "subscribed_events": [],
    }
    resp = client.post("/api/v1/notifications/channels", json=body)
    assert resp.status_code == 422
    assert "apprise" in resp.text.lower() or "url" in resp.text.lower()


def test_get_channel_masks_secret(client, make_channel):
    ch = make_channel(
        type="webhook",
        config={"type": "webhook",
                "url": "https://example.com/hook",
                "shared_secret": "supersecret123"},
        subscribed_events=["job.failed"],
    )
    resp = client.get(f"/api/v1/notifications/channels/{ch.id}")
    assert resp.status_code == 200
    data = resp.json()
    # Secret is masked. The dispatch code path retrieves it via the
    # raw DB column.
    assert data["config"]["shared_secret"] == "<hidden>"


def test_patch_channel_preserves_secret_when_sent_as_hidden(client, make_channel):
    ch = make_channel(
        type="webhook",
        config={"type": "webhook",
                "url": "https://example.com/hook",
                "shared_secret": "supersecret123"},
        subscribed_events=["job.failed"],
    )
    # Client gets the masked literal, modifies name, sends it back.
    body = {"name": "Renamed",
            "config": {"type": "webhook",
                       "url": "https://example.com/hook",
                       "shared_secret": "<hidden>"}}
    resp = client.patch(f"/api/v1/notifications/channels/{ch.id}", json=body)
    assert resp.status_code == 200
    # Verify the actual stored secret didn't change. Expire the test
    # session's identity map so the next query re-reads from the DB
    # rather than returning the cached row from before the API call.
    from arm.notifications.models import NotificationChannel
    from arm.database import db
    db.session.expire_all()
    refreshed = NotificationChannel.query.get(ch.id)
    assert refreshed.config["shared_secret"] == "supersecret123"
    assert refreshed.name == "Renamed"


def test_delete_channel_cascades_outbox(client, make_channel, db_session):
    from arm.notifications.models import NotificationOutbox
    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    db_session.add(NotificationOutbox(
        channel_id=ch.id, event_key="job.started",
        event_payload={"event_key": "job.started", "job_id": 1},
    ))
    db_session.commit()
    resp = client.delete(f"/api/v1/notifications/channels/{ch.id}")
    assert resp.status_code == 204
    assert NotificationOutbox.query.filter_by(channel_id=ch.id).count() == 0


def test_test_send_enqueues_synthetic_event(client, make_channel):
    from arm.notifications.models import NotificationOutbox
    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    resp = client.post(f"/api/v1/notifications/channels/{ch.id}/test", json={})
    assert resp.status_code == 202
    data = resp.json()
    assert "dispatch_id" in data
    assert NotificationOutbox.query.filter_by(
        channel_id=ch.id, event_key="job.started").count() == 1


def test_test_send_cooldown(client, make_channel):
    """Per-channel 10s cooldown rejects rapid test-sends with 429."""
    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    resp1 = client.post(f"/api/v1/notifications/channels/{ch.id}/test", json={})
    assert resp1.status_code == 202
    resp2 = client.post(f"/api/v1/notifications/channels/{ch.id}/test", json={})
    assert resp2.status_code == 429
    assert "Retry-After" in resp2.headers


def test_dispatch_status_endpoint(client, make_channel, db_session):
    from arm.notifications.models import NotificationOutbox
    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    row = NotificationOutbox(
        channel_id=ch.id, event_key="job.started",
        event_payload={"event_key": "job.started", "job_id": 1},
        status="success",
    )
    db_session.add(row)
    db_session.commit()
    resp = client.get(f"/api/v1/notifications/dispatch/{row.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"


def test_list_dispatches_filters(client, make_channel, db_session):
    from arm.notifications.models import NotificationOutbox
    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    db_session.add_all([
        NotificationOutbox(channel_id=ch.id, event_key="job.started",
                           event_payload={}, status="success"),
        NotificationOutbox(channel_id=ch.id, event_key="job.failed",
                           event_payload={}, status="failed"),
    ])
    db_session.commit()
    resp = client.get(
        f"/api/v1/notifications/dispatches?channel_id={ch.id}&status=success"
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["event_key"] == "job.started"


def test_catalog_endpoint(client):
    resp = client.get("/api/v1/notifications/services")
    assert resp.status_code == 200
    data = resp.json()
    assert "featured" in data
    assert "services" in data
    assert "discord" in data["featured"]


def test_compose_url_endpoint(client):
    body = {
        "required": {"webhook_id": "1234", "webhook_token": "abcd"},
        "advanced": {"tts": True},
    }
    resp = client.post(
        "/api/v1/notifications/services/discord/compose-url",
        json=body,
    )
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("discord://1234/abcd")
