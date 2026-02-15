"""API v1 — Job endpoints."""
import re

from flask import jsonify, request

from arm.api import api_bp
import arm.config.config as cfg
from arm.database import db
from arm.models.job import Job, JobState
from arm.models.notifications import Notifications
from arm.ui import json_api
import arm.ui.utils as ui_utils


@api_bp.route('/v1/jobs', methods=['GET'])

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

def delete_job(job_id):
    """Delete a job by ID."""
    return jsonify(json_api.delete_job(str(job_id), 'delete'))


@api_bp.route('/v1/jobs/<int:job_id>/abandon', methods=['POST'])

def abandon_job(job_id):
    """Abandon a running job."""
    return jsonify(json_api.abandon_job(str(job_id)))


@api_bp.route('/v1/jobs/<int:job_id>/start', methods=['POST'])
def start_waiting_job(job_id):
    """Start a job that is in 'waiting' status.

    Sets manual_start=True so the ripper loop picks it up.
    """
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    if job.status != JobState.MANUAL_WAIT_STARTED.value:
        return jsonify({"success": False, "error": "Job is not in waiting state"}), 409

    ui_utils.database_updater({"manual_start": True}, job)
    return jsonify({"success": True, "job_id": job.job_id})


@api_bp.route('/v1/jobs/<int:job_id>/cancel', methods=['POST'])
def cancel_waiting_job(job_id):
    """Cancel a job that is in 'waiting' status.

    Unlike abandon (which kills a running process), this simply marks the
    waiting job as failed so the ripper loop exits cleanly.
    """
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    if job.status != JobState.MANUAL_WAIT_STARTED.value:
        return jsonify({"success": False, "error": "Job is not in waiting state"}), 409

    notification = Notifications(
        f"Job: {job.job_id} was cancelled",
        f"'{job.title}' was cancelled by user during manual-wait"
    )
    db.session.add(notification)
    ui_utils.database_updater({"status": JobState.FAILURE.value}, job)

    return jsonify({"success": True, "job_id": job.job_id})


@api_bp.route('/v1/jobs/<int:job_id>/config', methods=['PATCH'])

def change_job_config(job_id):
    """Update job rip parameters.

    Accepts JSON body with optional fields:
        RIPMETHOD: 'mkv' | 'backup'
        DISCTYPE: 'dvd' | 'bluray' | 'music' | 'data'
        MAINFEATURE: bool
        MINLENGTH: int (seconds)
        MAXLENGTH: int (seconds)
    """
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"success": False, "error": "No fields to update"}), 400

    config = job.config
    job_args = {}
    changes = []

    valid_ripmethods = ('mkv', 'backup')
    valid_disctypes = ('dvd', 'bluray', 'music', 'data')

    if 'RIPMETHOD' in body:
        val = str(body['RIPMETHOD']).lower()
        if val not in valid_ripmethods:
            return jsonify({"success": False, "error": f"RIPMETHOD must be one of {valid_ripmethods}"}), 400
        config.RIPMETHOD = val
        cfg.arm_config["RIPMETHOD"] = val
        changes.append(f"Rip Method={val}")

    if 'DISCTYPE' in body:
        val = str(body['DISCTYPE']).lower()
        if val not in valid_disctypes:
            return jsonify({"success": False, "error": f"DISCTYPE must be one of {valid_disctypes}"}), 400
        job_args['disctype'] = val
        changes.append(f"Disctype={val}")

    if 'MAINFEATURE' in body:
        val = 1 if body['MAINFEATURE'] else 0
        config.MAINFEATURE = val
        cfg.arm_config["MAINFEATURE"] = val
        changes.append(f"Main Feature={bool(val)}")

    if 'MINLENGTH' in body:
        val = str(int(body['MINLENGTH']))
        config.MINLENGTH = val
        cfg.arm_config["MINLENGTH"] = val
        changes.append(f"Min Length={val}")

    if 'MAXLENGTH' in body:
        val = str(int(body['MAXLENGTH']))
        config.MAXLENGTH = val
        cfg.arm_config["MAXLENGTH"] = val
        changes.append(f"Max Length={val}")

    if not changes:
        return jsonify({"success": False, "error": "No valid fields provided"}), 400

    message = f"Parameters changed: {', '.join(changes)}"
    notification = Notifications(f"Job: {job.job_id} Config updated!", message)
    db.session.add(notification)
    ui_utils.database_updater(job_args, job)

    return jsonify({"success": True, "job_id": job.job_id})


@api_bp.route('/v1/jobs/<int:job_id>/fix-permissions', methods=['POST'])

def fix_job_permissions(job_id):
    """Fix file permissions for a job."""
    return jsonify(ui_utils.fix_permissions(str(job_id)))


@api_bp.route('/v1/jobs/<int:job_id>/send', methods=['POST'])

def send_job(job_id):
    """Send a job to a remote database."""
    return jsonify(ui_utils.send_to_remote_db(str(job_id)))


@api_bp.route('/v1/jobs/<int:job_id>/title', methods=['PUT'])

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
