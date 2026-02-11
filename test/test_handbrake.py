"""Tests for HandBrake pure-logic functions (arm/ripper/handbrake.py)."""
import os
import re
import subprocess
import unittest.mock

import pytest


class TestBuildHandbrakeCommand:
    """Test build_handbrake_command() returns a list of arguments."""

    def test_basic_command(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/output/title.mkv",
            hb_preset="Fast 1080p30",
            hb_args="--no-opencl",
        )
        assert isinstance(cmd, list)
        assert "-i" in cmd
        assert "/dev/sr0" in cmd
        assert "-o" in cmd
        assert "/output/title.mkv" in cmd
        assert "--preset" in cmd
        assert "Fast 1080p30" in cmd
        assert "--no-opencl" in cmd

    def test_main_feature_flag(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="",
            hb_args="",
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
        )
        assert "--main-feature" not in cmd

    def test_track_number(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/title_3.mkv",
            hb_preset="preset",
            hb_args="",
            track_number=3,
        )
        assert "-t" in cmd
        idx = cmd.index("-t")
        assert cmd[idx + 1] == "3"

    def test_no_track_number(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="preset",
            hb_args="",
        )
        assert "-t" not in cmd

    def test_empty_preset_omitted(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="",
            hb_args="",
        )
        assert "--preset" not in cmd

    def test_paths_with_spaces_preserved(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/media/My Movies/disc",
            filepathname="/out/My Movie.mkv",
            hb_preset="",
            hb_args="",
        )
        # List args preserve spaces without shell quoting
        assert "/media/My Movies/disc" in cmd
        assert "/out/My Movie.mkv" in cmd

    def test_single_quote_in_path_safe(self):
        """Paths with single quotes don't break the command (#1457)."""
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/Tom Clancy's Jack Ryan.mkv",
            hb_preset="HQ 480p30 Surround",
            hb_args="--subtitle-lang-list eng",
        )
        assert "/out/Tom Clancy's Jack Ryan.mkv" in cmd
        assert "HQ 480p30 Surround" in cmd

    def test_compound_hb_args_split(self):
        """Multiple hb_args in a single string are split correctly."""
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            srcpath="/dev/sr0",
            filepathname="/out/movie.mkv",
            hb_preset="",
            hb_args="--subtitle-lang-list eng --all-subtitles --subtitle-burned=none",
        )
        assert "--subtitle-lang-list" in cmd
        assert "eng" in cmd
        assert "--all-subtitles" in cmd
        assert "--subtitle-burned=none" in cmd


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


class TestRunHandbrakeCommand:
    """Test run_handbrake_command() subprocess execution and log redirection (#1457)."""

    def test_output_written_to_logfile(self, tmp_path):
        from arm.ripper.handbrake import run_handbrake_command

        logfile = str(tmp_path / "test.log")
        cmd = ["echo", "HandBrake output line"]
        run_handbrake_command(cmd, logfile)

        with open(logfile) as f:
            content = f.read()
        assert "HandBrake output line" in content

    def test_logfile_with_single_quote_in_name(self, tmp_path):
        """Single quote in logfile path doesn't break redirection (#1457)."""
        from arm.ripper.handbrake import run_handbrake_command

        logfile = str(tmp_path / "TOM_CLANCY'S_JACK_RYAN.log")
        cmd = ["echo", "transcoding output"]
        run_handbrake_command(cmd, logfile)

        with open(logfile) as f:
            content = f.read()
        assert "transcoding output" in content

    def test_track_status_set_on_success(self, tmp_path):
        from arm.ripper.handbrake import run_handbrake_command

        logfile = str(tmp_path / "test.log")
        track = unittest.mock.MagicMock()
        run_handbrake_command(["true"], logfile, track=track)
        assert track.status == "success"

    def test_track_status_set_on_failure(self, tmp_path):
        from arm.ripper.handbrake import run_handbrake_command

        logfile = str(tmp_path / "test.log")
        track = unittest.mock.MagicMock()
        with pytest.raises(subprocess.CalledProcessError):
            run_handbrake_command(["false"], logfile, track=track, track_number=1)
        assert track.status == "fail"
        assert "title 1" in track.error

    def test_appends_to_existing_logfile(self, tmp_path):
        from arm.ripper.handbrake import run_handbrake_command

        logfile = str(tmp_path / "test.log")
        with open(logfile, "w") as f:
            f.write("existing content\n")

        run_handbrake_command(["echo", "new line"], logfile)

        with open(logfile) as f:
            content = f.read()
        assert "existing content" in content
        assert "new line" in content
