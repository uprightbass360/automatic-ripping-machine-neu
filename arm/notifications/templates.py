"""Default templates + render function.

Stub for the publish_event test. Task 5 replaces this with the real
templating logic (per-event defaults + per-channel overrides + variable
substitution).
"""
from typing import Tuple


def render_title_and_body(event, channel_template) -> Tuple[str, str]:
    """Return (title, body) for an event.

    Stub: returns the event_key as title and a stub body. Task 5
    implements per-event defaults and per-channel overrides.
    """
    return event.event_key, f"event {event.event_key} for job {event.job_id}"
