# Naming Lifecycle Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace title-based work paths with GUID-based paths, consolidate three `clean_for_filename` implementations into one, stop sanitizing titles at storage time, and add a `finalize_output` path for transcoder-disabled deployments.

**Architecture:** Job gets a `guid` column (UUID4) set at creation. Raw/work directories use `{RAW_PATH}/{guid}/` instead of title-based names. All filesystem sanitization happens at render time via the naming engine's single `clean_for_filename`. A new `finalize_output()` function handles file placement when the transcoder is disabled.

**Tech Stack:** Python 3.11, SQLAlchemy/Alembic, pytest, Flask-SQLAlchemy

**Spec:** `docs/superpowers/specs/2026-04-06-naming-lifecycle-cleanup-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `arm/models/job.py` | Modify | Add `guid` column, rewrite `build_raw_path` to use GUID |
| `arm/ripper/naming.py` | Modify | Make `_clean_for_filename` public, add `disc_number`/`disc_total` to `_build_variables`, add `finalize_output()` |
| `arm/ripper/identify.py` | Modify | Remove `utils.clean_for_filename` call in `update_job` |
| `arm/ripper/utils.py` | Modify | Delete `clean_for_filename`, update `_build_webhook_payload` import |
| `arm/ripper/makemkv.py` | Modify | Simplify `setup_rawpath` (remove collision branch) |
| `arm/ripper/arm_ripper.py` | Modify | Call `finalize_output` when transcoder disabled |
| `arm/ripper/folder_ripper.py` | Modify | Call `finalize_output` when transcoder disabled |
| `arm/ripper/music_brainz.py` | Modify | Remove `utils.clean_for_filename` usage |
| `arm/api/v1/jobs.py` | Modify | Remove `_clean_for_filename` function and callsites, add `disc_number`/`disc_total` to `_FIELD_MAP` |
| `arm/migrations/versions/l7m8n9o0p1q2_job_add_guid.py` | Create | Migration to add `guid` column |
| `test/test_job_model.py` | Modify | Rewrite `build_raw_path` tests for GUID paths |
| `test/test_naming.py` | Modify | Update imports for public `clean_for_filename` |
| `test/test_utils.py` | Modify | Remove `TestCleanForFilename` class |
| `test/test_makemkv_coverage.py` | Modify | Rewrite `TestSetupRawpath` for simplified function |
| `test/test_finalize_output.py` | Create | Tests for new `finalize_output()` function |
| `test/test_identify_no_sanitize.py` | Create | Tests verifying titles stored without aggressive sanitization |

---

### Task 1: Add `guid` column to Job model + migration

**Files:**
- Modify: `arm/models/job.py:113-169` (column definitions), `arm/models/job.py:172-189` (`__init__`), `arm/models/job.py:191-205` (`from_folder`)
- Create: `arm/migrations/versions/l7m8n9o0p1q2_job_add_guid.py`
- Modify: `test/conftest.py:100-149` (sample_job fixture)
- Modify: `test/test_job_model.py`

- [ ] **Step 1: Write failing test for GUID on new job**

Add to `test/test_job_model.py`:

```python
import uuid


class TestJobGuid:
    def test_new_job_has_guid(self, sample_job):
        """Every job gets a UUID4 guid at creation."""
        assert sample_job.guid is not None
        # Validate it's a proper UUID4
        parsed = uuid.UUID(sample_job.guid)
        assert parsed.version == 4

    def test_guid_is_unique_per_job(self, app_context):
        """Two jobs get different GUIDs."""
        from arm.models.job import Job
        import unittest.mock
        with unittest.mock.patch.object(Job, 'parse_udev'), \
             unittest.mock.patch.object(Job, 'get_pid'):
            job1 = Job('/dev/sr0')
            job2 = Job('/dev/sr1')
        assert job1.guid != job2.guid

    def test_folder_job_has_guid(self, app_context):
        """Folder-import jobs also get GUIDs."""
        from arm.models.job import Job
        job = Job.from_folder('/tmp/test', 'dvd')
        assert job.guid is not None
        parsed = uuid.UUID(job.guid)
        assert parsed.version == 4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test/test_job_model.py::TestJobGuid -v
```

Expected: FAIL - `AttributeError: guid`

- [ ] **Step 3: Add guid column to Job model**

In `arm/models/job.py`, add import at top:

```python
import uuid
```

Add column after line 155 (`tvdb_id`):

```python
    guid = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
