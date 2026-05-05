"""API v1 - Folder import endpoints."""
import logging
import threading
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import arm.config.config as cfg
from arm.api.v1._import_helpers import apply_request_metadata_to_job
from arm.database import db
from arm.models.config import Config
from arm.models.job import Job, JobState
from arm.ripper.folder_scan import scan_folder, validate_ingress_path
from arm.ripper.import_prescan import (
    auto_disable_short_tracks,
    prescan_and_wait as _prescan_and_wait,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["folder"])

# Re-exported for backward compatibility with existing tests that patch
# `arm.api.v1.folder.auto_disable_short_tracks` and import
# `arm.api.v1.folder._prescan_and_wait`. The canonical home for both is
# `arm.ripper.import_prescan`.
__all__ = [
    "auto_disable_short_tracks",
    "FolderScanRequest",
    "FolderCreateRequest",
    "scan_folder_endpoint",
    "create_folder_job",
]


class FolderScanRequest(BaseModel):
    path: str


class FolderCreateRequest(BaseModel):
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


@router.post("/jobs/folder/scan")
def scan_folder_endpoint(req: FolderScanRequest):
    """Scan a folder and return disc type and metadata. No job created."""
    ingress_path = cfg.arm_config.get("INGRESS_PATH", "")
    if not ingress_path:
        return JSONResponse(
            {"success": False, "error": "INGRESS_PATH not configured"},
            status_code=400,
        )
    try:
        result = scan_folder(req.path, ingress_path)
    except FileNotFoundError:
        return JSONResponse(
            {"success": False, "error": "Folder not found or path is not accessible"},
            status_code=400,
        )
    except ValueError:
        return JSONResponse(
            {"success": False, "error": "Not a valid disc folder (no BDMV or VIDEO_TS structure found)"},
            status_code=422,
        )
    return {"success": True, **result}


@router.post("/jobs/folder", status_code=201)
def create_folder_job(req: FolderCreateRequest):
    """Create a folder import job in review state."""
    ingress_path = cfg.arm_config.get("INGRESS_PATH", "")
    if not ingress_path:
        return JSONResponse(
            {"success": False, "error": "INGRESS_PATH not configured"},
            status_code=400,
        )

    # Validate path is under ingress root
    try:
        validate_ingress_path(req.source_path, ingress_path)
    except FileNotFoundError:
        return JSONResponse(
            {"success": False, "error": "Source folder not found"},
            status_code=400,
        )
    except ValueError:
        return JSONResponse(
            {"success": False, "error": "Path is outside the configured ingress directory"},
            status_code=400,
        )

    # Check for duplicate active job with same source_path
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

    # Create job
    job = Job.from_folder(req.source_path, req.disctype)
    apply_request_metadata_to_job(job, req)
    job.status = JobState.IDENTIFYING.value

    db.session.add(job)
    db.session.flush()  # assigns job_id

    # Create Config (copies current arm.yaml settings for this job)
    config = Config(cfg.arm_config, job_id=job.job_id)
    db.session.add(config)
    db.session.commit()

    log.info("Created folder import job %s for %s (prescanning)", job.job_id, req.source_path)

    # Run prescan in background - populates tracks, then moves to MANUAL_PAUSED
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
