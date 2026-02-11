"""Tests for utility functions in arm.ripper.utils and arm.ui.utils."""
import os
import subprocess
import unittest.mock

import pytest


class TestCleanForFilename:
    """Test clean_for_filename() string sanitization."""

    def test_simple_title(self):
        from arm.ripper.utils import clean_for_filename
        assert clean_for_filename("Serial Mom") == "Serial-Mom"

    def test_brackets_removed(self):
        from arm.ripper.utils import clean_for_filename
        assert "Rated" not in clean_for_filename("Serial Mom [Rated R]")

    def test_colon_replaced(self):
        from arm.ripper.utils import clean_for_filename
        result = clean_for_filename("Star Wars: A New Hope")
        assert ":" not in result

    def test_ampersand_replaced(self):
        from arm.ripper.utils import clean_for_filename
        result = clean_for_filename("Tom & Jerry")
        assert "&" not in result
        assert "and" in result

    def test_special_chars_stripped(self):
        from arm.ripper.utils import clean_for_filename
        result = clean_for_filename("Movie! @#$% Title")
        # Only word chars, dots, parens, spaces, hyphens allowed
        assert all(c.isalnum() or c in '.() -_' for c in result)

    def test_empty_string(self):
        from arm.ripper.utils import clean_for_filename
        assert clean_for_filename("") == ""

    def test_preserves_year_parens(self):
        from arm.ripper.utils import clean_for_filename
        result = clean_for_filename("Serial Mom (1994)")
        assert "(1994)" in result


class TestConvertJobType:
    """Test convert_job_type() folder mapping."""

    def test_movie(self):
        from arm.ripper.utils import convert_job_type
        assert convert_job_type("movie") == "movies"

    def test_series(self):
        from arm.ripper.utils import convert_job_type
        assert convert_job_type("series") == "tv"

    def test_unknown(self):
        from arm.ripper.utils import convert_job_type
        assert convert_job_type("unknown") == "unidentified"

    def test_empty(self):
        from arm.ripper.utils import convert_job_type
        assert convert_job_type("") == "unidentified"


class TestFixJobTitle:
    """Test fix_job_title() delegates to job.formatted_title."""

    def test_delegates_to_formatted_title(self, sample_job):
        from arm.ripper.utils import fix_job_title
        assert fix_job_title(sample_job) == sample_job.formatted_title

    def test_with_manual_title(self, sample_job):
        from arm.ripper.utils import fix_job_title
        sample_job.title_manual = "Serial Mom"
        assert fix_job_title(sample_job) == "Serial Mom (1994)"


class TestDatabaseUpdaterUI:
    """Test database_updater in arm/ui/utils.py."""

    def test_sets_attributes(self, app_context, sample_job):
        from arm.ui.utils import database_updater
        database_updater({'status': 'success', 'title': 'New Title'}, sample_job)
        assert sample_job.status == 'success'
        assert sample_job.title == 'New Title'

    def test_returns_true(self, app_context, sample_job):
        from arm.ui.utils import database_updater
        result = database_updater({'status': 'success'}, sample_job)
        assert result is True

    def test_commits_to_db(self, app_context, sample_job):
        from arm.ui.utils import database_updater
        from arm.database import db
        database_updater({'status': 'success'}, sample_job)
        db.session.refresh(sample_job)
        assert sample_job.status == 'success'


class TestDatabaseUpdaterRipper:
    """Test database_updater in arm/ripper/utils.py (with break and rollback)."""

    def test_non_dict_rollback(self, app_context, sample_job):
        """Passing non-dict triggers rollback and returns False."""
        from arm.ripper.utils import database_updater
        result = database_updater("not a dict", sample_job)
        assert result is False

    def test_non_dict_none(self, app_context, sample_job):
        from arm.ripper.utils import database_updater
        result = database_updater(None, sample_job)
        assert result is False

    def test_sets_multiple_attrs(self, app_context, sample_job):
        from arm.ripper.utils import database_updater
        from arm.database import db
        database_updater({
            'status': 'success',
            'raw_path': '/test/raw',
            'transcode_path': '/test/transcode',
        }, sample_job)
        db.session.refresh(sample_job)
        assert sample_job.status == 'success'
        assert sample_job.raw_path == '/test/raw'
        assert sample_job.transcode_path == '/test/transcode'