```

In `__init__` (line 172), add after `self.devpath = devpath`:

```python
        self.guid = str(uuid.uuid4())
```

In `from_folder` (line 191), the `guid` is auto-set by `__init__` via `cls(devpath=None, ...)` - no change needed.

- [ ] **Step 4: Update sample_job fixture**

In `test/conftest.py`, the fixture creates a Job via `Job('/dev/sr0')` which will now auto-generate a guid. No change needed for the fixture itself since `__init__` handles it. But verify it works.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest test/test_job_model.py::TestJobGuid -v
```

Expected: PASS

- [ ] **Step 6: Create Alembic migration**

Create `arm/migrations/versions/l7m8n9o0p1q2_job_add_guid.py`:

```python
"""job: add guid column for GUID-based work paths

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-04-06

"""
import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l7m8n9o0p1q2'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade():
    # Add as nullable first so we can backfill
    with op.batch_alter_table('job') as batch_op:
        batch_op.add_column(sa.Column('guid', sa.String(36), nullable=True))

    # Backfill existing rows with generated UUIDs
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT job_id FROM job WHERE guid IS NULL"))
    for row in rows:
        conn.execute(
            sa.text("UPDATE job SET guid = :guid WHERE job_id = :id"),
            {"guid": str(uuid.uuid4()), "id": row[0]},
        )

    # Make non-nullable and add unique constraint
    with op.batch_alter_table('job') as batch_op:
        batch_op.alter_column('guid', nullable=False)
        batch_op.create_unique_constraint('uq_job_guid', ['guid'])


def downgrade():
    with op.batch_alter_table('job') as batch_op:
        batch_op.drop_constraint('uq_job_guid', type_='unique')
        batch_op.drop_column('guid')
```

- [ ] **Step 7: Run full test suite to check nothing breaks**

```bash
pytest test/ -v
```

Expected: All existing tests PASS, new TestJobGuid PASS.

- [ ] **Step 8: Commit**

```bash
git add arm/models/job.py arm/migrations/versions/l7m8n9o0p1q2_job_add_guid.py test/test_job_model.py
git commit -m "feat: add guid column to Job model for GUID-based work paths"
```

---

### Task 2: Rewrite `build_raw_path` to use GUID

**Files:**
- Modify: `arm/models/job.py:453-457` (`build_raw_path`)
- Modify: `test/test_job_model.py:42-70` (`TestBuildPaths`)

- [ ] **Step 1: Update existing build_raw_path tests**

In `test/test_job_model.py`, rewrite `TestBuildPaths`:

```python
class TestBuildPaths:
    def test_build_raw_path_uses_guid(self, sample_job):
        """Raw path uses job GUID, not title."""
        expected = f"/home/arm/media/raw/{sample_job.guid}"
        assert sample_job.build_raw_path() == expected

    def test_build_raw_path_independent_of_title(self, sample_job):
        """Changing title does not affect raw path."""
        path_before = sample_job.build_raw_path()
        sample_job.title = "Something Else"
        sample_job.title_auto = "Something Else"
        assert sample_job.build_raw_path() == path_before

    def test_build_raw_path_independent_of_manual_title(self, sample_job):
        """Manual title correction does not affect raw path."""
        path_before = sample_job.build_raw_path()
        sample_job.title_manual = "Serial Mom"
        assert sample_job.build_raw_path() == path_before

    def test_build_transcode_path(self, sample_job):
        assert sample_job.build_transcode_path() == "/home/arm/media/transcode/movies/SERIAL_MOM (1994)"

    def test_build_final_path(self, sample_job):
        assert sample_job.build_final_path() == "/home/arm/media/completed/movies/SERIAL_MOM (1994)"

    def test_build_paths_with_manual_title(self, sample_job):
        sample_job.title_manual = "Serial Mom"
        # raw_path uses GUID (independent of title)
        assert sample_job.build_raw_path() == f"/home/arm/media/raw/{sample_job.guid}"
        # transcode and final use formatted_title (prefers manual)
        assert sample_job.build_transcode_path() == "/home/arm/media/transcode/movies/Serial Mom (1994)"
        assert sample_job.build_final_path() == "/home/arm/media/completed/movies/Serial Mom (1994)"

    def test_build_paths_series(self, sample_job):
        sample_job.video_type = "series"
        assert sample_job.build_transcode_path() == "/home/arm/media/transcode/tv/SERIAL_MOM (1994)"
        assert sample_job.build_final_path() == "/home/arm/media/completed/tv/SERIAL_MOM (1994)"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test/test_job_model.py::TestBuildPaths -v
```

