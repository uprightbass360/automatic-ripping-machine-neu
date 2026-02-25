"""API v1 — Notification endpoints."""
from fastapi import APIRouter

from arm.services import jobs as svc_jobs

router = APIRouter(prefix="/api/v1", tags=["notifications"])


@router.patch('/notifications/{notify_id}')
def read_notification(notify_id: int):
    """Mark a notification as read."""
    return svc_jobs.read_notification(str(notify_id))
