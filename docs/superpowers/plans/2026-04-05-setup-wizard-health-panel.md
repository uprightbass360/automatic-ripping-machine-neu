# Setup Wizard Readiness Check + Settings Health Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a preflight readiness check to the setup wizard and Settings page that validates API keys, MakeMKV registration, and path permissions with UID/GID ownership info.

**Architecture:** New `POST /system/preflight` endpoint in ARM-neu runs all checks and returns a unified response. The UI adds a wizard step (ReadinessCheckStep) and a Settings section (SystemHealth) that both consume the same endpoint. A companion `POST /system/preflight/fix` endpoint handles auto-fixable issues (MakeMKV key update, chown on owned paths).

**Tech Stack:** Python/FastAPI (ARM-neu), SvelteKit/Svelte 5 runes/TypeScript (ARM-UI), pytest, vitest

**Spec:** `docs/superpowers/specs/2026-04-05-setup-wizard-health-panel-design.md`

**Repos:**
- ARM-neu: `/home/upb/src/automatic-ripping-machine-neu` (branch: `feat/setup-preflight`)
- ARM-UI: `/home/upb/src/automatic-ripping-machine-ui` (branch: `feat/setup-preflight`)

**Testing commands:**
- ARM-neu: `python3 -m pytest test/ -x -q --tb=short`
- ARM-UI backend: `cd /home/upb/src/automatic-ripping-machine-ui && python3 -m pytest tests/ -x -q --tb=short`
- ARM-UI frontend: `cd /home/upb/src/automatic-ripping-machine-ui/frontend && npm run build && npx svelte-check --tsconfig ./tsconfig.json`

---

## File Map

### ARM-neu (automatic-ripping-machine-neu)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `arm/services/preflight.py` | Preflight check orchestration: run all key checks, path ownership checks, host path resolution |
| Modify | `arm/services/tvdb.py` | Add `test_tvdb_key()` public function |
| Modify | `arm/api/v1/system.py` | Add `POST /system/preflight` and `POST /system/preflight/fix` endpoints |
| Modify | `docker-compose.yml` | Pass `ARM_CONFIG_PATH`, `ARM_LOGS_PATH`, `ARM_MUSIC_PATH` as env vars to arm-rippers |
| Create | `test/test_preflight.py` | Tests for preflight service and endpoints |

### ARM-UI (automatic-ripping-machine-ui)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/services/arm_client.py` | Add `run_preflight()` and `fix_preflight()` client methods |
| Modify | `backend/routers/system.py` | Add preflight proxy routes |
| Modify | `frontend/src/lib/api/system.ts` | Add `runPreflight()` and `fixPreflight()` TypeScript API calls |
| Create | `frontend/src/lib/components/setup/ReadinessCheckStep.svelte` | Wizard step 3: readiness check display |
| Modify | `frontend/src/lib/components/setup/SetupWizard.svelte` | Insert ReadinessCheckStep as step 3 of 4 |
| Create | `frontend/src/lib/components/settings/SystemHealth.svelte` | Settings page health panel |
| Modify | `frontend/src/routes/settings/+page.svelte` | Import and render SystemHealth at top |

---

## Chunk 1: ARM-neu Backend

### Task 1: Add `test_tvdb_key()` to tvdb.py

**Files:**
- Modify: `arm/services/tvdb.py`
- Create: `test/test_preflight.py`

- [ ] **Step 1: Write the failing test**

In `test/test_preflight.py`:

```python
"""Tests for preflight service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


class TestTvdbKeyValidation:
    @pytest.mark.asyncio
    async def test_tvdb_key_valid(self):
        from arm.services.tvdb import test_tvdb_key

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": {"token": "fake-token"}}

        with patch("arm.services.tvdb.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await test_tvdb_key("valid-key-123")

        assert result["success"] is True
        assert "valid" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_tvdb_key_invalid(self):
        from arm.services.tvdb import test_tvdb_key

        with patch("arm.services.tvdb.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "401", request=MagicMock(), response=MagicMock(status_code=401)
                )
            )
            mock_client_cls.return_value = mock_client

            result = await test_tvdb_key("bad-key")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_tvdb_key_timeout(self):
        from arm.services.tvdb import test_tvdb_key

        with patch("arm.services.tvdb.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client_cls.return_value = mock_client

            result = await test_tvdb_key("some-key")

        assert result["success"] is False
        assert "timeout" in result["message"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest test/test_preflight.py::TestTvdbKeyValidation -x -q --tb=short`
