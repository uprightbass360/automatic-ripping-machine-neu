"""API v1 — System endpoints."""
import os
import subprocess

from flask import jsonify

from arm.api import api_bp
from arm.ui import json_api


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