class TestDatabaseAdder:
    """Test database_adder in arm/ripper/utils.py."""

    def test_adds_object(self, app_context):
        from arm.ripper.utils import database_adder
        from arm.models.job import Job
        from arm.database import db

        with unittest.mock.patch.object(Job, 'parse_udev'), \
             unittest.mock.patch.object(Job, 'get_pid'):
            job = Job('/dev/sr0')
        job.title = "TEST_ADDER"
        job.title_auto = "TEST_ADDER"
        job.label = "TEST_ADDER"

        result = database_adder(job)
        assert result is True
        assert job.job_id is not None

        found = db.session.get(Job, job.job_id)
        assert found is not None
        assert found.title == "TEST_ADDER"


class TestFindLargestFile:
    """Test find_largest_file() file size comparison."""

    def test_finds_largest(self, tmp_path):
        from arm.ripper.utils import find_largest_file
        # Create files of different sizes
        (tmp_path / "small.mkv").write_bytes(b"x" * 100)
        (tmp_path / "large.mkv").write_bytes(b"x" * 10000)
        (tmp_path / "medium.mkv").write_bytes(b"x" * 5000)

        files = ["small.mkv", "large.mkv", "medium.mkv"]
        result = find_largest_file(files, str(tmp_path))
        assert result == "large.mkv"

    def test_single_file(self, tmp_path):
        from arm.ripper.utils import find_largest_file
        (tmp_path / "only.mkv").write_bytes(b"x" * 100)

        result = find_largest_file(["only.mkv"], str(tmp_path))
        assert result == "only.mkv"

    def test_equal_sizes(self, tmp_path):
        from arm.ripper.utils import find_largest_file
        (tmp_path / "a.mkv").write_bytes(b"x" * 100)
        (tmp_path / "b.mkv").write_bytes(b"x" * 100)

        result = find_largest_file(["a.mkv", "b.mkv"], str(tmp_path))
        # Should return one of them (first stays since not strictly greater)
        assert result in ("a.mkv", "b.mkv")


class TestConfigModel:
    """Test Config model initialization and methods."""

    def test_init_from_dict(self, app_context):
        from arm.models.config import Config
        config = Config({
            'RAW_PATH': '/test/raw',
            'COMPLETED_PATH': '/test/completed',
            'SKIP_TRANSCODE': False,
        }, job_id=1)
        assert config.RAW_PATH == '/test/raw'
        assert config.COMPLETED_PATH == '/test/completed'
        assert config.SKIP_TRANSCODE is False
        assert config.job_id == 1

    def test_str_masks_sensitive(self, app_context):
        from arm.models.config import Config
        config = Config({
            'OMDB_API_KEY': 'secret123',
            'RAW_PATH': '/test/raw',
        }, job_id=1)
        result = str(config)
        assert 'secret123' not in result
        assert '/test/raw' in result


class TestCalculateFilenameSimilarity:
    """Test _calculate_filename_similarity() fuzzy matching algorithm."""

    def test_identical_strings(self):
        from arm.ripper.utils import _calculate_filename_similarity
        score = _calculate_filename_similarity("FiveArmies", "FiveArmies")
        assert score > 0

    def test_off_by_one(self):
        from arm.ripper.utils import _calculate_filename_similarity
        score = _calculate_filename_similarity("FiveArmies", "FiveArmiess")
        # Should score highly — only 1 char difference
        assert score >= len("FiveArmies") * 0.8

    def test_completely_different(self):
        from arm.ripper.utils import _calculate_filename_similarity
        score = _calculate_filename_similarity("FiveArmies", "ZZZZZZZ")
        # Very low score
        assert score < len("FiveArmies") * 0.5

    def test_prefix_match(self):
        from arm.ripper.utils import _calculate_filename_similarity
        # "title_01" vs "title_01x" — matches from start, slight difference at end
        score = _calculate_filename_similarity("title_01", "title_01x")
        assert score >= 8  # 8 chars match from start

    def test_empty_strings(self):
        from arm.ripper.utils import _calculate_filename_similarity
        score = _calculate_filename_similarity("", "")
        # Both empty — length bonus for 0 diff
        assert score >= 0

    def test_length_bonus_same_length(self):
        from arm.ripper.utils import _calculate_filename_similarity
        score_same = _calculate_filename_similarity("abc", "xbc")
        score_diff = _calculate_filename_similarity("abc", "xbcdefgh")
        # Same-length pair should get length bonus, different shouldn't
        assert score_same > score_diff

    def test_symmetry(self):
        from arm.ripper.utils import _calculate_filename_similarity
        s1 = _calculate_filename_similarity("hello", "helloo")
        s2 = _calculate_filename_similarity("helloo", "hello")
        assert s1 == s2


