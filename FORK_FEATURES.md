# Fork Features

A comprehensive list of features and architectural improvements in this fork that are not present in upstream automatic-ripping-machine (as of upstream main ~v2.23.x and 3.0_devel HEAD, surveyed 2026-04-25).

## Architecture & Framework

**Backend API Framework**
- FastAPI + async backend replacing the upstream Flask monolith, with non-blocking I/O across the API surface (`arm/app.py`, `arm/api/v1/*.py`)
- Standalone SQLAlchemy ORM layer with automatic table name generation; includes transparent SQLite BUSY retry with exponential backoff (`arm/database/__init__.py`)
- Schema evolution kept current via 45 Alembic revisions (upstream has 21 on the same migration framework)

**Frontend UI Framework**
- Complete rewrite from Flask+Jinja templates to Svelte 5 + SvelteKit + Vite + TypeScript modern SPA, decoupled from backend (`automatic-ripping-machine-ui/frontend/`)
- Responsive CSS Grid + Tailwind CSS design replacing Flask Bootstrap templates
- Full end-to-end TypeScript type safety on frontend API calls (`frontend/src/api/`)

**Microservices Split**
- Separate transcoding microservice (`automatic-ripping-machine-transcoder`, v17.x) with independent scaling and GPU resource allocation
- Ripper-only deployment variant: `docker-compose.ripper-only.yml` allowing headless ripping without transcoder dependency (`TRANSCODER_ENABLED` flag gates all transcoder-related surfaces)
- Shared contracts library (`automatic-ripping-machine-contracts`) with StrEnum types for job status, disc types, and preset formats; submodule-lockstep CI ensures schema compatibility across all services (`components/contracts/`)

**Type Safety & Validation**
- Pydantic v2 with ConfigDict for API request/response validation; malformed webhook payloads return 422 with structured error detail
- End-to-end type hints on SQLAlchemy models, API handlers, and ripper utilities
- Runtime TypeVar-guarded async detection preventing "asyncio.run() from running loop" crashes (`arm/services/matching/_async_compat.py`)

## User Interface & Experience

**Dashboard & Monitoring**
- Real-time WebSocket updates to dashboard job status (ripping, transcoding, finalizing phases with progress % and ETA)
- Phase-aware progress bars with distinct visual states for each ripping/transcoding stage (`arm-ui PR #195`)
- GPU and transcoder health panels showing encoder utilization, queue depth, and connection status
- Disk usage and optical drive status cached to prevent NFS stalls (`arm/services/disk_usage_cache.py`)

**Episode Matching (TV Series)**
- TVDB v4 API integration for runtime-based episode matching via IMDb ID lookup and season resolution (`arm/services/tvdb.py`, `arm/services/matching/tvdb_matcher.py`)
- Browse/Match two-tab UI with per-season episode viewer, tolerance sliders, and alternative season quick-buttons (`arm-ui TvdbMatch.svelte`)
- Auto-detect best season across multi-season discs via greedy nearest-neighbor algorithm

**Preset System (Transcoding Profiles)**
- Database-driven preset management with per-job override capability: `PresetProfile` model with `name`, `slug`, `tier_name`, `codec_profile`, `bitrate_mode` (`arm/models/config.py`)
- Snapshot preset settings at job creation time to prevent mid-pipeline configuration drift
- Preset deletion with referential integrity cleanup across pending jobs
- `shared_contracts` type validation on preset selection slugs with regex pattern enforcement (`arm_contracts.job_config.TranscodeJobConfig`)

**Real-Time Track Status**
- Tracks marked as "Ripped=Success" **during** the MakeMKV rip (not after) via FILE_ADDED message parsing (MSG 3307) (`arm/ripper/makemkv.py:928-952`)
- Live UI updates showing tracks 0-2 complete while tracks 3-5 still in progress, with final sweep to catch prefix-mismatch edge cases

**Settings & Configuration**
- FastAPI settings endpoint with live config reload and hot-patch capability (`arm/api/v1/settings.py`)
- Per-optical-drive ripping speed tuning via `MAKEMKV_READ_SPEED` config without requiring restart
- Prescan quality/performance trade-off controls: `PRESCAN_QUALITY`, `PRESCAN_MIN_FILE_SIZE`
- Setup wizard with transcoder-optional sections and preflight health checks with bumped 30s timeout (was 10s, preventing "ARM unreachable" false positives)

## Ripping & Transcoding Pipeline

**Advanced MakeMKV Integration**
- Per-drive USB buffer and speed optimization: reduce read errors and increase throughput on problematic optical drives
- MakeMKV prescan settings fine-tuned to reduce scan time while maintaining accuracy
- Robust parsing of all TINFO fields including chapters count and file size; fallback handling for malformed/missing BDMV XML playlists
- UDF filesystem stale handle detection and workaround for Blu-ray multi-layer reading edge cases

**Callback Durability & Retry**
- Webhook callback pipeline refactored to durable two-table model: `pending_callbacks` for guaranteed delivery + drainer loop for async processing (`arm-transcoder PR #105`)
- Removed inline retry logic in favor of database-backed durability; callbacks survive service restarts
- Configurable retry intervals and backoff strategy

**Naming & File Lifecycle**
- Named file override system: allow per-job custom output filenames via API endpoint (`/api/v1/jobs/{job_id}/name`)
- Filename sanitization consolidation: single `clean_for_filename()` in `arm/naming.py` handling colons, commas, quotes, hyphens with proper edge-case collapsing
- Naming-preview endpoint returning rendered filenames for all tracks before ripping starts (`/api/v1/jobs/{job_id}/naming-preview`)
- TV series disc label parsing: detect `STARGATE_ATLANTIS_S1_D2` patterns to preserve season/disc metadata in folder naming

