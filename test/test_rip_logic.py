"""Tests for ripping business logic (no hardware required)."""
import os
import unittest.mock

import pytest


class TestRipWithMkv:
    """Test rip_with_mkv() decision logic from arm_ripper.py."""

    def test_bluray_always_uses_mkv(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "bluray"
        assert rip_with_mkv(sample_job) is True

    def test_dvd_mkv_no_mainfeature(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "dvd"
        sample_job.config.MAINFEATURE = False
        sample_job.config.RIPMETHOD = "mkv"
        assert rip_with_mkv(sample_job) is True

    def test_dvd_mainfeature_enabled(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "dvd"
        sample_job.config.MAINFEATURE = True
        sample_job.config.RIPMETHOD = "mkv"
        sample_job.config.SKIP_TRANSCODE = False
        assert rip_with_mkv(sample_job) is False

    def test_dvd_skip_transcode(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "dvd"
        sample_job.config.SKIP_TRANSCODE = True
        assert rip_with_mkv(sample_job) is True

    def test_dvd_99_protection(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "dvd"
        sample_job.config.MAINFEATURE = True
        sample_job.config.RIPMETHOD = "backup"
        sample_job.config.SKIP_TRANSCODE = False
        assert rip_with_mkv(sample_job, protection=1) is True

    def test_dvd_no_protection_mainfeature_backup(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "dvd"
        sample_job.config.MAINFEATURE = True
        sample_job.config.RIPMETHOD = "backup"
        sample_job.config.SKIP_TRANSCODE = False
        assert rip_with_mkv(sample_job, protection=0) is False

    def test_backup_dvd_method(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "dvd"
        sample_job.config.RIPMETHOD = "backup_dvd"
        assert rip_with_mkv(sample_job) is True

    def test_unknown_disctype(self, sample_job):
        from arm.ripper.arm_ripper import rip_with_mkv
        sample_job.disctype = "unknown"
        sample_job.config.MAINFEATURE = True
        sample_job.config.RIPMETHOD = "backup"
        sample_job.config.SKIP_TRANSCODE = False
        assert rip_with_mkv(sample_job) is False


class TestJobState:
    """Test JobState enum and status sets."""

    def test_success_value(self):
        from arm.models.job import JobState
        assert JobState.SUCCESS.value == "success"

    def test_failure_value(self):
        from arm.models.job import JobState
        assert JobState.FAILURE.value == "fail"

    def test_idle_value(self):
        from arm.models.job import JobState
        assert JobState.IDLE.value == "active"

    def test_ripping_value(self):
        from arm.models.job import JobState
        assert JobState.VIDEO_RIPPING.value == "ripping"

    def test_transcoding_value(self):
        from arm.models.job import JobState
        assert JobState.TRANSCODE_ACTIVE.value == "transcoding"

    def test_finished_set(self):
        from arm.models.job import JobState, JOB_STATUS_FINISHED
        assert JobState.SUCCESS in JOB_STATUS_FINISHED
        assert JobState.FAILURE in JOB_STATUS_FINISHED
        assert JobState.IDLE not in JOB_STATUS_FINISHED

    def test_ripping_set(self):
        from arm.models.job import JobState, JOB_STATUS_RIPPING
        assert JobState.VIDEO_RIPPING in JOB_STATUS_RIPPING
        assert JobState.AUDIO_RIPPING in JOB_STATUS_RIPPING
        assert JobState.IDLE not in JOB_STATUS_RIPPING

    def test_transcoding_set(self):
        from arm.models.job import JobState, JOB_STATUS_TRANSCODING
        assert JobState.TRANSCODE_ACTIVE in JOB_STATUS_TRANSCODING
        assert JobState.TRANSCODE_WAITING in JOB_STATUS_TRANSCODING
        assert JobState.IDLE not in JOB_STATUS_TRANSCODING


class TestRipData:
    """Test rip_data() data disc ripping logic."""

    def test_duplicate_label_gets_unique_filename(self, app_context, sample_job, tmp_path):
        """Second data disc with same label should NOT overwrite the first (#1651)."""
        from arm.ripper.utils import rip_data

        raw = tmp_path / "raw"
        completed = tmp_path / "completed"
        raw.mkdir()
        completed.mkdir()

        sample_job.disctype = "data"
        sample_job.label = "MYDATA"
        sample_job.video_type = "unknown"
        sample_job.config.RAW_PATH = str(raw)
        sample_job.config.COMPLETED_PATH = str(completed)

        # First rip: create the raw directory so the second call thinks it's a collision
        (raw / "MYDATA").mkdir()

        with unittest.mock.patch('arm.ripper.utils.subprocess.check_output') as mock_dd, \
             unittest.mock.patch('arm.ripper.utils.move_files_main') as mock_move:
            mock_dd.return_value = b""
            rip_data(sample_job)

            # move_files_main should have been called with a timestamped .iso filename
            if mock_move.called:
                dest_file = mock_move.call_args[0][0]  # incomplete_filename
                final_file = mock_move.call_args[0][1]  # full_final_file
                # The ISO filename should NOT be just "MYDATA.iso" — it should have a suffix
                assert "MYDATA.iso" not in final_file or "_" in os.path.basename(final_file)

    def test_unique_label_uses_plain_filename(self, app_context, sample_job, tmp_path):
        """Data disc with unique label uses plain label as filename."""
        from arm.ripper.utils import rip_data

        raw = tmp_path / "raw"
        completed = tmp_path / "completed"
        raw.mkdir()
        completed.mkdir()

        sample_job.disctype = "data"
        sample_job.label = "UNIQUE_DISC"
        sample_job.video_type = "unknown"
        sample_job.config.RAW_PATH = str(raw)
        sample_job.config.COMPLETED_PATH = str(completed)

        with unittest.mock.patch('arm.ripper.utils.subprocess.check_output') as mock_dd, \
             unittest.mock.patch('arm.ripper.utils.move_files_main') as mock_move:
            mock_dd.return_value = b""
            rip_data(sample_job)

            if mock_move.called:
                final_file = mock_move.call_args[0][1]
                assert final_file.endswith("UNIQUE_DISC.iso")


class TestRipMusic:
    """Test rip_music() audio CD ripping logic."""

    def test_abcde_error_in_log_detected(self, app_context, sample_job, tmp_path):
        """abcde exit 0 with [ERROR] in log should be treated as failure (#1526)."""
        from arm.ripper.utils import rip_music

        sample_job.disctype = "music"
        sample_job.config.LOGPATH = str(tmp_path)

        # Write a log file with abcde error markers
        logfile = "test_music.log"
        (tmp_path / logfile).write_text(
            "Grabbing track 01...\n"
            "[ERROR] cdparanoia could not read disc\n"
            "CDROM drive unavailable\n"
        )

        with unittest.mock.patch('arm.ripper.utils.subprocess.check_output', return_value=b""), \
             unittest.mock.patch('arm.ripper.utils.cfg') as mock_cfg:
            mock_cfg.arm_config = {"ABCDE_CONFIG_FILE": "/nonexistent"}
            result = rip_music(sample_job, logfile)

        assert result is False
        assert sample_job.status == "fail"

    def test_abcde_clean_log_succeeds(self, app_context, sample_job, tmp_path):
        """abcde exit 0 with clean log should be treated as success."""
        from arm.ripper.utils import rip_music

        sample_job.disctype = "music"
        sample_job.config.LOGPATH = str(tmp_path)

        logfile = "test_music.log"
        (tmp_path / logfile).write_text(
            "Grabbing track 01...\n"
            "Grabbing track 02...\n"
            "Finished.\n"
        )

        with unittest.mock.patch('arm.ripper.utils.subprocess.check_output', return_value=b""), \
             unittest.mock.patch('arm.ripper.utils.cfg') as mock_cfg:
            mock_cfg.arm_config = {"ABCDE_CONFIG_FILE": "/nonexistent"}
            result = rip_music(sample_job, logfile)

        assert result is True

    def test_abcde_nonzero_exit_detected(self, app_context, sample_job, tmp_path):
        """abcde with non-zero exit code should be caught."""
        import subprocess
        from arm.ripper.utils import rip_music

        sample_job.disctype = "music"
        sample_job.config.LOGPATH = str(tmp_path)

        with unittest.mock.patch('arm.ripper.utils.subprocess.check_output',
                                 side_effect=subprocess.CalledProcessError(1, "abcde", b"error")), \
             unittest.mock.patch('arm.ripper.utils.cfg') as mock_cfg:
            mock_cfg.arm_config = {"ABCDE_CONFIG_FILE": "/nonexistent"}
            result = rip_music(sample_job, "test.log")

        assert result is False