Expected: FAIL - `build_raw_path` still returns title-based path.

- [ ] **Step 3: Rewrite build_raw_path**

In `arm/models/job.py`, replace `build_raw_path` (lines 453-457):

```python
    def build_raw_path(self):
        """Compute the raw rip directory path. Uses GUID for uniqueness -
        no dependency on title fields, no collision handling needed."""
        return os.path.join(str(self.config.RAW_PATH), str(self.guid))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test/test_job_model.py::TestBuildPaths -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest test/ -v
```

Expected: Some tests may need updating if they assert specific raw path formats. Fix any failures.

- [ ] **Step 6: Commit**

```bash
git add arm/models/job.py test/test_job_model.py
git commit -m "feat: build_raw_path uses GUID instead of title"
```

---

### Task 3: Simplify `setup_rawpath` (remove collision branch)

**Files:**
- Modify: `arm/ripper/makemkv.py:1234-1263` (`setup_rawpath`)
- Modify: `test/test_makemkv_coverage.py:438-464` (`TestSetupRawpath`)

- [ ] **Step 1: Rewrite setup_rawpath tests**

In `test/test_makemkv_coverage.py`, replace `TestSetupRawpath`:

```python
class TestSetupRawpath:
    """Test setup_rawpath() directory creation with GUID-based paths."""

    def test_creates_new_path(self, tmp_path):
        from arm.ripper.makemkv import setup_rawpath

        job = unittest.mock.MagicMock()
        raw = str(tmp_path / "raw" / "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        result = setup_rawpath(job, raw)
        assert result == raw
        assert os.path.isdir(raw)

    def test_existing_path_is_reused(self, tmp_path):
        """With GUID paths, collision is impossible. If dir exists (e.g. retry),
        just reuse it."""
        from arm.ripper.makemkv import setup_rawpath

        raw = str(tmp_path / "raw" / "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        os.makedirs(raw)

        job = unittest.mock.MagicMock()
        result = setup_rawpath(job, raw)
        assert result == raw
        assert os.path.isdir(raw)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test/test_makemkv_coverage.py::TestSetupRawpath -v
```

Expected: `test_existing_path_is_reused` FAILS because current code appends timestamp.

- [ ] **Step 3: Simplify setup_rawpath**

In `arm/ripper/makemkv.py`, replace `setup_rawpath` (lines 1234-1263):

```python
def setup_rawpath(job, raw_path):
    """Create the raw rip output directory.

    With GUID-based paths, collision is not possible. If the directory
    already exists (e.g. retry after partial rip), reuse it.

    Parameters:
        job: arm.models.job.Job
        raw_path: str - absolute path to create
    Returns:
        str: the raw_path (unchanged)
    """
    logging.info(f"Destination is {raw_path}")
    try:
        os.makedirs(raw_path, exist_ok=True)
    except OSError:
        err = f"Couldn't create the base file path: {raw_path}. Probably a permissions error"
        logging.error(err)
        raise
    return raw_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test/test_makemkv_coverage.py::TestSetupRawpath -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest test/ -v
```

Expected: PASS. Some folder_ripper or rip_logic tests may mock `setup_rawpath` - verify they still work.

- [ ] **Step 6: Commit**

```bash
git add arm/ripper/makemkv.py test/test_makemkv_coverage.py
git commit -m "feat: simplify setup_rawpath - GUID paths eliminate collisions"
```

---

### Task 4: Make `clean_for_filename` public in naming.py, delete the other two

**Files:**
- Modify: `arm/ripper/naming.py:84-93` (rename `_clean_for_filename` to `clean_for_filename`)
- Modify: `arm/ripper/utils.py:197,928-941` (delete function, update import)
- Modify: `arm/api/v1/jobs.py:422-423,992-1000` (delete function, remove callsite)
- Modify: `test/test_utils.py:123-159` (delete `TestCleanForFilename`)
- Modify: `test/test_naming.py:272-296` (update import)

- [ ] **Step 1: Rename in naming.py**

In `arm/ripper/naming.py`, rename `_clean_for_filename` to `clean_for_filename` (line 84). Also update all internal references in the same file:

