"""Tests for the dispatcher's per-row processing logic.

The actual asyncio loop is exercised by the integration test in
Task 12 (the publish→dispatch→success end-to-end). Here we test
``process_one_row`` in isolation so behavior is fully covered without
spinning up the loop.
"""
import datetime
from unittest.mock import patch, MagicMock

import pytest


def _outbox_row(db_session, channel_id, event_payload, status="in_flight"):
    from arm.notifications.models import NotificationOutbox
    row = NotificationOutbox(
        channel_id=channel_id,
        event_key=event_payload["event_key"],
        event_payload=event_payload,
        status=status,
        attempts=0,
        next_attempt_at=datetime.datetime.utcnow(),
    )
    db_session.add(row)
    db_session.commit()
    return row


def _started_payload():
    from uuid import uuid4
    return {
        "event_key": "job.started",
        "event_id": str(uuid4()),
        "occurred_at": datetime.datetime.utcnow().isoformat(),
        "job_id": 1,
        "job_title": "X",
        "job_disc_type": "dvd",
        "job_imdb_id": None,
        "drive_mount": "/dev/sr0",
    }


def test_dispatcher_apprise_success_marks_row_success(db_session, make_channel):
    from arm.notifications.dispatcher import process_one_row
    from arm.notifications.models import NotificationOutbox

    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    row = _outbox_row(db_session, ch.id, _started_payload())

    with patch("arm.notifications.dispatcher.send_apprise",
               return_value=(True, None)) as send:
        process_one_row(row.id)

    db_session.refresh(row)
    assert row.status == "success"
    send.assert_called_once()


def test_dispatcher_apprise_transient_failure_reschedules(
    db_session, make_channel
):
    from arm.notifications.dispatcher import process_one_row
    from arm.notifications.models import NotificationOutbox

    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    row = _outbox_row(db_session, ch.id, _started_payload())

    with patch("arm.notifications.dispatcher.send_apprise",
               return_value=(False, "apprise.notify() returned False")):
        process_one_row(row.id)

    db_session.refresh(row)
    assert row.status == "pending"  # retried
    assert row.attempts == 1


def test_dispatcher_webhook_4xx_is_terminal(db_session, make_channel):
    from arm.notifications.dispatcher import process_one_row
    from arm.notifications.models import NotificationOutbox

    ch = make_channel(
        type="webhook",
        config={"type": "webhook",
                "url": "https://example.com/hook"},
        subscribed_events=["job.started"],
    )
    row = _outbox_row(db_session, ch.id, _started_payload())

    with patch("arm.notifications.dispatcher.send_webhook",
               return_value=(False, "HTTP 400: bad request terminal=true")):
        process_one_row(row.id)

    db_session.refresh(row)
    assert row.status == "failed"


def test_dispatcher_bash_runs_with_correct_env(db_session, make_channel):
    from arm.notifications.dispatcher import process_one_row

    ch = make_channel(
        type="bash",
        config={"type": "bash", "script_path": "/x"},
        subscribed_events=["job.started"],
    )
    row = _outbox_row(db_session, ch.id, _started_payload())

    with patch("arm.notifications.dispatcher.send_bash",
               return_value=(True, None)) as send:
        process_one_row(row.id)

    send.assert_called_once()
    kwargs = send.call_args.kwargs
    assert kwargs["script_path"] == "/x"
    env = kwargs["env_vars"]
    assert env["ARM_EVENT_KEY"] == "job.started"
    assert env["ARM_JOB_ID"] == "1"
    assert "ARM_TITLE" in env


def test_dispatcher_template_render_failure_is_terminal(
    db_session, make_channel
):
    """If the template references a missing variable, fail terminal."""
    from arm.notifications.dispatcher import process_one_row

    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
        templates={"job.started": {
            "title": "{nonexistent_field}", "body": "x"}},
    )
    row = _outbox_row(db_session, ch.id, _started_payload())

    process_one_row(row.id)
    db_session.refresh(row)
    assert row.status == "failed"
    assert "template" in row.last_error.lower()


def test_dispatcher_skips_disabled_channel(db_session, make_channel):
    """A channel disabled between enqueue and dispatch is skipped:
    mark the row failed (since we can't retry a disabled channel)."""
    from arm.notifications.dispatcher import process_one_row

    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
        enabled=False,
    )
    row = _outbox_row(db_session, ch.id, _started_payload())

    process_one_row(row.id)
    db_session.refresh(row)
    assert row.status == "failed"
    assert "disabled" in row.last_error.lower()


def test_dispatcher_handles_vanished_channel(db_session, make_channel):
    """If the channel row is deleted between enqueue and dispatch, mark
    the outbox row failed and move on."""
    from arm.notifications.dispatcher import process_one_row
    from arm.notifications.models import NotificationChannel

    ch = make_channel(
        type="apprise",
        config={"type": "apprise", "url": "discord://x/y"},
        subscribed_events=["job.started"],
    )
    row = _outbox_row(db_session, ch.id, _started_payload())
    db_session.delete(ch)
    db_session.commit()

    process_one_row(row.id)
    db_session.refresh(row)
    assert row.status == "failed"
