"""API v1 — System endpoints."""
from flask import jsonify
from flask_login import login_required

from arm.api import api_bp
from arm.ui import json_api


@api_bp.route('/v1/system/restart', methods=['POST'])
@login_required
def restart():
    """Restart the ARM UI service."""
    return jsonify(json_api.restart_ui())