- Line 84: `def clean_for_filename(s):` (was `_clean_for_filename`)
- Line 147: `segments = [clean_for_filename(seg) for seg in segments if seg.strip()]`
- Line 199: `return clean_for_filename(track.custom_filename)`
- Line 272: `segments = [clean_for_filename(seg) for seg in segments if seg.strip()]`

- [ ] **Step 2: Update utils.py webhook import**

In `arm/ripper/utils.py` line 197, change:

```python
    from arm.ripper.naming import render_folder, render_title, render_all_tracks, _clean_for_filename
```

to:

```python
    from arm.ripper.naming import render_folder, render_title, render_all_tracks, clean_for_filename
```

Update references at lines 214 and 244 from `_clean_for_filename` to `clean_for_filename`.

- [ ] **Step 3: Delete `utils.clean_for_filename`**

In `arm/ripper/utils.py`, delete lines 928-941 (the `clean_for_filename` function).

- [ ] **Step 4: Delete `jobs.py _clean_for_filename`**

In `arm/api/v1/jobs.py`, delete lines 992-1000 (the `_clean_for_filename` function).

- [ ] **Step 5: Remove sanitization from API title edit**

In `arm/api/v1/jobs.py` line 422-423, remove the sanitization:

Before:
```python
        if key == 'title':
            value = _clean_for_filename(value)
```

After: delete those two lines entirely. The `value = str(body[key]).strip()` on line 421 is sufficient.

- [ ] **Step 6: Update test imports**

In `test/test_naming.py`, update the import at the top from `_clean_for_filename` to `clean_for_filename`, and update the test function calls (lines 272-296) to use `clean_for_filename`.

In `test/test_utils.py`, delete the entire `TestCleanForFilename` class (lines 123-159).

- [ ] **Step 7: Run tests**

```bash
pytest test/test_naming.py test/test_utils.py -v
```

Expected: PASS

- [ ] **Step 8: Run full test suite**

```bash
pytest test/ -v
```

Expected: PASS. Any test that imports `utils.clean_for_filename` or `_clean_for_filename` from jobs.py needs updating.

- [ ] **Step 9: Commit**

```bash
git add arm/ripper/naming.py arm/ripper/utils.py arm/api/v1/jobs.py test/test_naming.py test/test_utils.py
git commit -m "refactor: consolidate to single clean_for_filename in naming.py"
```

---

### Task 5: Remove aggressive sanitization from `identify.py` and `music_brainz.py`

**Files:**
- Modify: `arm/ripper/identify.py:547` (`update_job`)
- Modify: `arm/ripper/music_brainz.py:375-387`
- Create: `test/test_identify_no_sanitize.py`

- [ ] **Step 1: Write failing test for clean title storage**

Create `test/test_identify_no_sanitize.py`:

