"""API v1 — Job endpoints."""
import re

from flask import jsonify, request
from flask_login import login_required

from arm.api import api_bp
from arm.database import db
from arm.models.job import Job, JobState
from arm.models.notifications import Notifications
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


@api_bp.route('/v1/jobs/<int:job_id>/title', methods=['PUT'])
@login_required
def update_job_title(job_id):
    """Update a job's title metadata.

    Accepts JSON body with optional fields:
        title, year, video_type, imdb_id, poster_url

    Sets both the effective and _manual fields for each provided value,
    marks hasnicetitle=True, and creates a notification.
    """
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    body = request.get_json(silent=True) or {}

    old_title = job.title
    old_year = job.year
    updated = {}

    # Map of body keys to (effective_field, manual_field) pairs
    field_map = {
        'title': ('title', 'title_manual'),
        'year': ('year', 'year_manual'),
        'video_type': ('video_type', 'video_type_manual'),
        'imdb_id': ('imdb_id', 'imdb_id_manual'),
        'poster_url': ('poster_url', 'poster_url_manual'),
    }

    args = {}
    for key, (eff, manual) in field_map.items():
        if key in body and body[key] is not None:
            value = str(body[key]).strip()
            if key == 'title':
                value = _clean_for_filename(value)
            args[eff] = value
            args[manual] = value
            updated[key] = value

    if not updated:
        return jsonify({"success": False, "error": "No fields to update"}), 400

    args['hasnicetitle'] = True

    notification = Notifications(
        f"Job: {job.job_id} was updated",
        f"Title: {old_title} ({old_year}) was updated to "
        f"{updated.get('title', old_title)} ({updated.get('year', old_year)})"
    )
    db.session.add(notification)
    ui_utils.database_updater(args, job)

    return jsonify({
        "success": True,
        "job_id": job.job_id,
        "updated": updated,
    })


def _clean_for_filename(string):
    """Clean a string for use in filenames (mirrors ui_utils.clean_for_filename)."""
    string = re.sub(r'\s+', ' ', string)
    string = string.replace(' : ', ' - ')
    string = string.replace(':', '-')
    string = string.replace('&', 'and')
    string = string.replace("\\", " - ")
    string = re.sub(r"[^\w -]", "", string)
    return string.strip()
