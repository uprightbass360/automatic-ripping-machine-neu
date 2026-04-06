# Harden Upstream Ports Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix safety issues found during audit of 6 upstream ports that were merged prematurely without full review.

**Architecture:** Targeted fixes to existing code — no new modules or major refactors. Each task is independent and can be committed separately. The TV disc label parser consolidation (#1605) is the largest change; all others are 1-5 line fixes.

**Tech Stack:** Python 3, SQLAlchemy, FastAPI, bash, pytest

**Testing:** All tests run in Docker: `docker exec arm-rippers python3 -m pytest /opt/arm/test/ -v`. After editing files on the host, copy into the container: `docker cp <file> arm-rippers:/opt/arm/<path>`.

---

## File Map

| File | Changes | Responsibility |
|------|---------|----------------|
| `arm/ripper/arm_matcher.py` | Hyphen fix (issue #60), dot separator fix, add `disc_identifier` property to `LabelInfo` | Single source of truth for label parsing |
| `arm/ripper/utils.py` | Remove `parse_disc_label_for_identifiers()`, rewrite `get_tv_folder_name()` to use `arm_matcher.parse_label()`, fix empty folder guard, fix `save_disc_poster()` spurious umount | TV folder naming, poster extraction |
| `arm/models/job.py` | Guard empty folder from `get_tv_folder_name()` in `build_final_path()` | Final path construction |
| `arm/api/v1/settings.py` | Atomic config reload, None guard | Settings persistence |
| `scripts/docker/runit/arm_user_files_setup.sh` | Fix abcde.conf ownership, fix sed ownership reset | Container init |
| `test/test_rip_logic.py` | Update tests for consolidated parser, add edge case tests | Test coverage |

---

## Chunk 1: Hyphen Fix + Label Parser Consolidation

### Task 1: Apply hyphen normalization in parse_label (issue #60)

**Files:**
- Modify: `arm/ripper/arm_matcher.py:197-201` (already done on branch)
- Test: `test/test_rip_logic.py` (new tests)

The hyphen fix is already applied on the current branch. This task also adds dot (`.`) separator normalization — required for consolidation in Task 3 because `parse_disc_label_for_identifiers()` handles dot separators (e.g., `Breaking.Bad.S02.D02`) but `parse_label()` does not.

- [ ] **Step 1: Write failing tests for hyphen and dot normalization**

In `test/test_rip_logic.py`, add a new test class:

```python
class TestLabelSeparatorNormalization:
    """Test that hyphens and dots in disc labels are treated as word separators (#60)."""

    def test_hyphenated_label_normalized(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("THE-BOONDOCK-SAINTS")
        assert info.title == "the boondock saints"

    def test_hyphenated_sequel_normalized(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("SPIDER-MAN-2")
        assert info.title == "spider man 2"

    def test_bluray_suffix_still_removed(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("X-MEN - Blu-rayTM")
        assert info.title == "x men"
        assert "blu" not in info.title

    def test_hyphenated_with_disc_suffix(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("X-MEN-FIRST-CLASS D1")
        assert info.title == "x men first class"
        assert info.disc_number == 1

    def test_dot_separated_label(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("Breaking.Bad.S02.D02")
        assert info.season_number == 2
        assert info.disc_number == 2
        assert "breaking" in info.title
        assert "bad" in info.title

    def test_dot_separated_title_only(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("The.Wire")
        assert info.title == "the wire"
```

- [ ] **Step 2: Add dot normalization to parse_label**

In `arm/ripper/arm_matcher.py`, after the hyphen replacement line, add:

```python
    s = s.replace('-', ' ')
    s = s.replace('.', ' ')
```

This must be after Blu-ray suffix removal (same reason as hyphens — suffixes like `' - Blu-rayTM'` contain dots in `'rayTM'` but that suffix is already removed by this point so no conflict).

- [ ] **Step 3: Copy files into container and run tests**

```bash
docker cp test/test_rip_logic.py arm-rippers:/opt/arm/test/test_rip_logic.py
docker cp arm/ripper/arm_matcher.py arm-rippers:/opt/arm/arm/ripper/arm_matcher.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py::TestLabelSeparatorNormalization -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add arm/ripper/arm_matcher.py test/test_rip_logic.py
git commit -m "fix: normalize hyphens and dots as word separators in parse_label (#60)

Adds s.replace('-', ' ') and s.replace('.', ' ') AFTER Blu-ray suffix
removal to avoid breaking literal matching in _BLURAY_SUFFIXES.
Gives 4.6x better sequel discrimination for hyphenated disc labels.
Dot handling required for parity with parse_disc_label_for_identifiers
ahead of parser consolidation."
```

---

### Task 2: Add disc_identifier property to LabelInfo

**Files:**
- Modify: `arm/ripper/arm_matcher.py:18-26`
- Test: `test/test_rip_logic.py` (new tests)

Add a computed property so `get_tv_folder_name()` can use `LabelInfo` instead of the duplicate parser.

- [ ] **Step 1: Write failing test**

```python
class TestLabelInfoDiscIdentifier:
    """Test LabelInfo.disc_identifier property."""

    def test_season_and_disc(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("BB_S1D1")
        assert info.disc_identifier == "S1D1"

    def test_season_only(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("BB_S1")
        assert info.disc_identifier == "S1"

    def test_disc_only(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("BB_D2")
        assert info.disc_identifier == "D2"

    def test_no_identifiers(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("BREAKING_BAD_2008")
        assert info.disc_identifier is None

    def test_season_disc_with_leading_zeros(self):
        from arm.ripper.arm_matcher import parse_label
        info = parse_label("GOT_S05_D03")
        assert info.disc_identifier == "S5D3"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker cp test/test_rip_logic.py arm-rippers:/opt/arm/test/test_rip_logic.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py::TestLabelInfoDiscIdentifier -v
```

Expected: FAIL — `LabelInfo` has no `disc_identifier` attribute

- [ ] **Step 3: Implement disc_identifier property**

In `arm/ripper/arm_matcher.py`, add a property to `LabelInfo`:

```python
@dataclass
class LabelInfo:
    """Parsed disc label with title and disc metadata."""
    title: str               # normalized title: "lotr fellowship of the ring"
    disc_number: int | None  # 1, 2, etc. (None if not a numbered disc)
    disc_type: str | None    # "part", "disc", "bonus", "extras", "special_features"
    raw_label: str           # original input: "LOTR_FELLOWSHIP_OF_THE_RING_P1"
    season_number: int | None = None  # 1, 2, etc. (None if not a TV season disc)

    @property
    def disc_identifier(self) -> str | None:
        """Format season/disc as a compact identifier (e.g. 'S1D1', 'S2', 'D3').

        Returns None when neither season nor disc number is available.
        """
        if self.season_number is not None and self.disc_number is not None:
            return f"S{self.season_number}D{self.disc_number}"
        if self.season_number is not None:
            return f"S{self.season_number}"
        if self.disc_number is not None:
            return f"D{self.disc_number}"
        return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker cp arm/ripper/arm_matcher.py arm-rippers:/opt/arm/arm/ripper/arm_matcher.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py::TestLabelInfoDiscIdentifier -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add arm/ripper/arm_matcher.py test/test_rip_logic.py
git commit -m "feat: add disc_identifier property to LabelInfo

Computed property formats season/disc as compact identifier
(S1D1, S2, D3) for use by TV folder naming. Enables consolidation
of duplicate parse_disc_label_for_identifiers() in utils.py."
```

---

### Task 3: Consolidate TV folder naming onto arm_matcher.parse_label

**Files:**
- Modify: `arm/ripper/utils.py:984-1094` — remove `parse_disc_label_for_identifiers()`, rewrite `get_tv_folder_name()`
- Modify: `arm/models/job.py:428-443` — guard empty folder name
- Modify: `test/test_rip_logic.py` — update tests

- [ ] **Step 1: Write test for empty folder fallback in build_final_path**

```python
class TestBuildFinalPathEmptyFolderGuard:
    """build_final_path must never produce a path ending in just the type subfolder."""

    def test_none_title_falls_back_to_formatted_title(self, app_context, sample_job):
        sample_job.video_type = "series"
        sample_job.title = None
        sample_job.title_manual = None
        sample_job.label = "BB_S1D1"
        sample_job.config.USE_DISC_LABEL_FOR_TV = True
        sample_job.config.COMPLETED_PATH = "/media/completed"
        path = sample_job.build_final_path()
        # Must not end with just "tv/" — should have a folder name
        assert not path.endswith("/tv/")
        assert not path.endswith("/tv")
        assert path.count("/") >= 3  # /media/completed/tv/something
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — current code produces `/media/completed/tv/` when title is None

- [ ] **Step 3: Rewrite get_tv_folder_name to use arm_matcher**

Replace the function body in `arm/ripper/utils.py`:

```python
def get_tv_folder_name(job):
    """Generate TV series folder name based on configuration.

    If USE_DISC_LABEL_FOR_TV is enabled and disc label parsing succeeds:
        Returns: "{normalized_series_name}_{disc_identifier}" e.g. "Breaking_Bad_S1D1"
    Otherwise, falls back to standard naming via formatted_title.

    :param job: Job object containing title, label, year, etc.
    :return: Folder name string (never empty — falls back to formatted_title)
    """
    from arm.ripper.arm_matcher import parse_label

    use_disc_label = getattr(job.config, 'USE_DISC_LABEL_FOR_TV', False) if hasattr(job, 'config') else False

    if not use_disc_label:
        return job.formatted_title

    if job.video_type != "series":
        return job.formatted_title

    series_name = job.title_manual if job.title_manual else job.title
    if not series_name:
        logging.warning("No series title available, falling back to standard naming")
        return job.formatted_title

    label_info = parse_label(job.label)
    disc_id = label_info.disc_identifier
    if disc_id:
        normalized_name = normalize_series_name(series_name)
        folder_name = f"{normalized_name}_{disc_id}"
        logging.info(f"Using disc label-based folder name: '{folder_name}' "
                     f"(from series '{series_name}' and label '{job.label}')")
        return folder_name

    logging.info(f"Could not parse disc identifier from label '{job.label}', "
                 f"falling back to standard naming")
    return job.formatted_title
```

Key changes from current implementation:
1. Returns `job.formatted_title` instead of `""` when series_name is None
2. Uses `arm_matcher.parse_label()` + `disc_identifier` instead of `parse_disc_label_for_identifiers()`

- [ ] **Step 4: Guard empty folder in build_final_path**

In `arm/models/job.py`, add a guard after `get_tv_folder_name`:

```python
    def build_final_path(self):
        from arm.ripper.utils import get_tv_folder_name, get_tv_series_parent_folder

        if self.video_type == "series" and getattr(self.config, 'USE_DISC_LABEL_FOR_TV', False):
            folder = get_tv_folder_name(self)
            if not folder:
                folder = self.formatted_title
            if getattr(self.config, 'GROUP_TV_DISCS_UNDER_SERIES', False):
                parent = get_tv_series_parent_folder(self)
                return os.path.join(self.config.COMPLETED_PATH, self.type_subfolder, parent, folder)
            return os.path.join(self.config.COMPLETED_PATH, self.type_subfolder, folder)
```

- [ ] **Step 5: Remove parse_disc_label_for_identifiers**

Delete the `parse_disc_label_for_identifiers()` function (lines 984-1031) from `arm/ripper/utils.py`. It is no longer called.

- [ ] **Step 6: Update existing tests**

Update `TestTVFolderNameEdgeCases`:

```python
def test_no_series_name_falls_back_to_formatted_title(self, app_context, sample_job):
    """When series title is None, fall back to formatted_title (not empty)."""
    from arm.ripper.utils import get_tv_folder_name
    sample_job.video_type = "series"
    sample_job.title = None
    sample_job.title_manual = None
    sample_job.label = "BB_S1D1"
    sample_job.year = "2008"
    sample_job.config.USE_DISC_LABEL_FOR_TV = True
    result = get_tv_folder_name(sample_job)
    assert result == sample_job.formatted_title
    assert result != ""

def test_empty_title_falls_back_to_formatted_title(self, app_context, sample_job):
    """When title is empty string, fall back to formatted_title."""
    from arm.ripper.utils import get_tv_folder_name
    sample_job.video_type = "series"
    sample_job.title = ""
    sample_job.title_manual = None
    sample_job.label = "BB_S1D1"
    sample_job.year = "2008"
    sample_job.config.USE_DISC_LABEL_FOR_TV = True
    result = get_tv_folder_name(sample_job)
    assert result == sample_job.formatted_title
```

Remove `TestDiscLabelParsing` class (tests for the deleted function). The equivalent parsing is covered by `TestLabelInfoDiscIdentifier` and existing `arm_matcher` tests.

- [ ] **Step 7: Run all tests**

```bash
docker cp arm/ripper/utils.py arm-rippers:/opt/arm/arm/ripper/utils.py
docker cp arm/ripper/arm_matcher.py arm-rippers:/opt/arm/arm/ripper/arm_matcher.py
docker cp arm/models/job.py arm-rippers:/opt/arm/arm/models/job.py
docker cp test/test_rip_logic.py arm-rippers:/opt/arm/test/test_rip_logic.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py -v -k "TVFolder or BuildFinalPath or DiscIdentifier"
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add arm/ripper/utils.py arm/models/job.py test/test_rip_logic.py
git commit -m "fix: consolidate TV disc label parser onto arm_matcher (#1605)

- Remove duplicate parse_disc_label_for_identifiers() from utils.py
- Rewrite get_tv_folder_name() to use arm_matcher.parse_label()
- Fix empty folder bug: return formatted_title instead of '' when
  series title is unavailable
- Guard empty folder in build_final_path() as defense-in-depth"
```

---

## Chunk 2: Settings Reload + Shell Script Fixes

### Task 4: Fix atomic config reload and None guard (#1639)

**Files:**
- Modify: `arm/api/v1/settings.py:93-96`
- Test: `test/test_rip_logic.py` (new test)

- [ ] **Step 1: Write failing test for None YAML**

```python
class TestSettingsReloadNoneGuard:
    """Config reload must not crash on empty YAML file (#1639)."""

    def test_empty_yaml_does_not_crash(self, tmp_path):
        import yaml
        import arm.config.config as cfg

        original_config = dict(cfg.arm_config)
        original_path = cfg.arm_config_path

        try:
            # Write an empty YAML file (safe_load returns None)
            config_file = tmp_path / "empty.yaml"
            config_file.write_text("")

            cfg.arm_config_path = str(config_file)
            with open(cfg.arm_config_path, "r") as f:
                new_values = yaml.safe_load(f)

            # This is what the endpoint does — should not raise TypeError
            new_values = new_values or {}
            cfg.arm_config.clear()
            cfg.arm_config.update(new_values)

            assert isinstance(cfg.arm_config, dict)
        finally:
            cfg.arm_config.clear()
            cfg.arm_config.update(original_config)
            cfg.arm_config_path = original_path
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker cp test/test_rip_logic.py arm-rippers:/opt/arm/test/test_rip_logic.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py::TestSettingsReloadNoneGuard -v
```

Expected: PASS (the test itself includes the fix inline — this validates the approach)

- [ ] **Step 3: Apply fix in settings.py**

In `arm/api/v1/settings.py`, replace lines 93-96:

```python
    try:
        new_values = await asyncio.to_thread(_read_config)
        new_values = new_values or {}
        cfg.arm_config.clear()
        cfg.arm_config.update(new_values)
```

This adds one line: `new_values = new_values or {}` — prevents `TypeError` from `update(None)`.

The non-atomic window between `clear()` and `update()` is microseconds on CPython (GIL prevents true parallel execution). Documenting this is sufficient; no lock needed for a settings endpoint that's called rarely by a single admin user.

- [ ] **Step 4: Run tests**

```bash
docker cp arm/api/v1/settings.py arm-rippers:/opt/arm/arm/api/v1/settings.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py -v -k "Settings"
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/settings.py test/test_rip_logic.py
git commit -m "fix: guard against None from yaml.safe_load in config reload (#1639)

Empty YAML files parse to None, which crashes dict.update().
Add 'new_values = new_values or {}' before clear+update."
```

---

### Task 5: Fix save_disc_poster spurious umount (#1664)

**Files:**
- Modify: `arm/ripper/utils.py:940-981`
- Test: `test/test_rip_logic.py` (update existing test)

- [ ] **Step 1: Write failing test**

```python
class TestSaveDiscPosterMountFailure:
    """When mount fails, umount should NOT be called (#1664)."""

    def test_mount_failure_skips_umount(self, app_context, sample_job):
        import unittest.mock
        sample_job.disctype = "dvd"
        sample_job.devpath = "/dev/sr0"
        sample_job.mountpoint = "/mnt/sr0"

        with unittest.mock.patch('arm.ripper.utils.cfg') as mock_cfg, \
             unittest.mock.patch('arm.ripper.utils.subprocess.run') as mock_run:
            mock_cfg.arm_config = {"RIP_POSTER": True}
            # Mount fails
            mock_run.return_value = unittest.mock.Mock(returncode=1, stderr="mount failed")

            from arm.ripper.utils import save_disc_poster
            save_disc_poster("/tmp/final", sample_job)

            # subprocess.run should be called once (mount) but NOT twice (umount)
            assert mock_run.call_count == 1
            assert mock_run.call_args_list[0][0][0][0] == "mount"
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — currently `finally` block always calls umount, so `call_count == 2`

- [ ] **Step 3: Apply fix**

In `arm/ripper/utils.py`, restructure `save_disc_poster` to track mount state:

```python
def save_disc_poster(final_directory, job):
    """
     Use FFMPeg to convert Large Poster if enabled in config
    :param final_directory: folder to put the poster in
    :param job: Current Job
    :return: None
    """
    if job.disctype != "dvd" or not cfg.arm_config["RIP_POSTER"]:
        return

    result = subprocess.run(
        ["mount", job.devpath],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logging.error(f"Failed to mount {job.devpath}: {result.stderr.strip()}")
        return

    try:
        ntsc_poster = os.path.join(job.mountpoint, "JACKET_P", "J00___5L.MP2")
        pal_poster = os.path.join(job.mountpoint, "JACKET_P", "J00___6L.MP2")
        poster_out = os.path.join(final_directory, "poster.png")

        if os.path.isfile(ntsc_poster):
            logging.info("Converting NTSC Poster Image")
            subprocess.run(
                ["ffmpeg", "-i", ntsc_poster, poster_out],
                capture_output=True, text=True,
            )
        elif os.path.isfile(pal_poster):
            logging.info("Converting PAL Poster Image")
            subprocess.run(
                ["ffmpeg", "-i", pal_poster, poster_out],
                capture_output=True, text=True,
            )
    finally:
        umount = subprocess.run(
            ["umount", job.devpath],
            capture_output=True, text=True,
        )
        if umount.returncode != 0:
            logging.error(f"Failed to umount {job.devpath}: {umount.stderr.strip()}")
```

The key change: `return` on mount failure happens *before* entering the `try/finally` block, so `finally` only runs when mount succeeded.

- [ ] **Step 4: Run tests**

```bash
docker cp arm/ripper/utils.py arm-rippers:/opt/arm/arm/ripper/utils.py
docker cp test/test_rip_logic.py arm-rippers:/opt/arm/test/test_rip_logic.py
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py::TestSaveDiscPosterMountFailure -v
docker exec arm-rippers python3 -m pytest /opt/arm/test/test_rip_logic.py -v -k "poster"
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add arm/ripper/utils.py test/test_rip_logic.py
git commit -m "fix: skip umount when mount fails in save_disc_poster (#1664)

Move early return on mount failure before the try/finally block
so the finally clause only runs umount when mount actually succeeded."
```

---

### Task 6: Fix config file ownership in setup script (#1660)

**Files:**
- Modify: `scripts/docker/runit/arm_user_files_setup.sh:141-144, 155-158`

- [ ] **Step 1: Fix abcde.conf to use install instead of cp**

In `scripts/docker/runit/arm_user_files_setup.sh`, replace line 157:

Old:
```bash
  cp /opt/arm/setup/.abcde.conf /etc/arm/config/abcde.conf
```

New:
```bash
  install -o arm -g arm -m 644 /opt/arm/setup/.abcde.conf /etc/arm/config/abcde.conf
```

- [ ] **Step 2: Fix sed -i ownership reset**

After the `apply_yaml_override` calls (after line 144), add a `chown` to restore ownership:

```bash
apply_yaml_override TRANSCODER_URL ARM_TRANSCODER_URL
apply_yaml_override TRANSCODER_WEBHOOK_SECRET ARM_TRANSCODER_WEBHOOK_SECRET
apply_yaml_override LOCAL_RAW_PATH ARM_LOCAL_RAW_PATH
apply_yaml_override SHARED_RAW_PATH ARM_SHARED_RAW_PATH
# sed -i may reset file ownership to root — restore arm ownership
chown arm:arm "$ARM_YAML" 2>/dev/null || true
```

- [ ] **Step 3: Validate shell syntax**

```bash
bash -n scripts/docker/runit/arm_user_files_setup.sh
```

Expected: No output (clean parse)

- [ ] **Step 4: Commit**

```bash
git add scripts/docker/runit/arm_user_files_setup.sh
git commit -m "fix: correct file ownership in setup script (#1660)

- Use 'install -o arm -g arm' for abcde.conf (was plain cp, created as root)
- Restore arm.yaml ownership after sed -i overrides (sed resets to root)"
```

---

## Chunk 3: Full Regression Test

### Task 7: Run full test suite

- [ ] **Step 1: Copy all modified files into container**

```bash
docker cp arm/ripper/arm_matcher.py arm-rippers:/opt/arm/arm/ripper/arm_matcher.py
docker cp arm/ripper/utils.py arm-rippers:/opt/arm/arm/ripper/utils.py
docker cp arm/models/job.py arm-rippers:/opt/arm/arm/models/job.py
docker cp arm/api/v1/settings.py arm-rippers:/opt/arm/arm/api/v1/settings.py
docker cp test/test_rip_logic.py arm-rippers:/opt/arm/test/test_rip_logic.py
```

- [ ] **Step 2: Run full test suite**

```bash
docker exec arm-rippers python3 -m pytest /opt/arm/test/ -v
```

Expected: All tests pass, no regressions

- [ ] **Step 3: Verify shell script**

```bash
bash -n scripts/docker/runit/arm_user_files_setup.sh
```

---

## Summary of Changes

| Issue | Bug | Fix | Risk |
|-------|-----|-----|------|
| #60 | Hyphens not normalized in disc labels | `s.replace('-', ' ')` after Blu-ray suffix removal | Low |
| #1605 | Duplicate parser + empty folder bug | Consolidate onto `arm_matcher.parse_label()`, return `formatted_title` instead of `""` | Medium — removes 48 lines of regex, changes function behavior |
| #1639 | Crash on empty YAML | `new_values = new_values or {}` | Low |
| #1660 | abcde.conf root-owned, sed resets ownership | `install` for abcde, `chown` after sed | Low |
| #1664 | Spurious umount on mount failure | Move early return before try/finally | Low |

### Parser Consolidation Detail (#1605)

The duplicate `parse_disc_label_for_identifiers()` in utils.py supports patterns that `arm_matcher.parse_label()` also handles. Coverage comparison:

| Pattern | `parse_disc_label_for_identifiers` | `arm_matcher.parse_label` |
|---------|-----------------------------------|--------------------------|
| `S1D1`, `S01_D02` | Yes | Yes (via `_SEASON_DISC_RE`) |
| `Season1Disc1` | Yes (Pattern 2) | No — but `_SEASON_KEYWORD_RE` handles `SEASON_1` |
| `S1E1D1` | Yes (Pattern 1) | No — arm_matcher doesn't parse episodes |
| `S1`, `D1` separate tokens | Yes (Pattern 3) | Yes (via `_SEASON_SUFFIX_RE` + `_DISC_SUFFIX_RE`) |
| Bonus/extras/special features | No | Yes |
| Word numbers (DISC_ONE) | No | Yes |

**Gaps and accepted regressions:**

| Pattern | Old parser | arm_matcher | Status |
|---------|-----------|-------------|--------|
| `Season1Disc1` (full word, no separator) | Yes | No — but `Season_1_Disc_1` works | Acceptable — rare without separators |
| `S1E1D1` (episode identifier) | Yes | No — extracts season and disc, ignores episode | Acceptable — uncommon format |
| Bare `s1d1` (no title prefix) | Returns `"S1D1"` | Returns `None` (requires separator before `S`) | Acceptable — real labels always have a title prefix |
| `Breaking.Bad.S02.D02` (dot separators) | Yes | Yes — **fixed in Task 1** (dot normalization) | Resolved |

If the first two edge cases prove important, they can be added to `arm_matcher`'s regex set in a follow-up.
