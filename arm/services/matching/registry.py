"""Matcher registry: select and run the right strategy for a job.

Matchers are tried in priority order.  The first one whose
``can_handle(job)`` returns True is used.  Additional matchers can be
registered at import time or via ``register()``.
"""

from __future__ import annotations

import logging
from typing import Sequence

import arm.config.config as cfg
from arm.services.matching.base import MatchResult, MatchStrategy

log = logging.getLogger(__name__)


def _no_matcher_reason(job) -> str:
    """Return a user-friendly reason why no matcher was selected."""
    job_id = getattr(job, "job_id", "?")
    vtype = getattr(job, "video_type", None)

    if vtype != "series":
        return f"Episode matching is only available for TV series (job {job_id} is '{vtype}')"
    if not cfg.arm_config.get("TVDB_API_KEY"):
        return "TVDB API key is not configured. Set TVDB_API_KEY in Settings to enable episode matching."
    imdb_id = getattr(job, "imdb_id", None) or getattr(job, "imdb_id_auto", None)
    if not imdb_id:
        return f"No IMDb ID set for job {job_id}. Use Search to identify the series first."
    return f"No matcher available for job {job_id} (type={vtype})"

# Ordered list — first match wins.
_MATCHERS: list[MatchStrategy] = []


def register(matcher: MatchStrategy) -> None:
    """Add a matcher to the registry (appended at the end)."""
    _MATCHERS.append(matcher)
    log.debug("Registered matcher: %s", matcher.name)


def get_matchers() -> Sequence[MatchStrategy]:
    """Return all registered matchers (read-only view)."""
    return list(_MATCHERS)


def select_matcher(job) -> MatchStrategy | None:
    """Return the first matcher that can handle *job*, or None."""
    for matcher in _MATCHERS:
        if matcher.can_handle(job):
            log.debug("Selected matcher '%s' for job %s", matcher.name, getattr(job, "job_id", "?"))
            return matcher
    return None


def match_job(job, tracks: list[dict] | None = None, **kwargs) -> MatchResult:
    """Select a matcher and run it.

    Builds track data from job.tracks if *tracks* is not provided.
    Returns a MatchResult (possibly with error or zero matches).
    """
    matcher = select_matcher(job)
    if matcher is None:
        reason = _no_matcher_reason(job)
        return MatchResult(
            matcher="none",
            error=reason,
        )

    if tracks is None:
        tracks = _build_track_data(job)

    log.info(
        "Running '%s' matcher on job %s (%d tracks)",
        matcher.name, getattr(job, "job_id", "?"), len(tracks),
    )

    try:
        return matcher.match(job, tracks, **kwargs)
    except Exception as e:
        log.warning("Matcher '%s' failed: %s", matcher.name, e)
        return MatchResult(matcher=matcher.name, error=str(e))


def _build_track_data(job) -> list[dict]:
    """Build list of dicts for matching algorithms from job.tracks."""
    return [
        {"track_number": str(t.track_number), "length": t.length or 0}
        for t in job.tracks
    ]
