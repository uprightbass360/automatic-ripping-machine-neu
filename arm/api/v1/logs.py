"""API v1 — Log endpoints."""
from fastapi import APIRouter

from arm.services import jobs as svc_jobs
import arm.config.config as cfg

router = APIRouter(prefix="/api/v1", tags=["logs"])


@router.get('/jobs/{job_id}/log')
def get_job_log(job_id: int):
    """Get the full log for a job."""
    return svc_jobs.generate_log(cfg.arm_config['LOGPATH'], str(job_id))
