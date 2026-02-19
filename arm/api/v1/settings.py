"""API v1 — Settings endpoints."""
import importlib

import logging

from flask import jsonify, request

import arm.config.config as cfg

app = logging.getLogger("ARM")
from arm.api import api_bp
from arm.models.config import hidden_attribs, HIDDEN_VALUE
from arm.ui import json_api
from arm.ui.utils import generate_comments, build_arm_cfg


@api_bp.route('/v1/settings/notify-timeout', methods=['GET'])
def get_notify_timeout():
    """Get the notification timeout setting."""
    return jsonify(json_api.get_notify_timeout('notify_timeout'))


@api_bp.route('/v1/settings/config', methods=['GET'])
def get_config():
    """Return live arm.yaml config with sensitive fields masked."""
    raw_config = dict(cfg.arm_config)
    config = {}
    for key in list(raw_config.keys()):
        if key in hidden_attribs and raw_config[key]:
            config[str(key)] = HIDDEN_VALUE
        else:
            config[str(key)] = str(raw_config[key]) if raw_config[key] is not None else None

    comments = generate_comments()
    return jsonify({"config": config, "comments": comments})


@api_bp.route('/v1/settings/config', methods=['PUT'])
def update_config():
    """Update arm.yaml config from JSON payload.

    Expects ``{"config": {key: value, ...}}``.  For sensitive fields where
    the client sends the ``HIDDEN_VALUE`` sentinel, the existing value is
    preserved so secrets are never lost on save.
    """
    data = request.get_json(silent=True)
    if not data or "config" not in data:
        return jsonify({"success": False, "error": "Missing 'config' in request body"}), 400

    incoming = data["config"]
    if not isinstance(incoming, dict) or len(incoming) == 0:
        return jsonify({"success": False, "error": "'config' must be a non-empty object"}), 400

    # Preserve existing values for hidden fields that were not changed
    current = dict(cfg.arm_config)
    for key in hidden_attribs:
        if key in incoming and incoming[key] == HIDDEN_VALUE and key in current:
            incoming[key] = str(current[key])

    # Convert all values to strings (build_arm_cfg expects str values)
    form_data = {k: str(v) for k, v in incoming.items()}

    comments = generate_comments()
    arm_cfg_text = build_arm_cfg(form_data, comments)

    try:
        with open(cfg.arm_config_path, "w") as f:
            f.write(arm_cfg_text)
    except OSError as e:
        app.logger.error(f"Failed to write config: {e}")
        return jsonify({"success": False, "error": "Failed to write config file"}), 500

    # Reload the config module so the running process picks up changes
    try:
        importlib.reload(cfg)
    except Exception as e:
        app.logger.error(f"Config reload failed: {e}")
        return jsonify({
            "success": True,
            "warning": "Config saved but reload failed",
        })

    return jsonify({"success": True})
