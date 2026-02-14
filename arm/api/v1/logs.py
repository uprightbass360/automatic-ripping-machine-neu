"""API v1 — Log endpoints."""
from flask import jsonify

from arm.api import api_bp
from arm.ui import json_api
import arm.config.config as cfg


@api_bp.route('/v1/jobs/<int:job_id>/log', methods=['GET'])
def get_job_log(job_id):
    """Get the full log for a job."""
    return jsonify(json_api.generate_log(cfg.arm_config['LOGPATH'], str(job_id)))