class TestPutTrack:
    """Test put_track() Track object creation."""

    def test_creates_track(self, app_context, sample_job):
        from arm.ripper.utils import put_track
        from arm.models.track import Track

        put_track(sample_job, 1, 3600, "16:9", 24.0, True, "HandBrake", "title_01.mkv")

        tracks = Track.query.filter_by(job_id=sample_job.job_id).all()
        assert len(tracks) == 1
        assert str(tracks[0].track_number) == '1'
        assert tracks[0].length == 3600
        assert tracks[0].main_feature is True

    def test_ripped_flag_based_on_minlength(self, app_context, sample_job):
        from arm.ripper.utils import put_track
        from arm.models.track import Track

        # MINLENGTH is 600 in sample_job config
        put_track(sample_job, 1, 700, "16:9", 24.0, False, "MakeMKV")
        put_track(sample_job, 2, 100, "16:9", 24.0, False, "MakeMKV")

        tracks = Track.query.filter_by(job_id=sample_job.job_id).order_by(Track.track_number).all()
        assert tracks[0].ripped is True   # 700 > 600
        assert tracks[1].ripped is False  # 100 < 600


class TestMakeDir:
    """Test make_dir() directory creation."""

    def test_creates_new_dir(self, tmp_path):
        from arm.ripper.utils import make_dir

        new_dir = str(tmp_path / "new_folder")
        result = make_dir(new_dir)
        assert result is True
        assert os.path.isdir(new_dir)

    def test_existing_dir_returns_false(self, tmp_path):
        from arm.ripper.utils import make_dir

        existing = str(tmp_path / "existing")
        os.makedirs(existing)
        result = make_dir(existing)
        assert result is False

    def test_nested_dirs(self, tmp_path):
        from arm.ripper.utils import make_dir

        nested = str(tmp_path / "a" / "b" / "c")
        result = make_dir(nested)
        assert result is True
        assert os.path.isdir(nested)


class TestSleepCheckProcess:
    """Test sleep_check_process() queue management."""

    def test_disabled_when_zero(self):
        from arm.ripper.utils import sleep_check_process

        result = sleep_check_process("HandBrakeCLI", 0)
        assert result is False

    def test_returns_true_when_below_limit(self):
        from arm.ripper.utils import sleep_check_process

        # With max=100 and no HandBrakeCLI running, should return immediately
        result = sleep_check_process("HandBrakeCLI", 100, sleep=(0, 1, 1))
        assert result is True

    def test_invalid_sleep_raises(self):
        from arm.ripper.utils import sleep_check_process

        with pytest.raises(TypeError):
            sleep_check_process("HandBrakeCLI", 1, sleep="invalid")


class TestCheckIp:
    """Test check_ip() IP selection logic."""

    def test_configured_ip_returned(self):
        from arm.ripper.utils import check_ip
        import arm.config.config as cfg

        original = cfg.arm_config.get('WEBSERVER_IP')
        cfg.arm_config['WEBSERVER_IP'] = '192.168.1.50'
        try:
            result = check_ip()
            assert result == '192.168.1.50'
        finally:
            if original is not None:
                cfg.arm_config['WEBSERVER_IP'] = original

    def test_autodetect_skips_placeholder(self):
        from arm.ripper.utils import check_ip
        import arm.config.config as cfg

        original = cfg.arm_config.get('WEBSERVER_IP')
        cfg.arm_config['WEBSERVER_IP'] = 'x.x.x.x'
        try:
            result = check_ip()
            # Should be a valid IP (either autodetected or 127.0.0.1 fallback)
            assert '.' in result
        finally:
            if original is not None:
                cfg.arm_config['WEBSERVER_IP'] = original


