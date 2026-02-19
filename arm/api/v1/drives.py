"""API v1 — Drive endpoints."""

from flask import jsonify, request

from arm.api import api_bp
from arm.database import db
from arm.models.system_drives import SystemDrives


@api_bp.route('/v1/drives/<int:drive_id>', methods=['PATCH'])
def update_drive(drive_id):
    """Update a drive's user-editable fields (name, description)."""
    drive = SystemDrives.query.get(drive_id)
    if not drive:
        return jsonify({"success": False, "error": "Drive not found"}), 404

    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"success": False, "error": "No fields to update"}), 400

    updated = {}
    if 'name' in body:
        drive.name = str(body['name']).strip()[:100]
        updated['name'] = drive.name
    if 'description' in body:
        drive.description = str(body['description']).strip()[:200]
        updated['description'] = drive.description
    if 'uhd_capable' in body:
        drive.uhd_capable = bool(body['uhd_capable'])
        updated['uhd_capable'] = drive.uhd_capable

    if not updated:
        return jsonify({"success": False, "error": "No valid fields provided"}), 400

    db.session.commit()
    return jsonify({"success": True, "drive_id": drive.drive_id})
