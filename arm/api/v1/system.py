"""API v1 — System endpoints."""
import os
import platform
import subprocess

import psutil
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import arm.config.config as cfg
from arm.database import db
from arm.models.app_state import AppState
from arm.services import jobs as svc_jobs

router = APIRouter(prefix="/api/v1", tags=["system"])


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


@router.get('/system/info')
def get_system_info():
    """Return static hardware identity (CPU model, total RAM). No DB access."""
    mem = psutil.virtual_memory()
    return {
        "cpu": _detect_cpu(),
        "memory_total_gb": round(mem.total / 1073741824, 1),
    }


@router.post('/system/restart')
def restart():
    """Restart the ARM UI service."""
    return svc_jobs.restart_ui()


@router.get('/system/gpu')
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

    return result


@router.get('/system/stats')
def get_system_stats():
    """Return live system metrics: CPU, memory, and disk usage."""
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

    mem = psutil.virtual_memory()
    memory = {
        "total_gb": round(mem.total / 1073741824, 1),
        "used_gb": round(mem.used / 1073741824, 1),
        "free_gb": round(mem.available / 1073741824, 1),
        "percent": mem.percent,
    }

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

    return {
        "cpu_percent": cpu_percent,
        "cpu_temp": cpu_temp,
        "memory": memory,
        "storage": storage,
    }


@router.get('/system/ripping-enabled')
def get_ripping_enabled():
    """Return whether ripping is currently enabled (not paused)."""
    state = AppState.get()
    return {"ripping_enabled": not state.ripping_paused}


@router.get('/system/version')
def get_version():
    """Return ARM, MakeMKV, and HandBrake versions."""
    import re

    arm_version = "unknown"
    install_path = cfg.arm_config.get("INSTALLPATH", "")
    version_file = os.path.join(install_path, "VERSION")
    try:
        with open(version_file) as f:
            arm_version = f.read().strip()
    except OSError:
        pass

    makemkv_version = "unknown"
    try:
        result = subprocess.run(
            ["makemkvcon", "--version"],
            capture_output=True, text=True, timeout=5
        )
        m = re.search(r'v([\d.]+)', result.stdout + result.stderr)
        if m:
            makemkv_version = m.group(1)
    except Exception:
        pass

    handbrake_version = "unknown"
    try:
        result = subprocess.run(
            ["HandBrakeCLI", "--version"],
            capture_output=True, text=True, timeout=5
        )
        m = re.search(r'HandBrake ([\d.]+)', result.stdout + result.stderr)
        if m:
            handbrake_version = m.group(1)
    except Exception:
        pass

    return {
        "arm_version": arm_version,
        "makemkv_version": makemkv_version,
        "handbrake_version": handbrake_version,
    }


@router.post('/system/ripping-enabled')
async def set_ripping_enabled(request: Request):
    """Toggle global ripping pause."""
    body = await request.json()
    if 'enabled' not in body:
        return JSONResponse(
            {"success": False, "error": "'enabled' field required"},
            status_code=400,
        )

    state = AppState.get()
    state.ripping_paused = not bool(body['enabled'])
    db.session.commit()

    return {
        "success": True,
        "ripping_enabled": not state.ripping_paused,
    }
