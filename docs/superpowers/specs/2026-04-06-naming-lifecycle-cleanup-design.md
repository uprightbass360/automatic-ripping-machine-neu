# Naming Lifecycle Cleanup - Design Spec

**Date:** 2026-04-06
**Branch:** TBD (feature/naming-lifecycle-cleanup)
**Status:** Draft

## Problem

`job.title` is a single field serving three conflicting roles:

1. **Display** (UI, logs, notifications) - wants human-readable text
2. **Metadata search** (OMDb/TMDB queries) - wants clean text without filesystem artifacts
3. **Filesystem paths** (raw rip directories) - wants sanitized, OS-safe characters

Different identification paths apply different sanitization before storing `job.title`:

- `identify_bluray`: light sanitization (only strips OS-illegal chars, PR #186)
- `update_job` metadata match: aggressive `utils.clean_for_filename` (spaces to hyphens, strips brackets)
- `_apply_label_as_title`: light (underscores to spaces, title-case)

Three separate `clean_for_filename` implementations exist with different behavior:

| Location | Behavior |
|----------|----------|
| `arm/ripper/utils.py:928` | Aggressive - spaces to hyphens, strips brackets, collapses hyphens |
| `arm/ripper/naming.py:84` | Conservative - preserves spaces/parens, prevents traversal |
| `arm/api/v1/jobs.py:992` | API variant - preserves spaces, no traversal protection |

**User-reported symptom:** Blu-ray XML title `Dynasties - Disc 2` was stored as `Dynasties-Disc-2`, causing 8+ wasted OMDb API calls before the fallback loop stripped enough hyphens to find the real title.

## Solution Overview

1. **GUID-based work paths** - raw/work directories use job GUID, not title. Eliminates filesystem dependency on title quality entirely.
2. **Clean title storage** - stop sanitizing titles at store time. Store human-readable text for display and search.
3. **Single sanitization function** - consolidate three implementations into one public `naming.clean_for_filename`.
4. **Structured disc metadata** - `disc_number`/`disc_total` as DB columns instead of embedded in title strings.
5. **Deferred naming** - human-readable names produced only at final placement, via the naming engine.
6. **DB-based file correlation** - all file-to-record lookups go through DB (job_id/guid/track_number), never by parsing directory or file names.

## Design

### 1. GUID-based work paths

#### New column

`job.guid` - String(36), UUID4, non-nullable, unique. Set in `Job.__init__` at job creation time.

```python
import uuid

class Job(db.Model):
    guid = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
```

Tracks do not need GUIDs. They are always looked up by `job_id` + `track_number`, and MakeMKV output files are correlated to tracks via track number, not filename.

#### build_raw_path

```python
def build_raw_path(self):
    """Raw rip directory path. Uses GUID for uniqueness."""
    return os.path.join(str(self.config.RAW_PATH), str(self.guid))
```

No dependency on any title field. GUID guarantees uniqueness - no collision handling needed.

#### setup_rawpath

Simplified to just create the directory. The entire collision/timestamp branch is removed.

```python
def setup_rawpath(job, raw_path):
    """Create the raw rip output directory."""
    logging.info(f"Destination is {raw_path}")
    os.makedirs(raw_path, exist_ok=True)
    return raw_path
```

#### File-to-record correlation

Any code that currently identifies files by matching against title-based directory names must switch to DB lookups:

- **Raw directory lookup:** Use `job.guid` to find the directory, or query `Job.raw_path` (absolute path stored in DB after rip starts).
- **Track file matching:** Use `track.track_number` and `track.filename` (MakeMKV's original filename like `B1_t00.mkv`), never parse the containing directory name.
- **Transcoder input:** Webhook includes `path` (GUID basename) and per-track `filename` values - transcoder matches files by filename within the GUID directory.

Files to audit for path-based lookups:
- `arm/ripper/makemkv.py` - `_scan_output_dir`, any post-rip file reconciliation
- `arm/ripper/utils.py` - `move_files`, `transcoder_notify` raw_basename extraction
- `arm/ripper/arm_ripper.py` - post-rip file handling
- `arm/ripper/folder_ripper.py` - folder import file handling
- `arm/api/v1/jobs.py` - any endpoint that resolves files from job metadata

### 2. Clean title storage

Remove all sanitization at title-store time. The only cleanup when setting `job.title` is stripping characters that are truly illegal (null bytes) or would break logging/DB queries.

#### Changes by identification path

| Location | Current | After |
|----------|---------|-------|
| `identify.py:547` (`update_job`) | `utils.clean_for_filename(best.title)` | Store `best.title` directly |
| `identify.py:434` (`identify_bluray`) | Light regex `[/\\<>"\|?*\x00]` | Keep as-is (already correct) |
| `identify.py:312` (`_apply_label_as_title`) | Replace `_` with space, `.title()` | Keep as-is |
| `jobs.py:423` (manual title edit API) | `_clean_for_filename(value)` | Store user input directly (strip only null bytes/control chars) |
| `jobs.py:455` (`_re_render_title`) | Writes `render_title()` output back to `title` + `title_manual` | Keep as-is - this is the naming engine producing a display value, not filesystem sanitization |
| `jobs.py:560` (track title edit API) | `_clean_for_filename(value)` | Store user input directly |
| `music_brainz.py:378-379` | Stores `artist + " " + title` | Keep as-is (already clean) |
| `folder.py:103` (folder import) | Stores user-provided title | Keep as-is |

#### Rationale

- Metadata API results (OMDb, TMDB) are already clean human-readable text
- User input via API should be stored as-provided (naming engine handles filesystem safety at render time)
- Disc labels need only light cleanup (underscores, case normalization)
- Blu-ray XML needs only OS-illegal char removal

### 3. Single clean_for_filename

#### Keep and make public

`naming.py:_clean_for_filename` becomes `naming.clean_for_filename` (drop the underscore).

This is the single authoritative sanitization function for filesystem output. It:
- Replaces colons with ` - `
- Normalizes whitespace
- Replaces `&` with `and`
- Replaces backslashes with ` - `
- Removes non-word characters except `. ()-`
- Prevents path traversal (`..` collapsed)
- Strips leading/trailing dots and spaces

#### Delete

- `arm/ripper/utils.py:928-938` `clean_for_filename` - aggressive version, all callsites removed
- `arm/api/v1/jobs.py:992-1000` `_clean_for_filename` - API variant, callsites no longer sanitize at store time

#### Remaining callsites after consolidation

All internal to the naming engine (called at render time, not store time):
- `naming.render_folder` - sanitizes each path segment
- `naming.render_track_title` - sanitizes custom filenames
- `naming.render_track_folder` - sanitizes each path segment
- `utils._build_webhook_payload` - sanitizes rendered title for webhook

#### music_brainz.py:375

```python
clean_title = u.clean_for_filename(artist) + "-" + u.clean_for_filename(title)
```

This return value is used as `job.label` in `job.py:258`. Switch to:

```python
clean_title = f"{artist} {title}"
```

The label is a display/identification value, not a filesystem path. No sanitization needed.

### 4. Structured disc metadata

#### New columns

```python
disc_number = db.Column(db.Integer, nullable=True)    # e.g. 2 for "Disc 2"
disc_total = db.Column(db.Integer, nullable=True)      # e.g. 3 for a 3-disc set
```

#### Extraction

During identification, parse disc number from:
- Blu-ray XML title: `"Dynasties - Disc 2"` -> `title="Dynasties"`, `disc_number=2`
- DVD label: `"DYNASTIES_DISC_2"` -> same
- Regex patterns to detect (case-insensitive, applied in order):
  - `[- ]+Disc\s+(\d+)` - "Dynasties - Disc 2"
  - `[- ]+Disk\s+(\d+)` - "Dynasties - Disk 2"
  - `[_-]+D(\d+)$` - "DYNASTIES_D2" (label format)
  - `[- ]+Part\s+(\d+)` - "Dynasties - Part 2"

The matched suffix is stripped from the title. The captured group becomes `disc_number`. If no pattern matches, `disc_number` stays NULL and the title is stored as-is.

#### Naming pattern variable

Available as `{disc_number}` and `{disc_total}` in naming patterns:
- `{title} - Disc {disc_number}` -> `"Dynasties - Disc 2"`
- `{title} ({year})` -> `"Dynasties (2018)"` (disc number omitted if not in pattern)

Add corresponding `_auto` / `_manual` columns for consistency with the existing field pattern:
- `disc_number_auto`, `disc_number_manual`
- `disc_total_auto`, `disc_total_manual`

### 5. Deferred naming - three paths

Human-readable output names are produced at exactly one moment, depending on the pipeline:

#### Path A: Transcoder enabled (current default)

1. Rip completes -> files in `{RAW_PATH}/{guid}/`
2. ARM builds webhook payload with pre-rendered names from naming engine (`render_folder`, `render_title`, `render_all_tracks`)
3. Transcoder receives payload, transcodes files, places output at rendered paths
4. No change to this flow - naming engine already handles it

#### Path B: Transcoder disabled

1. Rip completes -> files in `{RAW_PATH}/{guid}/`
2. New function `finalize_output(job)`:
   - Renders final folder/file names via naming engine
   - Moves files from GUID work directory to `{COMPLETED_PATH}/{rendered_folder}/{rendered_title}.mkv`
   - Handles per-track naming for multi-title discs
   - Updates `job.path` to final location
   - Cleans up empty GUID work directory
3. Called from `arm_ripper.rip_visual_media` when `SKIP_TRANSCODE=true` or `TRANSCODER_URL` not configured

#### Path C: Music rip

1. abcde handles rip + encoding + output naming via its own config (`OUTPUTDIR`)
2. No change - music pipeline is independent of the video naming engine

### 6. Webhook contract

#### Changes

| Field | Before | After | Breaking? |
|-------|--------|-------|-----------|
| `path` | Title-based basename (e.g. `"Dynasties-Disc-2"`) | GUID basename (e.g. `"a1b2c3d4-..."`) | Yes - transcoder must use this as opaque directory name (it already does) |
| All other fields | Unchanged | Unchanged | No |

The transcoder already treats `path` as an opaque string - it concatenates `{input_base}/{path}/` to find MKV files. The switch from title-based to GUID-based should be transparent.

**Coordinated release required:** Transcoder must accept GUID-format `path` values. Since it doesn't parse the path, this should be a no-op, but verify with integration test.

### 7. Database migration

Single Alembic migration:

```python
# New columns
op.add_column('job', sa.Column('guid', sa.String(36), nullable=True, unique=True))
op.add_column('job', sa.Column('disc_number', sa.Integer(), nullable=True))
op.add_column('job', sa.Column('disc_number_auto', sa.Integer(), nullable=True))
op.add_column('job', sa.Column('disc_number_manual', sa.Integer(), nullable=True))
op.add_column('job', sa.Column('disc_total', sa.Integer(), nullable=True))
op.add_column('job', sa.Column('disc_total_auto', sa.Integer(), nullable=True))
op.add_column('job', sa.Column('disc_total_manual', sa.Integer(), nullable=True))

# Backfill existing rows with generated UUIDs
for row in conn.execute(sa.text("SELECT job_id FROM job WHERE guid IS NULL")):
    conn.execute(
        sa.text("UPDATE job SET guid = :guid WHERE job_id = :id"),
        {"guid": str(uuid.uuid4()), "id": row.job_id},
    )

# Make guid non-nullable after backfill
op.alter_column('job', 'guid', nullable=False)
```

Existing `raw_path` values in the DB are absolute paths, so old jobs continue to work - they don't depend on `build_raw_path()` after the raw path is persisted.

### 8. Test changes

| Action | Files | Details |
|--------|-------|---------|
| Delete | `test_utils.py:TestCleanForFilename` | 8 tests for removed `utils.clean_for_filename` |
| Rewrite | `test_job_model.py` build_raw_path tests | Assert GUID-based paths instead of title-based |
| Rewrite | `test_makemkv_coverage.py` setup_rawpath tests | No collision branch, just directory creation |
| Update | `test_music_rip.py` | Assertions on `music_brainz.main()` return value format |
| Add | New test file or section | `disc_number` extraction from XML titles and labels |
| Add | New test file or section | `finalize_output` for transcoder-disabled path |
| Add | New test file or section | GUID generation and uniqueness on Job creation |
| Keep | `test_naming.py` | Naming engine unchanged except function visibility (private to public) |
| Update | `conftest.py`, `test_pipeline.py` | Fixtures gain `guid` field |

### 9. Files changed (complete inventory)

| File | Changes |
|------|---------|
| `arm/models/job.py` | Add `guid`, `disc_number`, `disc_total` columns + `_auto`/`_manual` variants. Rewrite `build_raw_path` to use GUID. Update `__init__` to generate GUID. |
| `arm/ripper/identify.py` | Remove `utils.clean_for_filename` call in `update_job` (line 547). Add disc_number extraction logic. |
| `arm/ripper/naming.py` | Make `_clean_for_filename` public. Add `disc_number`, `disc_total` to `_build_variables`. Add `finalize_output` function. |
| `arm/ripper/utils.py` | Delete `clean_for_filename` function. Update `_build_webhook_payload` (path field now GUID). |
| `arm/ripper/makemkv.py` | Simplify `setup_rawpath` (remove collision branch). |
| `arm/ripper/arm_ripper.py` | Call `finalize_output` when transcoder is disabled. |
| `arm/ripper/music_brainz.py` | Remove `clean_for_filename` usage in return value. |
| `arm/ripper/folder_ripper.py` | Update for GUID paths. Call `finalize_output` when transcoder is disabled. |
| `arm/api/v1/jobs.py` | Remove `_clean_for_filename` function and its callsites (lines 423, 560, 992-1000). Add `disc_number`/`disc_total` to title edit endpoint field map. |
| `arm/api/v1/folder.py` | Accept `disc_number`/`disc_total` in folder import. |
| `arm/migrations/versions/` | New migration for `guid`, `disc_number`, `disc_total` columns. |
| Tests (multiple) | See Section 8. |

### 10. Out of scope

- Renaming existing raw directories on disk (old jobs use stored absolute `raw_path`)
- Changing MakeMKV's internal file naming (`B1_t00.mkv` etc.)
- Changing the music rip pipeline (abcde manages its own output)
- Changing the naming pattern syntax or config format
- Modifying the transcoder's internal logic (it already treats paths as opaque)
