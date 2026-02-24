"""Tests for utility functions in arm.ripper.utils and arm.services.files."""
import os
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


class TestDatabaseUpdaterUI:
    """Test database_updater in arm/ui/utils.py."""

    def test_sets_attributes(self, app_context, sample_job):
        from arm.services.files import database_updater
        database_updater({'status': 'success', 'title': 'New Title'}, sample_job)
        assert sample_job.status == 'success'
        assert sample_job.title == 'New Title'

    def test_returns_true(self, app_context, sample_job):
        from arm.services.files import database_updater
        result = database_updater({'status': 'success'}, sample_job)
        assert result is True

    def test_commits_to_db(self, app_context, sample_job):
        from arm.services.files import database_updater
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


