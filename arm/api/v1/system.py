"""API v1 — System endpoints."""
import os
import platform
import subprocess

import psutil
from flask import jsonify, request

import arm.config.config as cfg
from arm.api import api_bp
from arm.database import db
from arm.models.app_state import AppState
from arm.ui import json_api


def _detect_cpu() -> str:
    """Detect CPU model name from /proc/cpuinfo (Linux) or platform fallback."""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "Unknown"


@api_bp.route('/v1/system/info', methods=['GET'])
def get_system_info():
    """Return static hardware identity (CPU model, total RAM). No DB access."""
    mem = psutil.virtual_memory()
    return jsonify({
        "cpu": _detect_cpu(),
        "memory_total_gb": round(mem.total / 1073741824, 1),
    })


@api_bp.route('/v1/system/restart', methods=['POST'])
def restart():
    """Restart the ARM UI service."""
    return jsonify(json_api.restart_ui())


@api_bp.route('/v1/system/gpu', methods=['GET'])
def get_gpu_support():
    """Probe available GPU encoders (HandBrake + FFmpeg)."""
    result = {
        "handbrake_nvenc": False,
        "ffmpeg_nvenc_h265": False,
        "ffmpeg_nvenc_h264": False,
        "ffmpeg_vaapi_h265": False,
        "ffmpeg_vaapi_h264": False,
        "ffmpeg_amf_h265": False,
        "ffmpeg_amf_h264": False,
        "ffmpeg_qsv_h265": False,
        "ffmpeg_qsv_h264": False,
        "vaapi_device": False,
    }

    # Check HandBrake NVENC
    try:
        output = subprocess.run(
            ["HandBrakeCLI", "--help"],
            capture_output=True, text=True, timeout=10
        )
        if "nvenc" in output.stdout.lower() or "nvenc" in output.stderr.lower():
            result["handbrake_nvenc"] = True
    except Exception:
        pass

    # Check FFmpeg encoders
    try:
        output = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        stdout = output.stdout
        if "hevc_nvenc" in stdout:
            result["ffmpeg_nvenc_h265"] = True
        if "h264_nvenc" in stdout:
            result["ffmpeg_nvenc_h264"] = True
        if "hevc_vaapi" in stdout:
            result["ffmpeg_vaapi_h265"] = True
        if "h264_vaapi" in stdout:
            result["ffmpeg_vaapi_h264"] = True
        if "hevc_amf" in stdout:
            result["ffmpeg_amf_h265"] = True
        if "h264_amf" in stdout:
            result["ffmpeg_amf_h264"] = True
        if "hevc_qsv" in stdout:
            result["ffmpeg_qsv_h265"] = True
        if "h264_qsv" in stdout:
            result["ffmpeg_qsv_h264"] = True
    except Exception:
        pass

    # Check for VAAPI render device
    vaapi_device = os.environ.get("VAAPI_DEVICE", "/dev/dri/renderD128")
    if os.path.exists(vaapi_device):
        result["vaapi_device"] = True

    return jsonify(result)


@api_bp.route('/v1/system/stats', methods=['GET'])
def get_system_stats():
    """Return live system metrics: CPU, memory, and disk usage."""
    # CPU
    cpu_percent = psutil.cpu_percent()
    cpu_temp = 0.0
    try:
        temps = psutil.sensors_temperatures()
        for key in ('coretemp', 'cpu_thermal', 'k10temp'):
            if temps.get(key):
                cpu_temp = temps[key][0].current
                break
    except (AttributeError, OSError):
        pass

    # Memory
    mem = psutil.virtual_memory()
    memory = {
        "total_gb": round(mem.total / 1073741824, 1),
        "used_gb": round(mem.used / 1073741824, 1),
        "free_gb": round(mem.available / 1073741824, 1),
        "percent": mem.percent,
    }

    # Storage
    media_paths = [
        ("Raw", cfg.arm_config.get("RAW_PATH", "")),
        ("Transcode", cfg.arm_config.get("TRANSCODE_PATH", "")),
        ("Completed", cfg.arm_config.get("COMPLETED_PATH", "")),
    ]
    storage = []
    for name, path in media_paths:
        if not path:
            continue
        try:
            usage = psutil.disk_usage(path)
            storage.append({
                "name": name,
                "path": path,
                "total_gb": round(usage.total / 1073741824, 1),
                "used_gb": round(usage.used / 1073741824, 1),
                "free_gb": round(usage.free / 1073741824, 1),
                "percent": usage.percent,
            })
        except FileNotFoundError:
            continue

    return jsonify({
        "cpu_percent": cpu_percent,
        "cpu_temp": cpu_temp,
        "memory": memory,
        "storage": storage,
    })


@api_bp.route('/v1/system/ripping-enabled', methods=['GET'])
def get_ripping_enabled():
    """Return whether ripping is currently enabled (not paused)."""
    state = AppState.get()
    return jsonify({"ripping_enabled": not state.ripping_paused})


@api_bp.route('/v1/system/ripping-enabled', methods=['POST'])
def set_ripping_enabled():
    """Toggle global ripping pause.

    Accepts JSON body: {"enabled": bool}
    """
    body = request.get_json(silent=True) or {}
    if 'enabled' not in body:
        return jsonify({"success": False, "error": "'enabled' field required"}), 400

    state = AppState.get()
    state.ripping_paused = not bool(body['enabled'])
    db.session.commit()

    return jsonify({
        "success": True,
        "ripping_enabled": not state.ripping_paused,
    })
