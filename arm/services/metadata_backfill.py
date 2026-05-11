"""One-shot best-effort backfill for jobs created before the MediaMetadata
column purge (Phase 2, migration u6v7w8x9y0).

Those jobs have imdb_id_auto set on the Job row (the matcher ran on the
pre-Phase-2 code path and only wrote columns, not the blob), but the
media_metadata_auto JSON blob is empty because the migration's backfill
relied on poster_url_auto which was often empty even when imdb_id_auto
had a value.

On every boot we re-fetch via the same metadata adapter the live matcher
uses now and write the blob. Fail-soft: rows whose API call errors are
skipped silently and retried on the next boot.
"""
import asyncio
import logging
from typing import Iterable

from arm_contracts import MediaMetadata
from arm_contracts.enums import VideoType

from arm.database import db
from arm.models.job import Job
from arm.services import metadata
from arm.services.metadata import MetadataConfigError

log = logging.getLogger("arm")


def _normalize_video_type(value: str | None) -> VideoType | None:
    if value == "movie":
        return VideoType.movie
    if value == "series":
        return VideoType.series
    return None


def _legacy_dict_to_metadata(legacy: dict) -> MediaMetadata:
    """Build a MediaMetadata from the legacy-shape dict the adapter returns.

    The adapter emits flat keys (poster_url, plot, runtime_seconds, ...).
    Pass them through to MediaMetadata; the model silently ignores any
    unknown keys.
    """
    payload = dict(legacy)
    vt = payload.pop("video_type", None)
    payload["video_type"] = _normalize_video_type(vt)
    # Filter to known MediaMetadata fields so a future adapter addition
    # doesn't crash with a validation error before we update the contract.
    allowed = set(MediaMetadata.model_fields.keys())
    return MediaMetadata(**{k: v for k, v in payload.items() if k in allowed and v not in (None, "", [])})


async def _backfill_one(job_id: int, imdb_id: str) -> bool:
    """Fetch metadata for one job and persist as the auto blob.

    Returns True on success (blob written or already-correct skip),
    False on error (will retry next boot).
    """
    try:
        legacy = await metadata.get_details(imdb_id)
    except MetadataConfigError as exc:
        log.debug("metadata-backfill: skipping job %s (config): %s", job_id, exc)
        return False
    except Exception as exc:
        log.debug("metadata-backfill: skipping job %s (fetch error): %s", job_id, exc)
        return False

    if not legacy:
        log.debug("metadata-backfill: imdb_id=%s returned no result for job %s", imdb_id, job_id)
        return False

    try:
        meta = _legacy_dict_to_metadata(legacy)
    except Exception as exc:
        log.warning("metadata-backfill: validation error for job %s imdb=%s: %s", job_id, imdb_id, exc)
        return False

    # Re-fetch the job inside this task's session so we don't touch
    # rows another task is operating on.
    job = Job.query.get(job_id)
    if job is None or job.media_metadata_auto:
        # Job was deleted, or another path wrote the blob first - nothing to do.
        return True
    job.set_metadata_auto(meta)
    db.session.commit()
    return True


def _candidate_job_ids() -> list[tuple[int, str]]:
    """Find jobs with imdb_id set but no media_metadata_auto blob."""
    rows = (
        db.session.query(Job.job_id, Job.imdb_id)
        .filter(Job.imdb_id.isnot(None))
        .filter(Job.imdb_id != "")
        .filter((Job.media_metadata_auto.is_(None)) | (Job.media_metadata_auto == ""))
        .all()
    )
    return [(r.job_id, r.imdb_id) for r in rows]


async def backfill_media_metadata():
    """Run a single backfill sweep over all candidate jobs.

    Quiet log if there's nothing to do; otherwise logs counts so an
    operator can tell whether the gap is closing.
    """
    try:
        candidates = _candidate_job_ids()
    except Exception as exc:
        log.warning("metadata-backfill: query failed, skipping: %s", exc)
        return

    if not candidates:
        return

    log.info("metadata-backfill: %d job(s) eligible for blob backfill", len(candidates))
    succeeded = 0
    for job_id, imdb_id in candidates:
        if await _backfill_one(job_id, imdb_id):
            succeeded += 1
    log.info(
        "metadata-backfill: wrote blob for %d/%d eligible jobs (remainder will retry next boot)",
        succeeded,
        len(candidates),
    )
