"""Tests for ripping business logic (no hardware required)."""
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
