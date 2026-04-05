# Setup Wizard Readiness Check + Settings Health Panel

## Goal

Help first-time users reach a working state by validating API keys, MakeMKV registration, and path permissions before the first rip. Surface the same checks as an always-accessible health panel in Settings.

## Context

A first-time user deploying published images hit multiple issues that could have been caught at setup time: missing TVDB key, transcoder work dir owned by root (UID mismatch), and no feedback about what was wrong until reading container logs. The existing setup wizard (Welcome, Drives, Settings Review) skips over these validations.

## Architecture

### Backend (ARM-neu)

One new endpoint, one extended endpoint, one new service function.

#### `POST /api/v1/system/preflight`

Unified check that validates all keys and paths in one call. Returns a consistent shape the UI can render directly.

Response:

```json
{
  "arm_uid": 1000,
  "arm_gid": 1000,
  "checks": [
    { "name": "omdb_key",    "success": true,  "message": "OMDb API key is valid",          "fixable": false },
    { "name": "tmdb_key",    "success": false, "message": "Not configured",                 "fixable": false },
    { "name": "tvdb_key",    "success": false, "message": "TVDB login failed: unauthorized", "fixable": false },
    { "name": "makemkv_key", "success": true,  "message": "MakeMKV key is valid",           "fixable": true  }
  ],
  "paths": [
    {
      "name": "RAW_PATH",
      "container_path": "/home/arm/media/raw",
      "host_path": "/home/arm/media/raw",
      "exists": true,
      "writable": true,
      "owner_uid": 1000,
      "owner_gid": 1000,
      "expected_uid": 1000,
      "expected_gid": 1000,
      "match": true,
      "fixable": false
    }
  ]
}
```

Field notes:
- `checks[].name` is a stable key the UI can use for icons and labels.
- `checks[].fixable` indicates whether `POST /system/preflight/fix` can resolve it (see below).
- `paths[].host_path` is resolved from `/proc/self/mountinfo` (bind-mounts) or falls back to env vars (`ARM_MEDIA_PATH`, `ARM_CONFIG_PATH`, etc.) passed via docker-compose. For named Docker volumes, shows the volume name.
- `paths[].fixable` is true when ARM can chown the path from inside the container.
- Unconfigured keys return `success: false` with message "Not configured" - these render as amber warnings, not red errors.
- Each metadata key check only runs if a value is configured. Empty keys skip the API call.

#### `POST /api/v1/system/preflight/fix`

Attempts to fix issues ARM can resolve from inside the container.

Request:

```json
{ "fix": ["makemkv_key", "TRANSCODE_PATH"] }
```

Response: same shape as preflight (re-runs all checks after fixes).

Fixable items:
- `makemkv_key` - calls existing `prep_mkv()` to fetch the current beta key.
- Any path where ARM has ownership of the parent - runs `chown arm:arm <path>`.
- Non-fixable items in the request array are silently skipped.

#### TVDB key validation

New function in `arm/services/tvdb.py`:

```python
async def test_tvdb_key(api_key: str) -> dict:
    """Test a TVDB API key by attempting login. Returns {success, message}."""
```

Calls the existing `POST /v4/login` endpoint with the provided key. Returns success/failure with a human-readable message. The preflight endpoint calls this when `TVDB_API_KEY` is configured.

#### Host path resolution

New utility function in `arm/services/` (or `arm/api/v1/system.py` inline):

```python
def resolve_host_path(container_path: str) -> str | None:
    """Resolve a container path to its host bind-mount source.

    Parses /proc/self/mountinfo to find the host path for bind-mounts.
    Falls back to known env var mappings (ARM_MEDIA_PATH, etc.).
    Returns None for named Docker volumes (no meaningful host path).
    """
```

Env var fallback mapping:
- `/home/arm/media` -> `ARM_MEDIA_PATH` (already in compose env)
- `/etc/arm/config` -> `ARM_CONFIG_PATH` (needs to be added to compose env)
- `/home/arm/logs` -> `ARM_LOGS_PATH` (needs to be added to compose env)
- `/home/arm/music` -> `ARM_MUSIC_PATH` (needs to be added to compose env)

The compose file needs to pass these as env vars so the fallback works:
```yaml
- ARM_MEDIA_PATH=${ARM_MEDIA_PATH}
- ARM_CONFIG_PATH=${ARM_CONFIG_PATH}
- ARM_LOGS_PATH=${ARM_LOGS_PATH}
- ARM_MUSIC_PATH=${ARM_MUSIC_PATH}
```

### Frontend (ARM-UI)

#### Wizard Step: ReadinessCheck (new)

New component: `frontend/src/lib/components/setup/ReadinessCheckStep.svelte`

Inserted as step 3 of 4 (Welcome, Drives, **Readiness Check**, Settings Review).