Expected: FAIL with `ImportError` or `AttributeError` (function doesn't exist yet)

- [ ] **Step 3: Implement `test_tvdb_key()`**

Add to `arm/services/tvdb.py` after the `_ensure_token()` function (after line 48):

```python
async def test_tvdb_key(api_key: str) -> dict[str, str]:
    """Test a TVDB API key by attempting login. Returns {success, message}."""
    if not api_key or not api_key.strip():
        return {"success": False, "message": "TVDB_API_KEY is empty"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{_BASE}/login", json={"apikey": api_key.strip()})
            resp.raise_for_status()
            data = resp.json()
            if data.get("data", {}).get("token"):
                return {"success": True, "message": "TVDB API key is valid"}
            return {"success": False, "message": "TVDB login returned no token"}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return {"success": False, "message": "Invalid TVDB API key"}
        return {"success": False, "message": f"TVDB returned HTTP {exc.response.status_code}"}
    except httpx.TimeoutException:
        return {"success": False, "message": "TVDB request timed out - check network"}
    except httpx.ConnectError:
        return {"success": False, "message": "Cannot connect to TVDB - check network/DNS"}
    except Exception as exc:
        log.warning("TVDB key test failed: %s", exc)
        return {"success": False, "message": f"Test failed: {type(exc).__name__}"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest test/test_preflight.py::TestTvdbKeyValidation -x -q --tb=short`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add arm/services/tvdb.py test/test_preflight.py
git commit -m "feat: add test_tvdb_key() for TVDB API key validation"
```

---

### Task 2: Create preflight service with host path resolution

**Files:**
- Create: `arm/services/preflight.py`
- Modify: `test/test_preflight.py`

- [ ] **Step 1: Write the failing tests**

Append to `test/test_preflight.py`:

```python
import os


class TestResolveHostPath:
    def test_bind_mount_resolved(self, tmp_path):
        from arm.services.preflight import resolve_host_path

        mountinfo = (
            "36 1 8:1 / / rw - ext4 /dev/sda1 rw\n"
            "100 36 8:1 /home/arm/media /home/arm/media rw - ext4 /dev/sda1 rw,bind\n"
        )
        with patch("builtins.open", mock_open(read_data=mountinfo)):
            result = resolve_host_path("/home/arm/media/raw")
        assert result == "/home/arm/media/raw"

    def test_env_var_fallback(self):
        from arm.services.preflight import resolve_host_path

        # Empty mountinfo - no bind mounts found
        with patch("builtins.open", mock_open(read_data="")), \
             patch.dict(os.environ, {"ARM_MEDIA_PATH": "/nfs/media"}):
            result = resolve_host_path("/home/arm/media/raw")
        assert result == "/nfs/media/raw"

    def test_no_match_returns_none(self):
        from arm.services.preflight import resolve_host_path

        with patch("builtins.open", mock_open(read_data="")), \
             patch.dict(os.environ, {}, clear=True):
            result = resolve_host_path("/some/unknown/path")
        assert result is None


class TestCheckPath:
    def test_existing_writable_path(self, tmp_path):
        from arm.services.preflight import check_path

        d = tmp_path / "raw"
        d.mkdir()
        result = check_path("RAW_PATH", str(d), 1000, 1000)
        assert result["exists"] is True
        assert result["writable"] is True
        assert result["name"] == "RAW_PATH"

    def test_nonexistent_path(self):
        from arm.services.preflight import check_path

        result = check_path("RAW_PATH", "/nonexistent/path", 1000, 1000)
        assert result["exists"] is False
        assert result["writable"] is False
        assert result["match"] is False

    def test_uid_mismatch(self, tmp_path):
        from arm.services.preflight import check_path

        d = tmp_path / "raw"
        d.mkdir()
        # Stat will return the real UID but expected is different
        result = check_path("RAW_PATH", str(d), 9999, 9999)
        assert result["exists"] is True
        assert result["match"] is False


from unittest.mock import mock_open, patch


class TestRunChecks:
    @pytest.mark.asyncio
    async def test_returns_correct_shape(self):
        from arm.services.preflight import run_checks

        with patch("arm.services.preflight._check_omdb_key", new_callable=AsyncMock,
                    return_value={"name": "omdb_key", "success": True, "message": "OK", "fixable": False}), \
             patch("arm.services.preflight._check_tmdb_key", new_callable=AsyncMock,
                    return_value={"name": "tmdb_key", "success": False, "message": "Not configured", "fixable": False}), \
             patch("arm.services.preflight._check_tvdb_key", new_callable=AsyncMock,
                    return_value={"name": "tvdb_key", "success": False, "message": "Not configured", "fixable": False}), \
             patch("arm.services.preflight._check_makemkv_key",
                    return_value={"name": "makemkv_key", "success": True, "message": "OK", "fixable": True}), \
             patch("arm.services.preflight._get_path_checks",
                    return_value=[]), \
             patch("os.getuid", return_value=1000), \
             patch("os.getgid", return_value=1000):
            result = await run_checks()

        assert "arm_uid" in result
        assert "arm_gid" in result
        assert "checks" in result
        assert "paths" in result
        assert len(result["checks"]) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_preflight.py::TestResolveHostPath test/test_preflight.py::TestCheckPath test/test_preflight.py::TestRunChecks -x -q --tb=short`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `arm/services/preflight.py`**

```python
"""Preflight checks - validates keys, paths, and permissions for setup wizard and health panel."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import arm.config.config as cfg

log = logging.getLogger(__name__)

# Env var fallback mapping: container mount point -> env var with host path
_ENV_PATH_MAP = {
    "/home/arm/media": "ARM_MEDIA_PATH",
    "/etc/arm/config": "ARM_CONFIG_PATH",
    "/home/arm/logs": "ARM_LOGS_PATH",
    "/home/arm/music": "ARM_MUSIC_PATH",
}


def resolve_host_path(container_path: str) -> str | None:
    """Resolve a container path to its host bind-mount source.

    Parses /proc/self/mountinfo to find the host path for bind-mounts.
    Falls back to known env var mappings.
    Returns None for named Docker volumes or unknown paths.
    """
    # Try /proc/self/mountinfo first
    try:
        with open("/proc/self/mountinfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 5:
                    continue
                mount_point = parts[4]
                # Find the source path (after the " - " separator)
                try:
                    sep_idx = parts.index("-")
                    # For bind mounts, root (parts[3]) contains the source subpath
                    root = parts[3]
                    if container_path.startswith(mount_point) and root != "/":
                        suffix = container_path[len(mount_point):]
                        return root + suffix
                except (ValueError, IndexError):
                    continue
    except OSError:
        pass

    # Fallback: env var mapping
    for mount_prefix, env_var in _ENV_PATH_MAP.items():
        if container_path.startswith(mount_prefix):
            host_base = os.environ.get(env_var)
            if host_base:
                suffix = container_path[len(mount_prefix):]
                return host_base + suffix

    return None


def check_path(name: str, path: str, expected_uid: int, expected_gid: int) -> dict[str, Any]:
    """Check a single path for existence, writability, and UID/GID ownership."""
    result: dict[str, Any] = {
        "name": name,
        "container_path": path,
        "host_path": resolve_host_path(path),
        "exists": False,
        "writable": False,
        "owner_uid": None,
        "owner_gid": None,
        "expected_uid": expected_uid,
        "expected_gid": expected_gid,
        "match": False,
        "fixable": False,
    }

    if not os.path.exists(path):
        return result

    result["exists"] = True
    result["writable"] = os.access(path, os.W_OK)

    try:
        st = os.stat(path)
        result["owner_uid"] = st.st_uid
        result["owner_gid"] = st.st_gid
        result["match"] = (st.st_uid == expected_uid and st.st_gid == expected_gid)
    except OSError:
        pass

    # Check if we can fix it (we can chown if we're root or own the parent)
    if not result["match"] and result["exists"]:
        try:
            parent = os.path.dirname(path)
            parent_st = os.stat(parent)
            result["fixable"] = (os.getuid() == 0 or parent_st.st_uid == os.getuid())
        except OSError:
            pass

    return result


def _get_path_checks() -> list[dict[str, Any]]:
    """Check all configured ARM paths."""
    uid = os.getuid()
    gid = os.getgid()

    path_keys = [
        "RAW_PATH", "COMPLETED_PATH", "TRANSCODE_PATH",
        "LOGPATH", "DBFILE",
    ]
    results = []
    for key in path_keys:
        value = cfg.arm_config.get(key, "")
        if value:
            results.append(check_path(key, value, uid, gid))
    # Also check config dir
    config_dir = "/etc/arm/config"
    if os.path.exists(config_dir):
        results.append(check_path("CONFIG_DIR", config_dir, uid, gid))
    return results


async def _check_omdb_key() -> dict[str, Any]:
    """Check OMDb API key."""
    key = cfg.arm_config.get("OMDB_API_KEY", "")
    if not key or not key.strip():
        return {"name": "omdb_key", "success": False, "message": "Not configured", "fixable": False}
    from arm.services.metadata import test_configured_key
    try:
        result = await test_configured_key(override_key=key, override_provider="omdb")
        return {"name": "omdb_key", "success": result.get("success", False),
                "message": result.get("message", "Unknown"), "fixable": False}
    except Exception as exc:
        return {"name": "omdb_key", "success": False, "message": str(exc), "fixable": False}


async def _check_tmdb_key() -> dict[str, Any]:
    """Check TMDb API key."""
    key = cfg.arm_config.get("TMDB_API_KEY", "")
    if not key or not key.strip():
        return {"name": "tmdb_key", "success": False, "message": "Not configured", "fixable": False}
    from arm.services.metadata import test_configured_key
    try:
        result = await test_configured_key(override_key=key, override_provider="tmdb")
        return {"name": "tmdb_key", "success": result.get("success", False),
                "message": result.get("message", "Unknown"), "fixable": False}
    except Exception as exc:
        return {"name": "tmdb_key", "success": False, "message": str(exc), "fixable": False}


async def _check_tvdb_key() -> dict[str, Any]:
    """Check TVDB API key."""
    key = cfg.arm_config.get("TVDB_API_KEY", "")
    if not key or not key.strip():
        return {"name": "tvdb_key", "success": False, "message": "Not configured", "fixable": False}
    from arm.services.tvdb import test_tvdb_key
    result = await test_tvdb_key(key)
    return {"name": "tvdb_key", "success": result["success"],
            "message": result["message"], "fixable": False}


def _check_makemkv_key() -> dict[str, Any]:
    """Check MakeMKV key validity."""
    from arm.ripper.makemkv import prep_mkv, UpdateKeyRunTimeError, UpdateKeyErrorCodes

    message = "MakeMKV key is valid"
    success = True
    try:
        prep_mkv()
    except UpdateKeyRunTimeError as exc:
        success = False
        code = UpdateKeyErrorCodes(exc.returncode)
        messages = {
            UpdateKeyErrorCodes.URL_ERROR: "Could not reach forum.makemkv.com",
            UpdateKeyErrorCodes.PARSE_ERROR: "MakeMKV settings file is corrupt",
            UpdateKeyErrorCodes.INTERNAL_ERROR: "Key update script produced invalid output",
            UpdateKeyErrorCodes.INVALID_MAKEMKV_SERIAL: "Invalid MakeMKV serial key format",
        }
        message = messages.get(code, f"Key update failed ({code.name})")
    except Exception as exc:
        success = False
        message = f"Key check failed: {type(exc).__name__}"

    return {"name": "makemkv_key", "success": success, "message": message, "fixable": True}


async def run_checks() -> dict[str, Any]:
    """Run all preflight checks. Returns unified response."""
    checks = [
        await _check_omdb_key(),
        await _check_tmdb_key(),
        await _check_tvdb_key(),
        _check_makemkv_key(),
    ]

    return {
        "arm_uid": os.getuid(),
        "arm_gid": os.getgid(),
        "checks": checks,
        "paths": _get_path_checks(),
    }


async def run_fixes(items: list[str]) -> dict[str, Any]:
    """Attempt to fix the requested items, then re-run all checks."""
    uid = os.getuid()
    gid = os.getgid()

    for item in items:
        if item == "makemkv_key":
            try:
                from arm.ripper.makemkv import prep_mkv
                prep_mkv()
            except Exception as exc:
                log.warning("MakeMKV key fix failed: %s", exc)
        else:
            # Treat as a path name (e.g. "RAW_PATH", "CONFIG_DIR")
            # Look up the actual path from config or known dirs
            if item == "CONFIG_DIR":
                path = "/etc/arm/config"
            else:
                path = cfg.arm_config.get(item, "")
            if path and os.path.exists(path):
                try:
                    os.chown(path, uid, gid)
                    log.info("Fixed ownership on %s to %d:%d", path, uid, gid)
                except OSError as exc:
                    log.warning("Cannot chown %s: %s", path, exc)

    return await run_checks()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_preflight.py -x -q --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add arm/services/preflight.py test/test_preflight.py
git commit -m "feat: add preflight service with key checks, path ownership, and host path resolution"
```

---

### Task 3: Add preflight endpoints to system.py

**Files:**
- Modify: `arm/api/v1/system.py`

- [ ] **Step 1: Add the endpoints**

Add at the end of `arm/api/v1/system.py` (before the `get_job_stats` function):

```python
@router.post('/system/preflight')
async def preflight():
    """Run all preflight checks: API keys, MakeMKV key, path permissions."""
    from arm.services.preflight import run_checks
    return await run_checks()


@router.post('/system/preflight/fix')
async def preflight_fix(body: dict):
    """Attempt to fix specified issues, then re-run all checks."""
    from arm.services.preflight import run_fixes
    items = body.get("fix", [])
    if not isinstance(items, list):
        return JSONResponse({"success": False, "error": "'fix' must be a list"}, status_code=400)
    return await run_fixes(items)
```

- [ ] **Step 2: Run existing system tests to verify no regressions**

Run: `python3 -m pytest test/ -x -q --tb=short -k "system or preflight"`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add arm/api/v1/system.py
git commit -m "feat: add preflight and preflight/fix API endpoints"
```

---

### Task 4: Pass host path env vars to arm-rippers in docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add env vars to arm-rippers environment block**

In `docker-compose.yml`, add these lines to the `arm-rippers` environment section (after the existing `ARM_SHARED_RAW_PATH` line):

```yaml
      # Host path mapping — lets preflight endpoint show host paths in health checks
      - ARM_MEDIA_PATH=${ARM_MEDIA_PATH}
      - ARM_CONFIG_PATH=${ARM_CONFIG_PATH}
      - ARM_LOGS_PATH=${ARM_LOGS_PATH}
      - ARM_MUSIC_PATH=${ARM_MUSIC_PATH}
```

- [ ] **Step 2: Verify compose file is valid**

Run: `docker compose config --quiet`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: pass host path env vars to arm-rippers for preflight host path resolution"
```

---

## Chunk 2: ARM-UI Backend Proxy

### Task 5: Add preflight proxy to UI backend

**Files:**
- Modify: `backend/services/arm_client.py` (in ARM-UI repo)
- Modify: `backend/routers/system.py` (in ARM-UI repo)

- [ ] **Step 1: Add client methods to arm_client.py**

Add to `backend/services/arm_client.py`:

```python
async def run_preflight() -> dict[str, Any] | None:
    """Run ARM preflight checks."""
    return await _post("/api/v1/system/preflight")


async def fix_preflight(items: list[str]) -> dict[str, Any] | None:
    """Fix specified preflight issues, then re-check."""
    return await _post("/api/v1/system/preflight/fix", json={"fix": items})
```

Note: Check if `_post` helper exists. If not, add it following the pattern of existing methods (use `get_client().post()`). The existing methods use a `_get` helper pattern - follow the same style for POST.

- [ ] **Step 2: Add proxy routes to system.py**

Add to `backend/routers/system.py`:

```python
@router.post("/system/preflight")
async def run_preflight() -> dict[str, Any]:
    """Run ARM preflight checks (proxied to ARM backend)."""
    result = await arm_client.run_preflight()
    if result is None:
        raise HTTPException(status_code=503, detail="ARM web UI is unreachable")
    return result


@router.post("/system/preflight/fix")
async def fix_preflight(body: dict) -> dict[str, Any]:
    """Fix preflight issues (proxied to ARM backend)."""
    result = await arm_client.fix_preflight(body.get("fix", []))
    if result is None:
        raise HTTPException(status_code=503, detail="ARM web UI is unreachable")
    return result
```

- [ ] **Step 3: Run UI backend tests**

Run: `cd /home/upb/src/automatic-ripping-machine-ui && python3 -m pytest tests/ -x -q --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
cd /home/upb/src/automatic-ripping-machine-ui
git add backend/services/arm_client.py backend/routers/system.py
git commit -m "feat: add preflight proxy routes to UI backend"
```

---

## Chunk 3: ARM-UI Frontend

### Task 6: Add preflight API functions to frontend

**Files:**
- Modify: `frontend/src/lib/api/system.ts` (in ARM-UI repo)

- [ ] **Step 1: Add TypeScript types and API functions**

Add to `frontend/src/lib/api/system.ts`:

```typescript
export interface PreflightCheck {
	name: string;
	success: boolean;
	message: string;
	fixable: boolean;
}

export interface PreflightPath {
	name: string;
	container_path: string;
	host_path: string | null;
	exists: boolean;
	writable: boolean;
	owner_uid: number | null;
	owner_gid: number | null;
	expected_uid: number;
	expected_gid: number;
	match: boolean;
	fixable: boolean;
}

export interface PreflightResult {
	arm_uid: number;
	arm_gid: number;
	checks: PreflightCheck[];
	paths: PreflightPath[];
}

export function runPreflight(): Promise<PreflightResult> {
	return apiFetch<PreflightResult>('/api/system/preflight', { method: 'POST' });
}

export function fixPreflight(items: string[]): Promise<PreflightResult> {
	return apiFetch<PreflightResult>('/api/system/preflight/fix', {
		method: 'POST',
		body: JSON.stringify({ fix: items }),
	});
}
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /home/upb/src/automatic-ripping-machine-ui/frontend && npx svelte-check --tsconfig ./tsconfig.json`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/upb/src/automatic-ripping-machine-ui
git add frontend/src/lib/api/system.ts
git commit -m "feat: add preflight TypeScript API types and functions"
```

---

### Task 7: Create ReadinessCheckStep wizard component

**Files:**
- Create: `frontend/src/lib/components/setup/ReadinessCheckStep.svelte` (in ARM-UI repo)

- [ ] **Step 1: Create the component**

Create `frontend/src/lib/components/setup/ReadinessCheckStep.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { runPreflight, fixPreflight, type PreflightResult, type PreflightCheck, type PreflightPath } from '$lib/api/system';
	import StatusIcon from './StatusIcon.svelte';

	let result: PreflightResult | null = $state(null);
	let loading = $state(true);
	let fixing = $state(false);
	let error = $state('');

	const SIGNUP_LINKS: Record<string, string> = {
		omdb_key: 'https://www.omdbapi.com/apikey.aspx',
		tmdb_key: 'https://www.themoviedb.org/settings/api',
		tvdb_key: 'https://thetvdb.com/api-information',
	};

	const CHECK_LABELS: Record<string, string> = {
		omdb_key: 'OMDb',
		tmdb_key: 'TMDb',
		tvdb_key: 'TVDB',
		makemkv_key: 'MakeMKV',
	};

	function checkStatus(c: PreflightCheck): 'pass' | 'warn' | 'fail' {
		if (c.success) return 'pass';
		if (c.message === 'Not configured') return 'warn';
		return 'fail';
	}

	function pathStatus(p: PreflightPath): 'pass' | 'warn' | 'fail' {
		if (!p.exists) return 'fail';
		if (!p.match) return 'fail';
		if (!p.writable) return 'fail';
		return 'pass';
	}

	function chownCommand(p: PreflightPath): string {
		const target = p.host_path || p.container_path;
		return `sudo chown -R ${p.expected_uid}:${p.expected_gid} ${target}`;
	}

	let fixableItems = $derived(
		result
			? [
					...result.checks.filter((c) => c.fixable && !c.success).map((c) => c.name),
					...result.paths.filter((p) => p.fixable && !p.match).map((p) => p.name),
				]
			: []
	);

	async function runChecks() {
		loading = true;
		error = '';
		try {
			result = await runPreflight();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Preflight check failed';
		} finally {
			loading = false;
		}
	}

	async function fixAll() {
		if (!fixableItems.length) return;
		fixing = true;
		try {
			result = await fixPreflight(fixableItems);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Fix failed';
		} finally {
			fixing = false;
		}
	}

	onMount(runChecks);
</script>

<div class="space-y-6">
	<div>
		<h2 class="text-xl font-semibold text-gray-900 dark:text-white">Readiness Check</h2>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
			Validating API keys, MakeMKV registration, and file permissions.
		</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
			<span class="ml-3 text-sm text-gray-500">Running checks...</span>
		</div>
	{:else if error}
		<div class="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
			<p class="text-sm text-red-700 dark:text-red-400">{error}</p>
		</div>
	{:else if result}
		<!-- ARM Identity -->
		<div class="rounded-lg bg-gray-50 px-4 py-3 font-mono text-sm dark:bg-gray-800">
			Running as UID <strong>{result.arm_uid}</strong> : GID <strong>{result.arm_gid}</strong>
		</div>

		<!-- API Keys -->
		<div>
			<h3 class="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">API Keys</h3>
			<div class="space-y-2">
				{#each result.checks as check}
					{@const status = checkStatus(check)}
					<div
						class="flex items-center gap-3 rounded-lg px-4 py-3 text-sm {status === 'pass'
							? 'border-l-4 border-green-500 bg-green-50 dark:bg-green-900/10'
							: status === 'warn'
								? 'border-l-4 border-amber-500 bg-amber-50 dark:bg-amber-900/10'
								: 'border-l-4 border-red-500 bg-red-50 dark:bg-red-900/10'}"
					>
						<span class="text-lg">
							{#if status === 'pass'}
								<span class="text-green-600">&#10003;</span>
							{:else if status === 'warn'}
								<span class="text-amber-600">&#9888;</span>
							{:else}
								<span class="text-red-600">&#10007;</span>
							{/if}
						</span>
						<span class="flex-1">
							<strong>{CHECK_LABELS[check.name] || check.name}</strong> - {check.message}
						</span>
						{#if SIGNUP_LINKS[check.name] && !check.success}
							<a
								href={SIGNUP_LINKS[check.name]}
								target="_blank"
								rel="noopener"
								class="text-xs text-primary hover:underline"
							>
								Get key
							</a>
						{/if}
					</div>
				{/each}
			</div>
		</div>

		<!-- Paths & Permissions -->
		<div>
			<h3 class="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Paths & Permissions</h3>
			<div class="space-y-2">
				{#each result.paths as path}
					{@const status = pathStatus(path)}
					<div
						class="rounded-lg px-4 py-3 text-sm {status === 'pass'
							? 'border-l-4 border-green-500 bg-green-50 dark:bg-green-900/10'
							: 'border-l-4 border-red-500 bg-red-50 dark:bg-red-900/10'}"
					>
						<div class="flex items-center gap-3">
							<span class="text-lg">
								{#if status === 'pass'}
									<span class="text-green-600">&#10003;</span>
								{:else}
									<span class="text-red-600">&#10007;</span>
								{/if}
							</span>
							<span class="flex-1">
								<strong>{path.name}</strong>
								{path.host_path || path.container_path}
								<span class="opacity-60">
									({path.owner_uid}:{path.owner_gid}{#if !path.match} - expected {path.expected_uid}:{path.expected_gid}{/if})
								</span>
							</span>
						</div>
						{#if status === 'fail' && !path.fixable}
							<div class="mt-2 ml-9">
								<code class="rounded bg-gray-800 px-2 py-1 text-xs text-gray-200">{chownCommand(path)}</code>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>

		<!-- Actions -->
		<div class="flex gap-3">
			<button
				type="button"
				onclick={runChecks}
				class="rounded-lg px-4 py-2 text-sm font-medium ring-1 ring-gray-300 hover:bg-gray-100 dark:ring-gray-600 dark:hover:bg-gray-800"
			>
				Re-run Checks
			</button>
			{#if fixableItems.length > 0}
				<button
					type="button"
					onclick={fixAll}
					disabled={fixing}
					class="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary-hover disabled:opacity-50"
				>
					{fixing ? 'Fixing...' : `Fix ${fixableItems.length} Issue${fixableItems.length > 1 ? 's' : ''}`}
				</button>
			{/if}
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /home/upb/src/automatic-ripping-machine-ui/frontend && npx svelte-check --tsconfig ./tsconfig.json`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/upb/src/automatic-ripping-machine-ui
git add frontend/src/lib/components/setup/ReadinessCheckStep.svelte
git commit -m "feat: add ReadinessCheckStep component for setup wizard"
```

---

### Task 8: Wire ReadinessCheckStep into SetupWizard

**Files:**
- Modify: `frontend/src/lib/components/setup/SetupWizard.svelte` (in ARM-UI repo)

- [ ] **Step 1: Add the import and step**

In `SetupWizard.svelte`, add the import after the existing imports (line 8):

```typescript
import ReadinessCheckStep from './ReadinessCheckStep.svelte';
```

Update the `steps` array (line 23-27) to insert the new step:

```typescript
const steps: SetupStep[] = [
    { id: 'welcome', label: 'Welcome', component: WelcomeStep },
    { id: 'drives', label: 'Drives', component: DriveScanStep },
    { id: 'readiness', label: 'Readiness', component: ReadinessCheckStep },
    { id: 'settings', label: 'Settings', component: SettingsReviewStep },
];
```

Add the rendering block in the step content section (after the DriveScanStep block, around line 71):

```svelte
{:else if currentStep.id === 'readiness'}
    <ReadinessCheckStep />
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /home/upb/src/automatic-ripping-machine-ui/frontend && npx svelte-check --tsconfig ./tsconfig.json`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/upb/src/automatic-ripping-machine-ui
git add frontend/src/lib/components/setup/SetupWizard.svelte
git commit -m "feat: insert ReadinessCheckStep as step 3 in setup wizard"
```

---

### Task 9: Create SystemHealth settings panel

**Files:**
- Create: `frontend/src/lib/components/settings/SystemHealth.svelte` (in ARM-UI repo)

- [ ] **Step 1: Create the component**

Create `frontend/src/lib/components/settings/SystemHealth.svelte`:

```svelte
<script lang="ts">
	import { runPreflight, fixPreflight, type PreflightResult, type PreflightCheck, type PreflightPath } from '$lib/api/system';

	let result: PreflightResult | null = $state(null);
	let loading = $state(false);
	let fixing = $state(false);
	let error = $state('');
	let expanded = $state(false);
	let lastChecked: Date | null = $state(null);

	const CHECK_LABELS: Record<string, string> = {
		omdb_key: 'OMDb',
		tmdb_key: 'TMDb',
		tvdb_key: 'TVDB',
		makemkv_key: 'MakeMKV',
	};

	let hasIssues = $derived(
		result
			? result.checks.some((c) => !c.success && c.message !== 'Not configured') ||
				result.paths.some((p) => !p.exists || !p.match || !p.writable)
			: false
	);

	let warningCount = $derived(
		result
			? result.checks.filter((c) => !c.success).length +
				result.paths.filter((p) => !p.exists || !p.match || !p.writable).length
			: 0
	);

	let passedKeys = $derived(result ? result.checks.filter((c) => c.success).length : 0);
	let passedPaths = $derived(result ? result.paths.filter((p) => p.exists && p.match && p.writable).length : 0);

	let fixableItems = $derived(
		result
			? [
					...result.checks.filter((c) => c.fixable && !c.success).map((c) => c.name),
					...result.paths.filter((p) => p.fixable && !p.match).map((p) => p.name),
				]
			: []
	);

	function timeAgo(d: Date): string {
		const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
		if (seconds < 60) return 'just now';
		if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
		return `${Math.floor(seconds / 3600)} hr ago`;
	}

	function chownCommand(p: PreflightPath): string {
		const target = p.host_path || p.container_path;
		return `sudo chown -R ${p.expected_uid}:${p.expected_gid} ${target}`;
	}

	async function runChecks() {
		loading = true;
		error = '';
		try {
			result = await runPreflight();
			lastChecked = new Date();
			expanded = hasIssues;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Check failed';
		} finally {
			loading = false;
		}
	}

	async function fixAll() {
		if (!fixableItems.length) return;
		fixing = true;
		try {
			result = await fixPreflight(fixableItems);
			lastChecked = new Date();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Fix failed';
		} finally {
			fixing = false;
		}
	}
</script>

<section class="rounded-xl border border-primary/20 bg-surface p-6 shadow-sm dark:border-primary/20 dark:bg-surface-dark">
	<div class="flex items-center justify-between">
		<h2 class="text-lg font-semibold text-gray-900 dark:text-white">System Health</h2>
		<button
			type="button"
			onclick={runChecks}
			disabled={loading}
			class="rounded-lg px-4 py-2 text-sm font-medium ring-1 ring-gray-300 hover:bg-gray-100 disabled:opacity-50 dark:ring-gray-600 dark:hover:bg-gray-800"
		>
			{loading ? 'Checking...' : 'Run Checks'}
		</button>
	</div>

	{#if error}
		<div class="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
			{error}
		</div>
	{:else if result}
		<!-- Summary bar -->
		<button
			type="button"
			onclick={() => (expanded = !expanded)}
			class="mt-4 flex w-full items-center gap-3 rounded-lg p-4 text-left text-sm {hasIssues
				? 'border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/10'
				: 'border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/10'}"
		>
			<span class="text-lg">
				{#if hasIssues}
					<span class="text-amber-600">&#9888;</span>
				{:else}
					<span class="text-green-600">&#10003;</span>
				{/if}
			</span>
			<div class="flex-1">
				<div class="font-medium">
					{#if hasIssues}{warningCount} issue{warningCount > 1 ? 's' : ''} found{:else}All checks passed{/if}
				</div>
				<div class="text-xs opacity-60">
					{passedKeys} keys valid - {passedPaths} paths writable - ARM {result.arm_uid}:{result.arm_gid}
					{#if lastChecked} - {timeAgo(lastChecked)}{/if}
				</div>
			</div>
			<span class="opacity-40">{expanded ? '\u25B2' : '\u25BC'}</span>
		</button>

		{#if expanded}
			<div class="mt-3 space-y-2">
				<!-- Failed/warning items first -->
				{#each result.checks.filter((c) => !c.success) as check}
					<div class="flex items-center gap-3 rounded-lg border-l-4 px-4 py-2 text-sm {check.message === 'Not configured'
						? 'border-amber-500 bg-amber-50 dark:bg-amber-900/10'
						: 'border-red-500 bg-red-50 dark:bg-red-900/10'}">
						<span>{check.message === 'Not configured' ? '\u26A0' : '\u2717'}</span>
						<span class="flex-1"><strong>{CHECK_LABELS[check.name] || check.name}</strong> - {check.message}</span>
					</div>
				{/each}
				{#each result.paths.filter((p) => !p.exists || !p.match || !p.writable) as path}
					<div class="space-y-1 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-2 text-sm dark:bg-red-900/10">
						<div class="flex items-center gap-3">
							<span>&#10007;</span>
							<span class="flex-1">
								<strong>{path.name}</strong>
								{path.host_path || path.container_path}
								<span class="opacity-60">({path.owner_uid}:{path.owner_gid} - expected {path.expected_uid}:{path.expected_gid})</span>
							</span>
						</div>
						{#if !path.fixable}
							<div class="ml-6">
								<code class="rounded bg-gray-800 px-2 py-1 text-xs text-gray-200">{chownCommand(path)}</code>
							</div>
						{/if}
					</div>
				{/each}

				<!-- Passing items dimmed -->
				{#if result.checks.some((c) => c.success) || result.paths.some((p) => p.exists && p.match && p.writable)}
					<div class="border-t border-gray-200 pt-2 dark:border-gray-700">
						{#each result.checks.filter((c) => c.success) as check}
							<div class="flex items-center gap-3 px-4 py-1 text-sm opacity-50">
								<span class="text-green-600">&#10003;</span>
								<span>{CHECK_LABELS[check.name] || check.name} - {check.message}</span>
							</div>
						{/each}
						{#each result.paths.filter((p) => p.exists && p.match && p.writable) as path}
							<div class="flex items-center gap-3 px-4 py-1 text-sm opacity-50">
								<span class="text-green-600">&#10003;</span>
								<span>{path.name} {path.host_path || path.container_path} ({path.owner_uid}:{path.owner_gid})</span>
							</div>
						{/each}
					</div>
				{/if}

				{#if fixableItems.length > 0}
					<div class="pt-2">
						<button
							type="button"
							onclick={fixAll}
							disabled={fixing}
							class="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary-hover disabled:opacity-50"
						>
							{fixing ? 'Fixing...' : `Fix ${fixableItems.length} Issue${fixableItems.length > 1 ? 's' : ''}`}
						</button>
					</div>
				{/if}
			</div>
		{/if}
	{:else}
		<p class="mt-4 text-sm text-gray-500 dark:text-gray-400">
			Click "Run Checks" to validate API keys, MakeMKV key, and path permissions.
		</p>
	{/if}
</section>
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /home/upb/src/automatic-ripping-machine-ui/frontend && npx svelte-check --tsconfig ./tsconfig.json`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/upb/src/automatic-ripping-machine-ui
git add frontend/src/lib/components/settings/SystemHealth.svelte
git commit -m "feat: add SystemHealth panel component for Settings page"
```

---

### Task 10: Wire SystemHealth into Settings page

**Files:**
- Modify: `frontend/src/routes/settings/+page.svelte` (in ARM-UI repo)

- [ ] **Step 1: Add import and render**

Add the import near the top of the `<script>` block in `settings/+page.svelte`:

```typescript
import SystemHealth from '$lib/components/settings/SystemHealth.svelte';
```

Render it as the first section in the template, before the existing first section (find the first `<section>` tag and add above it):

```svelte
<SystemHealth />
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /home/upb/src/automatic-ripping-machine-ui/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd /home/upb/src/automatic-ripping-machine-ui
git add frontend/src/routes/settings/+page.svelte
git commit -m "feat: add System Health panel to Settings page"
```

---

## Chunk 4: Integration Test

### Task 11: End-to-end verification

- [ ] **Step 1: Start the dev stack**

```bash
cd /home/upb/src/automatic-ripping-machine-neu
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

- [ ] **Step 2: Test preflight endpoint directly**

```bash
curl -s -X POST http://localhost:8080/api/v1/system/preflight | python3 -m json.tool
```

Verify: response contains `arm_uid`, `arm_gid`, `checks` (4 items), `paths` (5+ items with host_path populated).

- [ ] **Step 3: Test via UI proxy**

```bash
curl -s -X POST http://localhost:8888/api/system/preflight | python3 -m json.tool
```

Verify: same response shape.

- [ ] **Step 4: Test the setup wizard**

Open `http://localhost:8888/setup` (or reset `AppState.setup_complete` to False). Navigate to step 3 (Readiness). Verify:
- Loading spinner appears briefly
- API key status cards render with correct colors
- Path cards show host paths and ownership
- "Re-run Checks" button works
- "Fix" button appears for fixable items

- [ ] **Step 5: Test the Settings health panel**

Open `http://localhost:8888/settings`. Verify:
- SystemHealth section appears at top
- "Run Checks" button triggers preflight
- Results collapse/expand correctly
- Copy-able chown commands appear for failed paths
