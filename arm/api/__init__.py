"""ARM REST API — versioned blueprint for external and UI clients."""
from flask import Blueprint

api_bp = Blueprint('api', __name__)

from arm.api.v1 import jobs, logs, settings, notifications, system, drives  # noqa: E402,F401