**Transcoding Overrides**
- Job-level transcode configuration overrides: bitrate, codec, preset, output format passed via webhook payload
- Retranscode functionality: re-transcode completed jobs with new settings without re-ripping
- Transcoding skip-and-finalize option: move source file without transcoding when transcoder unavailable

## Operations & Deployment

**Multi-Server Architecture**
- ARM ripper and UI deployed to `hifi-server` (CPU/SSD optimized)
- Transcoder GPU workloads deployed to separate `transcoder-server` (NVIDIA GPU with dedicated VRAM)
- Docker Compose files for three deployment profiles: all-in-one, remote-transcoder, ripper-only
- Environment-specific image versioning with `ARM_VERSION` and `UI_VERSION` pins for reproducible deployments

**Docker & Container Improvements**
- Slimmed runtime images via a base-image refactor that pulls heavy build deps out of the runtime layer (see `base-image-refactor` memory)
- Separate `Dockerfile.dev` for development with parity enforcement (fixture-checked to prevent broken dev stacks)
- GPU-optimized images: `latest-nvidia`, `latest-amd`, `latest-intel` with provider-specific encoder probes
- Docker device pass-through for optical drives with udev rule automation and Pioneer USB stability workarounds

**Logging & Observability**
- Structured logging via `structlog` for JSON-format audit trails (vs Python logging dicts)
- Request/response logging middleware on all FastAPI endpoints
- Per-job detailed log streaming endpoint (`/api/v1/jobs/{job_id}/logs/stream`)
- Metrics export for SonarCloud and CodeQL scanning with uniform-pattern rollout deduplication

**Database & State Management**
- Automatic DB migration on container startup (Alembic `upgrade head`)
- Session pool cleanup middleware preventing connection leaks under high load (fixed `worker.py` session attachment)
- Scoped sessions on both sync (ripper) and async (FastAPI) code paths
- App state singleton (`AppState` model) tracking service health, config hot-patch flags, and scan-in-progress locks

## Reliability & Quality

**Type Safety & Testing**
- 700+ test cases across unit/integration/API tests with pytest-cov coverage reporting
- Snapshot testing for UI visual regression (Playwright snapshots in `arm-ui`)
- TypeScript strict mode enforced on all frontend code
- SonarCloud quality gates with automatic code duplication detection

**Error Handling & Recovery**
- Graceful degradation when transcoder unreachable: fallback to direct file move without transcoding
- GPU encoder probe gated on functional no-op encode (prevents false positives on broken NVIDIA drivers)
- All MakeMKV message parsing failures captured with fallback to post-rip disk scan
- Webhook handler 422 validation errors with detailed `{loc, msg, type}` feedback for callers

**Data Integrity**
- Track count now excludes disabled tracks (fixes UI discrepancy in `arm-ui PR #193`)
- Data disc duplicate detection prevents silent overwrites of same-label rips
- Database locking no longer triggers setup wizard flash on startup
- DVD unmount on error preventing subsequent MakeMKV access failures

**Code Quality**
- Pydantic v2 ConfigDict migration complete (no deprecated `class Config:` patterns)
- ReDoS-safe regex patterns for FPS parsing and progress tracking
- Uniform test helper functions: `patched_app_client` for webhook mocking, `sample_job` factory with realistic config

## Bug Fixes Still Open Upstream

The following 14 issues are fixed in the fork and remain open in upstream (`automatic-ripping-machine/automatic-ripping-machine`):

| Issue | Title | Fork Commit(s) |
|-------|-------|---|
| [#1281](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1281) | Filename error moving file after transcode | `c1f6caa`, `2623b11` |
| [#1345](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1345) | `fatal: invalid object name 'origin/HEAD'` | `edac6d2`, `e3d0e03` |
| [#1355](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1355) | Comma in filename breaks file move | `c1f6caa`, `2623b11` |
| [#1430](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1430) | OMDb "Too many results" for short queries | `9a87349`, `ed39afc`, `d939362` |
| [#1457](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1457) | Single quote in disc name breaks transcoding | `4f32270` |
| [#1526](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1526) | abcde I/O error not detected (zero exit) | `abc4f68`, `830a743` |
| [#1584](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1584) | NOT NULL on system_drives.name at startup | `2e63381`, `d939362` |
| [#1628](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1628) | ffprobe failure crashes HandBrake transcode | `96697d1`, `c10d917` |
| [#1641](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1641) | calc_process_time fails on >24h jobs | `78ab2e9`, `40bf39f` |
| [#1650](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1650) | Malformed BDMV XML crashes identification | `efa139d`, `ac33272` |
| [#1651](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1651) | Data disc same label silently overwrites | `500e89d`, `830a743` |
| [#1664](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1664) | DVD stays mounted → MakeMKV can't access drive | `ac33272`, `d939362` |
| [#1684](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1684) | Settings values not trimmed on save | `edac6d2` |
| [#1688](https://github.com/automatic-ripping-machine/automatic-ripping-machine/issues/1688) | Unparsed MakeMKV lines cause fatal error | `7297893` |

---

**Notes on upstream state (surveyed 2026-04-25):**
- Upstream `main` is on the v2.x line (~v2.23.x) with the original Flask + Jinja monolith.
- Upstream `3.0_devel` is partway toward a service split (separate `Dockerfile-Ripper` and `Dockerfile-UI`) but still in-progress; this fork's split-and-shared-contracts model is well past that point.
- Upstream has an `arm-vuejs` branch (last touched 2025-10) but it is not on the v2 release line and has not been merged. This fork's Svelte 5 + Vite + TypeScript SPA is independent of that effort.