Behavior:
- On mount, calls `POST /api/system/preflight` (proxied through UI backend).
- Shows loading spinner during check.
- Renders results in three sections: ARM Identity, API Keys, Paths & Permissions.
- Each result row is green (pass), amber (not configured / warning), or red (failed / mismatch).
- Red path rows show the exact `chown` command if not fixable, or a "Fix" button if fixable.
- Amber API key rows show an inline input field + "Test" button + link to the provider's signup page.
- "Re-run Checks" button re-calls preflight.
- "Fix All" button appears when any items are fixable - calls `POST /system/preflight/fix` with all fixable items, then re-runs checks.
- "Next" button is always enabled - warnings and errors do not block setup completion.

Signup links:
- OMDb: `https://www.omdbapi.com/apikey.aspx`
- TMDb: `https://www.themoviedb.org/settings/api`
- TVDB: `https://thetvdb.com/api-information`

#### Settings Health Panel (new)

New component: `frontend/src/lib/components/settings/SystemHealth.svelte`

Added as the first section on the Settings page, above Metadata.

Behavior:
- **Not auto-run on page load.** Shows a "Run Checks" button in a neutral card.
- After clicking, calls preflight and renders results.
- **Collapsed when all pass:** single green summary line: "All checks passed - 4 keys valid, 5 paths writable, ARM running as 1000:1000 - Last checked 2 min ago". Expand arrow to see details.
- **Auto-expanded when issues found:** problems at top (amber/red), passing checks dimmed below.
- Failed path rows show host path + container path + owner UID:GID + expected UID:GID.
- Failed path rows show copy-able `chown` command for host-level fixes, "Fix" button for container-fixable issues.
- Failed/missing API key rows show inline input + "Test" button + signup link.
- MakeMKV key failure shows "Update Key" button (calls preflight/fix).
- "Fix All" button when fixable items exist.

#### UI Backend Proxy

New route in `backend/routers/system.py` (or existing settings router):
- `POST /api/system/preflight` -> proxies to `http://arm-rippers:8080/api/v1/system/preflight`
- `POST /api/system/preflight/fix` -> proxies to `http://arm-rippers:8080/api/v1/system/preflight/fix`

#### API Key Inline Editing

When a user enters a key in the health panel's inline input and clicks "Test":
1. Call `GET /api/settings/test-metadata?key=<value>&provider=<provider>` (existing) for OMDB/TMDB.
2. For TVDB, call the new test endpoint via preflight or a dedicated route.
3. On success, save the key to config via `PUT /api/settings/arm` (existing).
4. Re-run preflight to refresh all statuses.

This reuses existing endpoints - no new config persistence logic needed.

## Graceful Degradation

- **Transcoder offline/absent:** Preflight does not probe the transcoder. Transcoder-related paths (TRANSCODE_PATH) are checked for local writability only. No transcoder-specific checks in the health panel. If transcoder becomes optional in the future, these path checks simply become irrelevant.
- **DB not initialized:** Preflight works before the DB exists (key checks use arm.yaml, path checks use filesystem). MakeMKV key check writes to AppState but gracefully handles missing table.
- **Network unreachable:** API key checks return `"Cannot connect to API"` messages, not exceptions. The UI shows these as red failures with a retry button.

## Files Changed

### ARM-neu (automatic-ripping-machine-neu)

| Action | File | Change |
|--------|------|--------|
| New | `arm/api/v1/system.py` | Add `preflight` and `preflight/fix` endpoints |
| New | `arm/services/preflight.py` | Preflight check orchestration, host path resolution |
| Modify | `arm/services/tvdb.py` | Add `test_tvdb_key()` function |
| Modify | `docker-compose.yml` | Pass `ARM_MEDIA_PATH`, `ARM_CONFIG_PATH`, `ARM_LOGS_PATH`, `ARM_MUSIC_PATH` as env vars to arm-rippers |

### ARM-UI (automatic-ripping-machine-ui)

| Action | File | Change |
|--------|------|--------|
| New | `frontend/src/lib/components/setup/ReadinessCheckStep.svelte` | Wizard step component |
| Modify | `frontend/src/lib/components/setup/SetupWizard.svelte` | Add step 3, update step count |
| New | `frontend/src/lib/components/settings/SystemHealth.svelte` | Health panel component |
| Modify | `frontend/src/routes/settings/+page.svelte` | Import and render SystemHealth at top |
| Modify | `frontend/src/lib/api/system.ts` | Add `runPreflight()` and `fixPreflight()` API calls |
| Modify | `backend/routers/system.py` | Add preflight proxy routes |

## Testing

### Backend
- Unit test `preflight.py`: mock key checks and path stats, verify response shape.
- Unit test `test_tvdb_key()`: mock httpx to simulate login success, 401, timeout.
- Unit test `resolve_host_path()`: mock `/proc/self/mountinfo` parsing, env var fallback.
- Unit test fix endpoint: mock chown calls, verify re-check after fix.

### Frontend
- Component test `ReadinessCheckStep`: mock preflight response, verify green/amber/red rendering.
- Component test `SystemHealth`: mock preflight, verify collapsed/expanded states.
- Test inline key input: mock test-metadata call, verify save-on-success flow.
