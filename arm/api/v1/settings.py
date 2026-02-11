"""API v1 — Settings endpoints."""
from flask import jsonify
from flask_login import login_required

from arm.api import api_bp
from arm.ui import json_api


@api_bp.route('/v1/settings/notify-timeout', methods=['GET'])
@login_required
def get_notify_timeout():
    """Get the notification timeout setting."""
    return jsonify(json_api.get_notify_timeout('notify_timeout'))