```python
"""Tests that identification stores clean, unsanitized titles."""
import unittest.mock

from arm.ripper import identify


class TestUpdateJobNoSanitize:
    """update_job should store API titles without aggressive sanitization."""

    def test_title_preserves_spaces(self, app_context, sample_job):
        """Metadata title 'Serial Mom' should not become 'Serial-Mom'."""
        match = unittest.mock.MagicMock()
        match.title = "Serial Mom"
        match.year = "1994"
        match.type = "movie"
        match.imdb_id = "tt0111127"
        match.poster_url = ""
        match.score = 0.95
        match.title_score = 0.95
        match.year_score = 1.0
        match.type_score = 1.0

        selection = unittest.mock.MagicMock()
        selection.confident = True
        selection.best = match
        selection.all_scored = [match]
        selection.label_info = None

        sample_job.label = "SERIAL_MOM"

        with unittest.mock.patch('arm.ripper.identify.arm_matcher') as mock_matcher:
            mock_matcher.return_value = selection
            identify.update_job(sample_job, [{"Title": "Serial Mom", "Year": "1994"}])

        assert sample_job.title == "Serial Mom"
        assert " " in sample_job.title  # spaces preserved, not converted to hyphens

    def test_title_preserves_colons(self, app_context, sample_job):
        """Colons in metadata titles are preserved for display/search."""
        match = unittest.mock.MagicMock()
        match.title = "Star Wars: A New Hope"
        match.year = "1977"
        match.type = "movie"
        match.imdb_id = "tt0076759"
        match.poster_url = ""
        match.score = 0.95
        match.title_score = 0.95
        match.year_score = 1.0
        match.type_score = 1.0

        selection = unittest.mock.MagicMock()
        selection.confident = True
        selection.best = match
        selection.all_scored = [match]
        selection.label_info = None

        sample_job.label = "STAR_WARS"

        with unittest.mock.patch('arm.ripper.identify.arm_matcher') as mock_matcher:
            mock_matcher.return_value = selection
            identify.update_job(sample_job, [{"Title": "Star Wars: A New Hope", "Year": "1977"}])

        assert sample_job.title == "Star Wars: A New Hope"


class TestMusicBrainzNoSanitize:
    """music_brainz should return clean artist + title without filesystem sanitization."""

    def test_return_value_preserves_spaces(self, app_context, sample_job):
        """Return value should be 'Artist Title', not 'Artist-Title'."""
        import arm.ripper.music_brainz as mb
        import musicbrainzngs

        disc_info = {
            'disc': {
                'release-list': [{
                    'id': 'test-release-id',
                    'title': 'The Dark Side of the Moon',
                    'artist-credit': [{'artist': {'name': 'Pink Floyd'}}],
                    'date': '1973-03-01',
                    'medium-list': [{'disc-list': [{}], 'track-list': []}],
                }]
            }
        }

        with unittest.mock.patch.object(mb, 'get_cd_art', return_value=False), \
             unittest.mock.patch.object(musicbrainzngs, 'get_releases_by_discid',
                                        return_value=disc_info):
            result = mb.music_brainz('fake-disc-id', sample_job)

        # Should contain spaces, not hyphens between words
        assert "Pink Floyd" in result
        assert "The Dark Side of the Moon" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test/test_identify_no_sanitize.py -v
```

Expected: FAIL - title gets aggressively sanitized.

- [ ] **Step 3: Remove sanitization from update_job**

In `arm/ripper/identify.py` line 547, change:

```python
    title = utils.clean_for_filename(best.title)
```

to:

```python
    title = best.title
```

- [ ] **Step 4: Remove sanitization from music_brainz.py**

In `arm/ripper/music_brainz.py` line 375, change:

```python
        clean_title = u.clean_for_filename(artist) + "-" + u.clean_for_filename(title)
```

to:

```python
        clean_title = f"{artist} {title}"
```

- [ ] **Step 5: Run tests**

```bash
pytest test/test_identify_no_sanitize.py -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest test/ -v
```

Expected: PASS. Some music_brainz tests may assert hyphens in return values - update those.

- [ ] **Step 7: Commit**

```bash
git add arm/ripper/identify.py arm/ripper/music_brainz.py test/test_identify_no_sanitize.py
git commit -m "feat: store clean titles without aggressive sanitization"
```

---

### Task 6: Add `disc_number`/`disc_total` to naming engine variables

**Files:**
- Modify: `arm/ripper/naming.py:50-76` (`_build_variables`)
- Modify: `test/test_naming.py`

Note: `disc_number` and `disc_total` columns already exist on the Job model (lines 153-154) and migration `d3e4f5a6b7c8` already created them. We just need to wire them into the naming pattern engine.

- [ ] **Step 1: Write failing test**

Add to `test/test_naming.py`:

```python
def test_disc_number_in_pattern():
    """disc_number variable is available in naming patterns."""
    job = _make_job(title='Dynasties', year='2018', video_type='movie')
    job.disc_number = 2
    cfg = {'MOVIE_TITLE_PATTERN': '{title} - Disc {disc_number}'}
    assert render_title(job, cfg) == 'Dynasties - Disc 2'


def test_disc_number_omitted_when_none():
    """Missing disc_number renders as empty string (cleaned up by pattern engine)."""
    job = _make_job(title='Dynasties', year='2018', video_type='movie')
    job.disc_number = None
    cfg = {'MOVIE_TITLE_PATTERN': '{title} ({year})'}
    assert render_title(job, cfg) == 'Dynasties (2018)'


def test_disc_total_in_pattern():
    job = _make_job(title='Dynasties', year='2018', video_type='movie')
    job.disc_number = 2
    job.disc_total = 3
    cfg = {'MOVIE_FOLDER_PATTERN': '{title} ({year})/Disc {disc_number} of {disc_total}'}
    assert render_folder(job, cfg) == os.path.join('Dynasties (2018)', 'Disc 2 of 3')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test/test_naming.py::test_disc_number_in_pattern test/test_naming.py::test_disc_number_omitted_when_none test/test_naming.py::test_disc_total_in_pattern -v
```

