"""Tests for HandBrake pure-logic functions (arm/ripper/handbrake.py)."""
import re
import unittest.mock

import pytest


class TestBuildHandbrakeCommand:
    """Test build_handbrake_command() command string construction."""

    def test_basic_command(self):
        from arm.ripper.handbrake import build_handbrake_command
        import arm.config.config as cfg

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/output/title.mkv",
            hb_preset="Fast 1080p30",
            hb_args="--no-opencl",
            logfile="/tmp/arm.log",
        )
        assert f"-i {'/dev/sr0'}" in cmd or "-i '/dev/sr0'" in cmd
        assert f"-o {'/output/title.mkv'}" in cmd or "-o '/output/title.mkv'" in cmd
        assert '--preset "Fast 1080p30"' in cmd
        assert "--no-opencl" in cmd
        assert ">> /tmp/arm.log 2>&1" in cmd

    def test_main_feature_flag(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="",
            hb_args="",
            logfile="/tmp/arm.log",
            main_feature=True,
        )
        assert "--main-feature" in cmd

    def test_no_main_feature_by_default(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="preset",
            hb_args="",
            logfile="/tmp/arm.log",
        )
        assert "--main-feature" not in cmd

    def test_track_number(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/title_3.mkv",
            hb_preset="preset",
            hb_args="",
            logfile="/tmp/arm.log",
            track_number=3,
        )
        assert "-t 3" in cmd

    def test_no_track_number(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="preset",
            hb_args="",
            logfile="/tmp/arm.log",
        )
        assert "-t " not in cmd

    def test_empty_preset_omitted(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="",
            hb_args="",
            logfile="/tmp/arm.log",
        )
        assert "--preset" not in cmd

    def test_path_with_spaces_quoted(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/media/My Movies/disc",
            filepathname="/out/My Movie.mkv",
            hb_preset="",
            hb_args="",
            logfile="/tmp/arm.log",
        )
        # shlex.quote wraps paths with spaces in single quotes
        assert "'/media/My Movies/disc'" in cmd
        assert "'/out/My Movie.mkv'" in cmd


class TestCorrectHbSettings:
    """Test correct_hb_settings() preset selection."""

    def _make_job(self, disctype):
        job = unittest.mock.MagicMock()
        job.disctype = disctype
        job.config.HB_ARGS_DVD = "--dvd-args"
        job.config.HB_PRESET_DVD = "DVD Preset"
        job.config.HB_ARGS_BD = "--bd-args"
        job.config.HB_PRESET_BD = "BD Preset"
        return job

    def test_dvd_settings(self):
        from arm.ripper.handbrake import correct_hb_settings

        job = self._make_job("dvd")
        args, preset = correct_hb_settings(job)
        assert args == "--dvd-args"
        assert preset == "DVD Preset"

    def test_bluray_settings(self):
        from arm.ripper.handbrake import correct_hb_settings

        job = self._make_job("bluray")
        args, preset = correct_hb_settings(job)
        assert args == "--bd-args"
        assert preset == "BD Preset"

    def test_unknown_disctype_returns_empty(self):
        from arm.ripper.handbrake import correct_hb_settings

        job = self._make_job("music")
        args, preset = correct_hb_settings(job)
        assert args == ""
        assert preset == ""


class TestIsMainFeature:
    """Test is_main_feature() boolean detection."""

    def test_main_feature_found(self):
        from arm.ripper.handbrake import is_main_feature

        result = is_main_feature("  + Main Feature", False)
        assert result is True

    def test_main_feature_not_found(self):
        from arm.ripper.handbrake import is_main_feature

        result = is_main_feature("  + duration: 01:30:00", False)
        assert result is False

    def test_preserves_existing_true(self):
        from arm.ripper.handbrake import is_main_feature

        result = is_main_feature("  + some other line", True)
        # Previous True is preserved (not reset)
        assert result is True

    def test_sets_true_from_false(self):
        from arm.ripper.handbrake import is_main_feature

        result = is_main_feature("Main Feature detected", False)
        assert result is True


class TestSecondsBuilder:
    """Test seconds_builder() duration extraction."""

    def test_parses_duration(self):
        from arm.ripper.handbrake import seconds_builder

        pattern = re.compile(r'.*duration:.*')
        result = seconds_builder("  + duration: 01:30:45", pattern, 0)
        assert result == 1 * 3600 + 30 * 60 + 45

    def test_short_duration(self):
        from arm.ripper.handbrake import seconds_builder

        pattern = re.compile(r'.*duration:.*')
        result = seconds_builder("  + duration: 00:05:30", pattern, 0)
        assert result == 5 * 60 + 30

    def test_non_matching_line_preserves_seconds(self):
        from arm.ripper.handbrake import seconds_builder

        pattern = re.compile(r'.*duration:.*')
        result = seconds_builder("  + some other line", pattern, 999)
        assert result == 999


class TestTitleFinder:
    """Test title_finder() track number extraction."""

    def test_finds_title_number(self):
        from arm.ripper.handbrake import title_finder

        t_pattern = re.compile(r'.*\+ title *')
        # First title (t_no starts at 0, no put_track call)
        main_feature, t_no = title_finder(0, 0.0, unittest.mock.MagicMock(),
                                           "  + title 1:", False, 0, 0, t_pattern)
        assert t_no == "1"
        assert main_feature is False

    def test_resets_main_feature_on_new_title(self):
        from arm.ripper.handbrake import title_finder

        t_pattern = re.compile(r'.*\+ title *')
        # Simulate finding second title after first was main
        with unittest.mock.patch('arm.ripper.handbrake.utils'):
            main_feature, t_no = title_finder(0, 0.0, unittest.mock.MagicMock(),
                                               "  + title 2:", True, 100, 1, t_pattern)
        assert t_no == "2"
        assert main_feature is False  # reset on new title

    def test_non_matching_line_returns_unchanged(self):
        from arm.ripper.handbrake import title_finder

        t_pattern = re.compile(r'.*\+ title *')
        main_feature, t_no = title_finder(0, 0.0, unittest.mock.MagicMock(),
                                           "  + duration: 01:30:00", True, 100, 5, t_pattern)
        assert t_no == 5
        assert main_feature is True
