"""Dispatcher worker — drains the outbox in an asyncio loop.

The public entry points are:

- ``process_one_row(outbox_id)`` — sync, processes one outbox row.
  Pure function over (outbox row → side effect → outbox + channel
  state mutation). Tested in isolation.
- ``run_dispatcher_loop()`` — async, runs forever. Called as an
  asyncio.Task from FastAPI's ``lifespan``. On startup, reaps stale
  in_flight rows; then loops: dequeue → process each → sleep.

The dispatcher is single-tasked; sends are sequential within the loop.
Concurrency could be added later if real-world send latency demands
it — for a home single-user setup, a few seconds per send is fine.
"""
import asyncio
import datetime
import json
import logging
from typing import Optional

from arm_contracts import (
    Channel as ChannelModel,
    ChannelTemplate,
    NotificationEvent,
    OutboundWebhookPayload,
    ChannelRef,
)
from pydantic import TypeAdapter

from arm.database import db
from arm.notifications.channels.apprise import send_apprise
from arm.notifications.channels.webhook import send_webhook
from arm.notifications.channels.bash import send_bash
from arm.notifications.models import NotificationChannel, NotificationOutbox
from arm.notifications.outbox import (
    cleanup_completed,
    dequeue_due,
    record_failure,
    record_success,
    reap_stale_in_flight,
)
from arm.notifications.templates import (
    render_title_and_body,
    TemplateRenderError,
)

log = logging.getLogger(__name__)

_TICK_INTERVAL_SECONDS = 5.0
_BATCH_SIZE = 20
_CLEANUP_INTERVAL_SECONDS = 3600.0  # outbox retention sweep cadence
_CLEANUP_RETENTION_DAYS = 7

# Keys we set explicitly in _build_bash_env — pass-through loop skips
# these to avoid double-emit / overwrite of curated values.
_BASH_EXPLICIT_PAYLOAD_KEYS = frozenset({
    "event_key",
    "job_id",
    "job_title",
    "job_disc_type",
    "job_imdb_id",
})


def _parse_terminal_flag(error: str) -> bool:
    """Channel senders embed ``terminal=true|false`` in their error
    strings. Parse it back out. Default to terminal=False (retry) if
    the marker is missing — safer than the reverse."""
    if "terminal=true" in error:
        return True
    return False


def _build_bash_env(event_payload: dict, title: str, body: str) -> dict[str, str]:
    """Translate the event payload into the ARM_* env-var contract for
    bash channels. Keep keys stable across releases — third-party
    scripts depend on them."""
    env = {
        "ARM_EVENT_KEY": str(event_payload.get("event_key", "")),
        "ARM_JOB_ID": str(event_payload.get("job_id", "")),
        "ARM_TITLE": title,
        "ARM_BODY": body,
        "ARM_JOB_TITLE": str(event_payload.get("job_title") or ""),
        "ARM_JOB_DISC_TYPE": str(event_payload.get("job_disc_type") or ""),
        "ARM_JOB_IMDB_ID": str(event_payload.get("job_imdb_id") or ""),
    }
    # Pass through any other top-level scalar fields as well, prefixed.
    for k, v in event_payload.items():
        if k in env or k in _BASH_EXPLICIT_PAYLOAD_KEYS:
            continue
        if isinstance(v, (str, int, float, bool)):
            env[f"ARM_{k.upper()}"] = str(v)
    return env


def _reconstruct_event(event_payload: dict):
    """Re-validate the stored event_payload as a NotificationEvent so
    templating sees a model (with type-checked fields) rather than a
    raw dict."""
    adapter = TypeAdapter(NotificationEvent)
    return adapter.validate_python(event_payload)


