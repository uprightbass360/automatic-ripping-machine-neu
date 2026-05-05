"""API v1 - ISO file import endpoints.

Mirrors `arm.api.v1.folder` but for `.iso` files. The ISO is identified via
MakeMKV's info pass on `iso:{path}`, persisted as a Job with
`source_type=iso`, and prescan runs in a background thread that leaves the
job in MANUAL_PAUSED for review.
"""
import logging
import threading
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from arm_contracts.enums import SkipReason

import arm.config.config as cfg
from arm.database import db
from arm.models.config import Config
from arm.models.job import Job, JobState
from arm.ripper.iso_scan import extract_metadata, validate_iso_path
from arm.ripper.makemkv import prescan_iso_disc_type

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["iso"])


def _auto_disable_short_tracks(job, minlength: int) -> int:
    """Disable tracks below `minlength` seconds and tag with skip_reason.

    MakeMKV silently skips these during rip regardless of the checkbox state,
    so disabling them prevents misleading UI. Returns the count disabled.
    Mirrors arm.api.v1.folder.auto_disable_short_tracks.
    """
    disabled_count = 0
    for track in job.tracks:
        if track.length is not None and track.length < minlength:
            track.enabled = False
            track.skip_reason = SkipReason.too_short.value
            disabled_count += 1
    return disabled_count


class IsoScanRequest(BaseModel):
    path: str


class IsoCreateRequest(BaseModel):
    source_path: str
    title: str
    year: Optional[str] = None
    video_type: str
    disctype: str
    imdb_id: Optional[str] = None
    poster_url: Optional[str] = None
    multi_title: bool = False
    season: Optional[int] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None


@router.post("/jobs/iso/scan")
def scan_iso_endpoint(req: IsoScanRequest):
    """Scan an ISO file: validate, extract metadata, detect disc type. No job created."""
    ingress_path = cfg.arm_config.get("INGRESS_PATH", "")
    if not ingress_path:
        return JSONResponse(
            {"success": False, "error": "INGRESS_PATH not configured"},
            status_code=400,
        )
    try:
        validate_iso_path(req.path, ingress_path)
    except FileNotFoundError as exc:
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=400,
        )
    except ValueError as exc:
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=400,
        )

    meta = extract_metadata(req.path)
    info = prescan_iso_disc_type(req.path)
    return {
        "success": True,
        "disc_type": info["disc_type"],
        "label": meta["label"],
        "title_suggestion": meta["title_suggestion"],
        "year_suggestion": meta["year_suggestion"],
        "iso_size": meta["iso_size"],
        "stream_count": info["stream_count"],
        "volume_id": info.get("volume_id"),
    }


@router.post("/jobs/iso", status_code=201)
def create_iso_job(req: IsoCreateRequest):
    """Create an ISO import job in review state."""
    ingress_path = cfg.arm_config.get("INGRESS_PATH", "")
    if not ingress_path:
        return JSONResponse(
            {"success": False, "error": "INGRESS_PATH not configured"},
            status_code=400,
        )

    try:
        validate_iso_path(req.source_path, ingress_path)
    except FileNotFoundError:
        return JSONResponse(
            {"success": False, "error": "ISO file not found"},
            status_code=400,
        )
    except ValueError:
        return JSONResponse(
            {"success": False, "error": "Path is outside the configured ingress directory or not an ISO"},
            status_code=400,
        )

    existing = Job.query.filter(
        Job.source_path == req.source_path,
        ~Job.finished,
    ).first()
    if existing:
        return JSONResponse(
            {
                "success": False,
                "error": f"Active job already exists for this path (job_id={existing.job_id})",
            },
            status_code=409,
        )

    job = Job.from_iso(req.source_path, req.disctype)
    job.title = req.title
    job.title_auto = req.title
    if req.year:
        job.year = req.year
        job.year_auto = req.year
    job.video_type = req.video_type
    if req.imdb_id:
        job.imdb_id = req.imdb_id
    if req.poster_url:
        job.poster_url = req.poster_url
    job.multi_title = req.multi_title
    if req.season is not None:
        job.season = str(req.season)
        job.season_manual = str(req.season)
    if req.disc_number is not None:
        job.disc_number = req.disc_number
    if req.disc_total is not None:
        job.disc_total = req.disc_total
    job.status = JobState.IDENTIFYING.value

    db.session.add(job)
    db.session.flush()

    config = Config(cfg.arm_config, job_id=job.job_id)
    db.session.add(config)
    db.session.commit()

    log.info("Created ISO import job %s for %s (prescanning)", job.job_id, req.source_path)

    thread = threading.Thread(
        target=_prescan_and_wait, args=(job.job_id,), daemon=True
    )
    thread.start()

    return {
        "success": True,
        "job_id": job.job_id,
        "status": job.status,
        "source_type": job.source_type,
        "source_path": job.source_path,
    }


def _prescan_and_wait(job_id: int):
    """Background: prescan ISO tracks with MakeMKV, then move to MANUAL_PAUSED.

    Mirrors arm.api.v1.folder._prescan_and_wait. Runs in a daemon thread and
    must clean up the scoped DB session on exit to prevent connection pool
    exhaustion.
    """
    from arm.ripper.makemkv import prep_mkv, prescan_track_info

    db.session.commit_timeout = 90
    try:
        job = Job.query.get(job_id)
        if not job:
            log.error("Prescan: job %s not found", job_id)
            return

        from arm.ripper.logger import log_filename, create_file_handler
        import logging as _logging
        log_file = log_filename(job_id)
        job.logfile = log_file
        db.session.commit()
        try:
            _file_handler = create_file_handler(log_file)
            _log_level = cfg.arm_config.get("LOGLEVEL", "INFO")
            _file_handler.setLevel(_log_level)
            _root = _logging.getLogger()
            _root.addHandler(_file_handler)
            _root.setLevel(_log_level)
        except OSError:
            _file_handler = None
            log.warning("Could not create log file handler for %s", log_file)

        try:
            prep_mkv()
            prescan_track_info(job)

            minlength = int(cfg.arm_config.get("MINLENGTH", 120))
            disabled_count = _auto_disable_short_tracks(job, minlength)
            if disabled_count:
                log.info(
                    "Auto-disabled %d tracks shorter than %ds",
                    disabled_count, minlength,
                )

            job.status = JobState.MANUAL_PAUSED.value
            db.session.commit()
            log.info(
                "Prescan complete for ISO job %s - %d tracks found, waiting for review",
                job_id, len(list(job.tracks)),
            )
        except Exception as exc:
            log.error("Prescan failed for ISO job %s: %s", job_id, exc)
            try:
                job.status = JobState.MANUAL_PAUSED.value
                job.errors = f"Prescan failed: {exc}"
                db.session.commit()
            except Exception:
                log.exception("Failed to update ISO job %s status after prescan error", job_id)
    finally:
        if '_file_handler' in dir() and _file_handler is not None:
            _logging.getLogger().removeHandler(_file_handler)
            _file_handler.close()
        db.session.remove()