Expected: FAIL - `disc_number` not in pattern variables.

- [ ] **Step 3: Add disc_number/disc_total to _build_variables**

In `arm/ripper/naming.py`, update `_build_variables` (around line 67):

```python
    return _SafeDict({
        'title': title,
        'year': year,
        'artist': artist,
        'album': album,
        'season': season,
        'episode': episode,
        'label': getattr(job, 'label', '') or '',
        'video_type': getattr(job, 'video_type', '') or '',
        'disc_number': str(getattr(job, 'disc_number', '') or ''),
        'disc_total': str(getattr(job, 'disc_total', '') or ''),
    })
```

- [ ] **Step 4: Run tests**

```bash
pytest test/test_naming.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add arm/ripper/naming.py test/test_naming.py
git commit -m "feat: add disc_number/disc_total to naming pattern variables"
```

---

### Task 7: Add `finalize_output()` for transcoder-disabled deployments

**Files:**
- Modify: `arm/ripper/naming.py` (add `finalize_output` function)
- Create: `test/test_finalize_output.py`

- [ ] **Step 1: Write failing tests**

Create `test/test_finalize_output.py`:

```python
"""Tests for finalize_output() — moves files from GUID work dir to final library."""
import os
import unittest.mock

import pytest

from arm.ripper.naming import finalize_output


class TestFinalizeOutput:
    """finalize_output moves ripped files from GUID raw dir to final named path."""

    def test_moves_single_movie(self, app_context, sample_job, tmp_path):
        """Single MKV file moved to completed path with rendered name."""
        # Setup: create raw GUID dir with one MKV
        raw_dir = tmp_path / "raw" / sample_job.guid
        raw_dir.mkdir(parents=True)
        (raw_dir / "B1_t00.mkv").write_bytes(b"fake mkv")

        sample_job.raw_path = str(raw_dir)
        sample_job.config.COMPLETED_PATH = str(tmp_path / "completed")
        sample_job.video_type = "movie"
        sample_job.title = "Serial Mom"
        sample_job.year = "1994"

        finalize_output(sample_job)

        # File should be in completed/movies/Serial Mom (1994)/
        final_dir = tmp_path / "completed" / "movies"
        assert final_dir.exists()
        # At least one .mkv file in the final tree
        mkv_files = list(final_dir.rglob("*.mkv"))
        assert len(mkv_files) == 1

    def test_moves_multiple_tracks(self, app_context, sample_job, tmp_path):
        """Multi-title disc: each track gets its rendered name."""
        from arm.models.track import Track
        from arm.database import db

        raw_dir = tmp_path / "raw" / sample_job.guid
        raw_dir.mkdir(parents=True)
        (raw_dir / "B1_t00.mkv").write_bytes(b"fake")
        (raw_dir / "B1_t01.mkv").write_bytes(b"fake")

        sample_job.raw_path = str(raw_dir)
        sample_job.config.COMPLETED_PATH = str(tmp_path / "completed")
        sample_job.video_type = "movie"
        sample_job.title = "Serial Mom"
        sample_job.year = "1994"

        # Create track records
        t1 = Track(job_id=sample_job.job_id, track_number=0, filename="B1_t00.mkv", ripped=True)
        t2 = Track(job_id=sample_job.job_id, track_number=1, filename="B1_t01.mkv", ripped=True)
        db.session.add_all([t1, t2])
        db.session.commit()

        finalize_output(sample_job)

        final_dir = tmp_path / "completed" / "movies"
        mkv_files = list(final_dir.rglob("*.mkv"))
        assert len(mkv_files) == 2

    def test_cleans_up_empty_raw_dir(self, app_context, sample_job, tmp_path):
        """After moving all files, empty GUID directory is removed."""
        raw_dir = tmp_path / "raw" / sample_job.guid
        raw_dir.mkdir(parents=True)
        (raw_dir / "B1_t00.mkv").write_bytes(b"fake")

        sample_job.raw_path = str(raw_dir)
        sample_job.config.COMPLETED_PATH = str(tmp_path / "completed")

        finalize_output(sample_job)

        assert not raw_dir.exists()

    def test_updates_job_path(self, app_context, sample_job, tmp_path):
        """job.path is updated to the final directory after move."""
        raw_dir = tmp_path / "raw" / sample_job.guid
        raw_dir.mkdir(parents=True)
        (raw_dir / "B1_t00.mkv").write_bytes(b"fake")

        sample_job.raw_path = str(raw_dir)
        sample_job.config.COMPLETED_PATH = str(tmp_path / "completed")

        finalize_output(sample_job)

        assert sample_job.path is not None
        assert "completed" in sample_job.path

    def test_noop_if_no_raw_path(self, app_context, sample_job):
        """No error if raw_path is not set."""
        sample_job.raw_path = None
        finalize_output(sample_job)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test/test_finalize_output.py -v
```