def process_one_row(outbox_id: int) -> None:
    """Process a single in_flight outbox row.

    All branches end in ``record_success`` or ``record_failure``. This
    function never raises — every failure path captures the error and
    routes it through ``record_failure``, and the entire body is wrapped
    in a final try/except so even a DB commit error in
    ``record_success``/``record_failure`` cannot escape.
    """
    try:
        row = NotificationOutbox.query.get(outbox_id)
        if row is None:
            log.warning("process_one_row: outbox %s vanished", outbox_id)
            return

        channel = NotificationChannel.query.get(row.channel_id)
        if channel is None:
            record_failure(outbox_id, "channel vanished", terminal=True)
            return
        if not channel.enabled:
            record_failure(outbox_id, "channel disabled", terminal=True)
            return

        # 1. Reconstruct event + resolve template.
        try:
            event = _reconstruct_event(row.event_payload)
            tmpl_dict = (channel.templates or {}).get(row.event_key)
            tmpl = ChannelTemplate(**tmpl_dict) if tmpl_dict else None
            title, body = render_title_and_body(event, channel_template=tmpl)
        except TemplateRenderError as exc:
            record_failure(outbox_id, f"template render: {exc}", terminal=True)
            return
        except Exception as exc:
            record_failure(outbox_id, f"event reconstruction: {exc}",
                           terminal=True)
            return

        # 2. Dispatch by channel type.
        cfg = channel.config or {}
        try:
            if channel.type == "apprise":
                ok, error = send_apprise(
                    url=cfg.get("url", ""), title=title, body=body)
            elif channel.type == "webhook":
                payload = OutboundWebhookPayload(
                    event=event,
                    title=title,
                    body=body,
                    channel=ChannelRef(id=channel.id, name=channel.name,
                                       type=channel.type),
                    arm_instance_name=None,
                    sent_at=datetime.datetime.utcnow(),
                )
                payload_dict = json.loads(payload.model_dump_json())
                ok, error = send_webhook(
                    url=cfg.get("url", ""),
                    payload_dict=payload_dict,
                    shared_secret=cfg.get("shared_secret"),
                    headers=cfg.get("headers"),
                )
            elif channel.type == "bash":
                env_vars = _build_bash_env(row.event_payload, title, body)
                ok, error = send_bash(
                    script_path=cfg.get("script_path", ""),
                    title=title, body=body, env_vars=env_vars,
                )
            else:
                record_failure(outbox_id,
                               f"unknown channel type: {channel.type}",
                               terminal=True)
                return
        except Exception as exc:
            # Last-resort catch — channel senders shouldn't raise, but if
            # one does, treat it as transient so a bug doesn't permanently
            # break dispatch.
            record_failure(outbox_id, f"sender raised: {exc}", terminal=False)
            return

        if ok:
            record_success(outbox_id)
        else:
            # Per N9 contract, bash failures are *always* terminal,
            # regardless of any embedded marker. Other channels honor the
            # ``terminal=...`` flag emitted by the sender.
            if channel.type == "bash":
                terminal = True
            else:
                terminal = _parse_terminal_flag(error or "")
            record_failure(outbox_id, error or "send failed",
                           terminal=terminal)
    except Exception:
        # Final safety net — record_success/record_failure can raise on
        # DB commit error. The dispatcher contract guarantees this
        # function never raises, so swallow and log.
        log.exception(
            "dispatcher: unhandled error processing outbox row %s",
            outbox_id,
        )
        return


async def run_dispatcher_loop(stop_event: Optional[asyncio.Event] = None) -> None:
    """Run the dispatcher loop. Yields to the event loop between rows
    so other tasks (HTTP requests, etc.) aren't starved.

    Calling code should pass a ``stop_event`` and set it on shutdown
    so the loop exits cleanly. The FastAPI lifespan handles this.
    """
    log.info("notification dispatcher starting")
    rescued = reap_stale_in_flight(stale_after_minutes=5)
    if rescued:
        log.info("dispatcher rescued %d stale in_flight rows", rescued)

    loop = asyncio.get_event_loop()
    next_cleanup_at = loop.time() + _CLEANUP_INTERVAL_SECONDS

    while True:
        if stop_event is not None and stop_event.is_set():
            log.info("notification dispatcher stopping")
            return
        try:
            rows = dequeue_due(limit=_BATCH_SIZE)
            for row in rows:
                process_one_row(row.id)
                # Yield to the loop between sends.
                await asyncio.sleep(0)
        except Exception as exc:
            # Dispatcher-level failure (DB error etc.) — log and sleep
            # so we don't tight-loop on the same error.
            log.exception("dispatcher tick failed: %s", exc)

        if loop.time() >= next_cleanup_at:
            try:
                deleted = cleanup_completed(
                    older_than_days=_CLEANUP_RETENTION_DAYS,
                )
                if deleted:
                    log.info(
                        "notification outbox cleanup: deleted %d "
                        "completed rows", deleted,
                    )
            except Exception:
                log.exception("notification outbox cleanup failed")
            next_cleanup_at = loop.time() + _CLEANUP_INTERVAL_SECONDS

        await asyncio.sleep(_TICK_INTERVAL_SECONDS)
