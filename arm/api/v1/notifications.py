"""API v1 — Notification endpoints."""
from flask import jsonify
from flask_login import login_required

from arm.api import api_bp
from arm.ui import json_api


@api_bp.route('/v1/notifications/<int:notify_id>', methods=['PATCH'])
@login_required
def read_notification(notify_id):
    """Mark a notification as read."""
    return jsonify(json_api.read_notification(str(notify_id)))
