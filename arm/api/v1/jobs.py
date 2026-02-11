"""API v1 — Job endpoints."""
from flask import jsonify, request
from flask_login import login_required

from arm.api import api_bp
from arm.models.job import JobState
from arm.ui import json_api
import arm.ui.utils as ui_utils


@api_bp.route('/v1/jobs', methods=['GET'])
@login_required
def list_jobs():
    """List jobs, optionally filtered by status or search query.

    Query params:
        status: 'fail' | 'success' (omit for active jobs)
        q: search query string
    """
    status = request.args.get('status')
    query = request.args.get('q')

    if query:
        return jsonify(json_api.search(query))
    elif status == 'fail':
        return jsonify(json_api.get_x_jobs(JobState.FAILURE.value))
    elif status == 'success':
        return jsonify(json_api.get_x_jobs(JobState.SUCCESS.value))
    else:
        return jsonify(json_api.get_x_jobs('joblist'))


@api_bp.route('/v1/jobs/<int:job_id>', methods=['DELETE'])
@login_required
def delete_job(job_id):
    """Delete a job by ID."""
    return jsonify(json_api.delete_job(str(job_id), 'delete'))


@api_bp.route('/v1/jobs/<int:job_id>/abandon', methods=['POST'])
@login_required
def abandon_job(job_id):
    """Abandon a running job."""
    return jsonify(json_api.abandon_job(str(job_id)))


@api_bp.route('/v1/jobs/<int:job_id>/config', methods=['PATCH'])
@login_required
def change_job_config(job_id):
    """Update job configuration parameters."""
    return jsonify(json_api.change_job_params(job_id))


@api_bp.route('/v1/jobs/<int:job_id>/fix-permissions', methods=['POST'])
@login_required
def fix_job_permissions(job_id):
    """Fix file permissions for a job."""
    return jsonify(ui_utils.fix_permissions(str(job_id)))


@api_bp.route('/v1/jobs/<int:job_id>/send', methods=['POST'])
@login_required
def send_job(job_id):
    """Send a job to a remote database."""
    return jsonify(ui_utils.send_to_remote_db(str(job_id)))