class TestDeleteRawFiles:
    """Test delete_raw_files() cleanup."""

    def test_deletes_when_enabled(self, tmp_path):
        from arm.ripper.utils import delete_raw_files
        import arm.config.config as cfg

        original = cfg.arm_config.get('DELRAWFILES')
        cfg.arm_config['DELRAWFILES'] = True

        raw_dir = str(tmp_path / "raw_files")
        os.makedirs(raw_dir)
        (tmp_path / "raw_files" / "title.mkv").write_bytes(b"x" * 100)

        try:
            delete_raw_files([raw_dir])
            assert not os.path.exists(raw_dir)
        finally:
            cfg.arm_config['DELRAWFILES'] = original if original is not None else False

    def test_skips_when_disabled(self, tmp_path):
        from arm.ripper.utils import delete_raw_files
        import arm.config.config as cfg

        original = cfg.arm_config.get('DELRAWFILES')
        cfg.arm_config['DELRAWFILES'] = False

        raw_dir = str(tmp_path / "raw_files")
        os.makedirs(raw_dir)

        try:
            delete_raw_files([raw_dir])
            assert os.path.exists(raw_dir)
        finally:
            cfg.arm_config['DELRAWFILES'] = original if original is not None else False

    def test_handles_nonexistent_dir(self, tmp_path):
        from arm.ripper.utils import delete_raw_files
        import arm.config.config as cfg

        original = cfg.arm_config.get('DELRAWFILES')
        cfg.arm_config['DELRAWFILES'] = True
        try:
            # Should not raise
            delete_raw_files([str(tmp_path / "nonexistent")])
        finally:
            cfg.arm_config['DELRAWFILES'] = original if original is not None else False


class TestGitCheckVersion:
    """Test git_check_version() resilience to missing origin/HEAD (#1345)."""

    def test_fallback_to_origin_main(self):
        """When origin/HEAD fails, should fall back to origin/main."""
        from arm.ui.utils import git_check_version
        import arm.config.config as cfg

        original = cfg.arm_config.get('INSTALLPATH')
        cfg.arm_config['INSTALLPATH'] = '/opt/arm'

        call_count = 0

        def mock_check_output(cmd, cwd=None, stderr=None):
            nonlocal call_count
            call_count += 1
            if 'origin/HEAD' in cmd[2]:
                raise subprocess.CalledProcessError(128, cmd)
            if 'origin/main' in cmd[2]:
                return b'2.21.0\n'
            raise subprocess.CalledProcessError(128, cmd)

        try:
            with unittest.mock.patch('subprocess.check_output', side_effect=mock_check_output), \
                 unittest.mock.patch('builtins.open', unittest.mock.mock_open(read_data='2.20.0\n')):
                local_ver, remote_ver = git_check_version()
            assert local_ver == '2.20.0'
            assert remote_ver == '2.21.0'
            assert call_count == 2  # origin/HEAD failed, origin/main succeeded
        finally:
            cfg.arm_config['INSTALLPATH'] = original

    def test_all_refs_fail_returns_unknown(self):
        """When all git refs fail, remote version should be 'Unknown'."""
        from arm.ui.utils import git_check_version
        import arm.config.config as cfg

        original = cfg.arm_config.get('INSTALLPATH')
        cfg.arm_config['INSTALLPATH'] = '/opt/arm'

        def mock_check_output(cmd, cwd=None, stderr=None):
            raise subprocess.CalledProcessError(128, cmd)

        try:
            with unittest.mock.patch('subprocess.check_output', side_effect=mock_check_output), \
                 unittest.mock.patch('builtins.open', unittest.mock.mock_open(read_data='2.20.0\n')):
                local_ver, remote_ver = git_check_version()
            assert remote_ver == 'Unknown'
        finally:
            cfg.arm_config['INSTALLPATH'] = original

    def test_missing_version_file_returns_unknown(self):
        """When VERSION file is missing, local version should be 'Unknown'."""
        from arm.ui.utils import git_check_version
        import arm.config.config as cfg

        original = cfg.arm_config.get('INSTALLPATH')
        cfg.arm_config['INSTALLPATH'] = '/opt/arm'

        def mock_check_output(cmd, cwd=None, stderr=None):
            return b'2.21.0\n'

        try:
            with unittest.mock.patch('subprocess.check_output', side_effect=mock_check_output), \
                 unittest.mock.patch('builtins.open', side_effect=FileNotFoundError):
                local_ver, remote_ver = git_check_version()
            assert local_ver == 'Unknown'
        finally:
            cfg.arm_config['INSTALLPATH'] = original