Expected: FAIL - `ImportError: cannot import name 'finalize_output'`

- [ ] **Step 3: Implement finalize_output**

In `arm/ripper/naming.py`, add at the end of the file:

```python
def finalize_output(job):
    """Move ripped files from GUID work directory to final named location.

    Used when the transcoder is disabled - ARM handles final naming directly.
    Renders folder/file names via the naming engine, moves files, updates job.path,
    and cleans up the empty work directory.
    """
    import shutil
    from arm.database import db
    import arm.config.config as cfg

    raw_path = getattr(job, 'raw_path', None)
    if not raw_path or not os.path.isdir(raw_path):
        logging.warning("finalize_output: no raw_path for job %s", getattr(job, 'job_id', '?'))
        return

    config_dict = cfg.arm_config if hasattr(cfg, 'arm_config') else None
    final_dir = job.build_final_path()
    os.makedirs(final_dir, exist_ok=True)

    # Get rendered names for each track
    rendered = render_all_tracks(job, config_dict)
    rendered_map = {r["track_number"]: r for r in rendered}

    moved_count = 0
    for track in job.tracks:
        if not track.filename:
            continue
        src = os.path.join(raw_path, track.filename)
        if not os.path.isfile(src):
            continue

        r = rendered_map.get(str(track.track_number or ''), {})
        rendered_title = r.get("rendered_title", '')
        rendered_folder = r.get("rendered_folder", '')

        if rendered_title:
            dest_name = clean_for_filename(rendered_title) + os.path.splitext(track.filename)[1]
        else:
            dest_name = track.filename

        if rendered_folder:
            dest_dir = os.path.join(final_dir, rendered_folder)
        else:
            dest_dir = final_dir

        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(src, os.path.join(dest_dir, dest_name))
        moved_count += 1

    # If no tracks (single-title disc without track records), move all MKVs
    if moved_count == 0:
        for fname in os.listdir(raw_path):
            if fname.lower().endswith('.mkv'):
                rendered_title = render_title(job, config_dict)
                if rendered_title:
                    dest_name = clean_for_filename(rendered_title) + '.mkv'
                else:
                    dest_name = fname
                shutil.move(os.path.join(raw_path, fname), os.path.join(final_dir, dest_name))

    # Update job.path and clean up
    job.path = final_dir
    db.session.commit()

    # Remove empty work directory
    try:
        if os.path.isdir(raw_path) and not os.listdir(raw_path):
            os.rmdir(raw_path)
    except OSError:
        pass

    logging.info("finalize_output: moved %d files to %s", moved_count, final_dir)
```

- [ ] **Step 4: Run tests**

```bash
pytest test/test_finalize_output.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add arm/ripper/naming.py test/test_finalize_output.py
git commit -m "feat: add finalize_output for transcoder-disabled deployments"
```

---

### Task 8: Wire `finalize_output` into rip pipelines

**Files:**
- Modify: `arm/ripper/arm_ripper.py:57-71`
- Modify: `arm/ripper/folder_ripper.py:205-218`

- [ ] **Step 1: Update arm_ripper.py**

In `arm/ripper/arm_ripper.py`, replace lines 57-71:

```python
    # Persist raw_path to DB — this is the actual directory on disk
    utils.database_updater({'raw_path': makemkv_out_path}, job)

    # Determine whether to hand off to transcoder or finalize locally
    import arm.config.config as cfg
    transcoder_url = cfg.arm_config.get('TRANSCODER_URL', '')

    if transcoder_url:
        if job.config.NOTIFY_RIP:
            # notify() also calls transcoder_notify internally
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} rip complete.")
        else:
            # Always notify the transcoder when TRANSCODER_URL is set, even if
            # NOTIFY_RIP is off.  The transcoder webhook is a pipeline trigger,
            # not a user notification.
            utils.transcoder_notify(
                cfg.arm_config, constants.NOTIFY_TITLE,
                f"{job.title} rip complete.", job,
            )
    else:
        # No transcoder — finalize output locally
        from arm.ripper.naming import finalize_output
        logging.info("No transcoder configured — finalizing output locally")
        finalize_output(job)
        if job.config.NOTIFY_RIP:
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} rip complete.")
```

