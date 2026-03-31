"""API v1 - Notification endpoints."""
import datetime

from fastapi import APIRouter

from arm.database import db
from arm.models.notifications import Notifications
from arm.services import jobs as svc_jobs

router = APIRouter(prefix="/api/v1", tags=["notifications"])


@router.get('/notifications')
def list_notifications(include_cleared: bool = False):
    """List notifications, newest first. Excludes cleared by default."""
    query = Notifications.query
    if not include_cleared:
        query = query.filter(Notifications.cleared == False)  # noqa: E712
    notifications = query.order_by(Notifications.trigger_time.desc()).all()
    return {
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "seen": n.seen,
                "cleared": n.cleared,
                "trigger_time": n.trigger_time.isoformat() if n.trigger_time else None,
                "dismiss_time": n.dismiss_time.isoformat() if n.dismiss_time else None,
            }
            for n in notifications
        ],
    }


@router.get('/notifications/count')
def notification_count():
    """Return notification counts by status."""
    total = Notifications.query.count()
    unseen = Notifications.query.filter(
        Notifications.seen == False  # noqa: E712
    ).count()
    cleared = Notifications.query.filter(
        Notifications.cleared == True  # noqa: E712
    ).count()
    seen = total - unseen - cleared
    return {
        "unseen": unseen,
        "seen": seen,
        "cleared": cleared,
        "total": total,
    }


@router.post('/notifications/dismiss-all')
def dismiss_all_notifications():
    """Mark all unseen notifications as seen."""
    now = datetime.datetime.now()
    count = (
        Notifications.query
        .filter(Notifications.seen == False)  # noqa: E712
        .update({"seen": True, "dismiss_time": now})
    )
    db.session.commit()
    return {"success": True, "count": count}


@router.post('/notifications/purge')
def purge_cleared_notifications():
    """Hard-delete all cleared notifications."""
    count = (
        Notifications.query
        .filter(Notifications.cleared == True)  # noqa: E712
        .delete()
    )
    db.session.commit()
    return {"success": True, "count": count}


@router.patch('/notifications/{notify_id}')
def read_notification(notify_id: int):
    """Mark a notification as read."""
    return svc_jobs.read_notification(str(notify_id))