- [ ] **Step 2: Update folder_ripper.py**

In `arm/ripper/folder_ripper.py`, replace lines 205-218:

```python
        # 7. Notify transcoder or finalize locally
        transcoder_url = cfg.arm_config.get("TRANSCODER_URL", "")
        if transcoder_url:
            utils.transcoder_notify(
                cfg.arm_config,
                "ARM Notification",
                f"{job.title} folder import rip complete.",
                job,
            )
            job.status = JobState.TRANSCODE_WAITING.value
        else:
            from arm.ripper.naming import finalize_output
            log.info("No transcoder configured — finalizing output locally")
            finalize_output(job)
            job.status = JobState.SUCCESS.value

        db.session.commit()
        log.info("Folder import rip complete for job %s", job.job_id)
```

- [ ] **Step 3: Run full test suite**

```bash
pytest test/ -v
```

Expected: PASS. Mocked tests should still work since they mock `transcoder_notify`.

- [ ] **Step 4: Commit**

```bash
git add arm/ripper/arm_ripper.py arm/ripper/folder_ripper.py
git commit -m "feat: call finalize_output when transcoder is disabled"
```

---

### Task 9: Add `disc_number`/`disc_total` to API field maps

**Files:**
- Modify: `arm/api/v1/jobs.py:398-411` (`_FIELD_MAP`, `_DIRECT_FIELDS`)

- [ ] **Step 1: Update field maps**

`disc_number` and `disc_total` are already in `_DIRECT_FIELDS` on line 409:

```python
_DIRECT_FIELDS = ('path', 'label', 'disctype', 'disc_number', 'disc_total')
```

These are already editable via the title edit endpoint. No code change needed here - verify with a test.

- [ ] **Step 2: Write test to verify disc_number is editable via API**

Add to test file for API (or create if needed):

```python
def test_disc_number_editable_via_title_endpoint(self, app_context, sample_job, client):
    """disc_number can be set via PUT /jobs/{id}/title."""
    from arm.database import db
    db.session.add(sample_job)
    db.session.commit()

    resp = client.put(
        f"/api/v1/jobs/{sample_job.job_id}/title",
        json={"disc_number": 2, "disc_total": 3},
    )
    assert resp.status_code == 200
    assert sample_job.disc_number == 2
    assert sample_job.disc_total == 3
```

- [ ] **Step 3: Run test**

```bash
pytest test/ -k "disc_number_editable" -v
```

Expected: PASS (already supported).

- [ ] **Step 4: Commit (if any changes were needed)**

```bash
git add -A && git commit -m "test: verify disc_number/disc_total API editability"
```

---

### Task 10: Final integration pass - run full test suite and CI checks

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest test/ -v --cov=arm --cov-report=term-missing
```

Expected: All tests PASS.

- [ ] **Step 2: Check for any remaining references to deleted functions**

```bash
grep -rn "utils.clean_for_filename\|from arm.ripper.utils import.*clean_for_filename" arm/ test/
grep -rn "_clean_for_filename" arm/api/
```

Expected: No hits (all references removed).

- [ ] **Step 3: Check for any remaining imports of deleted code**

```bash
grep -rn "from arm.ripper.naming import.*_clean_for_filename" arm/ test/
```

Expected: No hits (all switched to `clean_for_filename` without underscore).

- [ ] **Step 4: Verify linting passes**

```bash
python -m py_compile arm/models/job.py
python -m py_compile arm/ripper/naming.py
python -m py_compile arm/ripper/identify.py
python -m py_compile arm/ripper/utils.py
python -m py_compile arm/ripper/makemkv.py
python -m py_compile arm/ripper/arm_ripper.py
python -m py_compile arm/ripper/folder_ripper.py
python -m py_compile arm/ripper/music_brainz.py
python -m py_compile arm/api/v1/jobs.py
```

Expected: No syntax errors.

- [ ] **Step 5: Final commit if any fixups needed, then prepare PR**

```bash
git log --oneline main..HEAD
```

Review commit history, then create PR.
