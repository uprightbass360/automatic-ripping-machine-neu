"""Tests for arm_ripper.py dispatch logic and post-processing functions."""
import unittest.mock

import pytest


class TestStartTranscode:
    """Test start_transcode() dispatch to correct transcoder."""

    def _make_job(self, **overrides):
        """Build a mock job with configurable attributes."""
        job = unittest.mock.MagicMock()
        job.config.SKIP_TRANSCODE = overrides.get('skip_transcode', False)
        job.config.USE_FFMPEG = overrides.get('use_ffmpeg', False)
        job.config.RIPMETHOD = overrides.get('ripmethod', 'mkv')
        job.config.MAINFEATURE = overrides.get('mainfeature', False)
        job.video_type = overrides.get('video_type', 'movie')
        job.hasnicetitle = overrides.get('hasnicetitle', True)
        job.disctype = overrides.get('disctype', 'bluray')
        return job

    def test_skip_transcode_returns_none(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(skip_transcode=True)
        result = start_transcode(job, "test.log", "/raw", "/out", 0)
        assert result is None

    def test_ffmpeg_mkv_dispatch(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(use_ffmpeg=True, disctype='bluray', ripmethod='mkv')

        with unittest.mock.patch('arm.ripper.arm_ripper.ffmpeg') as mock_ff, \
             unittest.mock.patch('arm.ripper.arm_ripper.utils'):
            result = start_transcode(job, "test.log", "/raw", "/out", 0)
            mock_ff.ffmpeg_mkv.assert_called_once_with("/raw", "/out", job)
            assert result is True

    def test_ffmpeg_main_feature_dispatch(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(
            use_ffmpeg=True, disctype='dvd', ripmethod='backup',
            mainfeature=True, video_type='movie', hasnicetitle=True,
        )

        with unittest.mock.patch('arm.ripper.arm_ripper.ffmpeg') as mock_ff, \
             unittest.mock.patch('arm.ripper.arm_ripper.utils'), \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            result = start_transcode(job, "test.log", "/dev/sr0", "/out", 0)
            mock_ff.ffmpeg_main_feature.assert_called_once()
            assert result is True

    def test_ffmpeg_all_dispatch(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(
            use_ffmpeg=True, disctype='dvd', ripmethod='backup',
            mainfeature=False, video_type='series',
        )

        with unittest.mock.patch('arm.ripper.arm_ripper.ffmpeg') as mock_ff, \
             unittest.mock.patch('arm.ripper.arm_ripper.utils'), \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            result = start_transcode(job, "test.log", "/dev/sr0", "/out", 0)
            mock_ff.ffmpeg_all.assert_called_once()
            assert result is True

    def test_handbrake_mkv_dispatch(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(use_ffmpeg=False, disctype='bluray', ripmethod='mkv')

        with unittest.mock.patch('arm.ripper.arm_ripper.handbrake') as mock_hb, \
             unittest.mock.patch('arm.ripper.arm_ripper.utils'):
            result = start_transcode(job, "test.log", "/raw", "/out", 0)
            mock_hb.handbrake_mkv.assert_called_once_with("/raw", "/out", "test.log", job)
            assert result is True

    def test_handbrake_main_feature_dispatch(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(
            use_ffmpeg=False, disctype='dvd', ripmethod='backup',
            mainfeature=True, video_type='movie', hasnicetitle=True,
        )

        with unittest.mock.patch('arm.ripper.arm_ripper.handbrake') as mock_hb, \
             unittest.mock.patch('arm.ripper.arm_ripper.utils'), \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            result = start_transcode(job, "test.log", "/dev/sr0", "/out", 0)
            mock_hb.handbrake_main_feature.assert_called_once()
            assert result is True

    def test_handbrake_all_dispatch(self):
        from arm.ripper.arm_ripper import start_transcode

        job = self._make_job(
            use_ffmpeg=False, disctype='dvd', ripmethod='backup',
            mainfeature=False, video_type='series',
        )

        with unittest.mock.patch('arm.ripper.arm_ripper.handbrake') as mock_hb, \
             unittest.mock.patch('arm.ripper.arm_ripper.utils'), \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            result = start_transcode(job, "test.log", "/dev/sr0", "/out", 0)
            mock_hb.handbrake_all.assert_called_once()
            assert result is True


class TestNotifyExit:
    """Test notify_exit() message formatting."""

    def test_success_notification(self):
        from arm.ripper.arm_ripper import notify_exit

        job = unittest.mock.MagicMock()
        job.config.NOTIFY_TRANSCODE = True
        job.errors = None
        job.title = "Serial Mom"

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils:
            notify_exit(job)
            mock_utils.notify.assert_called_once()
            call_args = mock_utils.notify.call_args[0]
            assert "Serial Mom" in call_args[2]
            assert "processing completed" not in call_args[2].lower() or "error" not in call_args[2].lower()

    def test_error_notification(self):
        from arm.ripper.arm_ripper import notify_exit

        job = unittest.mock.MagicMock()
        job.config.NOTIFY_TRANSCODE = True
        job.errors = ["title_03.mkv", "title_07.mkv"]
        job.title = "Serial Mom"

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils:
            notify_exit(job)
            mock_utils.notify.assert_called_once()
            call_args = mock_utils.notify.call_args[0]
            assert "errors" in call_args[2].lower()
            assert "title_03.mkv" in call_args[2]

    def test_no_notification_when_disabled(self):
        from arm.ripper.arm_ripper import notify_exit

        job = unittest.mock.MagicMock()
        job.config.NOTIFY_TRANSCODE = False

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils:
            notify_exit(job)
            mock_utils.notify.assert_not_called()


class TestSkipTranscodeMovie:
    """Test skip_transcode_movie() file routing logic."""

    def test_largest_file_is_main_feature(self, tmp_path):
        from arm.ripper.arm_ripper import skip_transcode_movie

        # Create test files
        (tmp_path / "small.mkv").write_bytes(b"x" * 100)
        (tmp_path / "large.mkv").write_bytes(b"x" * 10000)
        (tmp_path / "medium.mkv").write_bytes(b"x" * 5000)

        job = unittest.mock.MagicMock()
        job.video_type = "movie"
        job.config.MAINFEATURE = False
        job.config.EXTRAS_SUB = "extras"

        files = ["small.mkv", "large.mkv", "medium.mkv"]

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils:
            # find_largest_file must return a real filename
            mock_utils.find_largest_file.return_value = "large.mkv"
            skip_transcode_movie(files, job, str(tmp_path))

            # large.mkv should be moved as main feature (is_main_feature=True)
            calls = mock_utils.move_files.call_args_list
            main_calls = [c for c in calls if c[0][1] == "large.mkv"]
            assert len(main_calls) == 1
            assert main_calls[0][0][3] is True  # is_main_feature=True

    def test_mainfeature_skips_extras(self, tmp_path):
        from arm.ripper.arm_ripper import skip_transcode_movie

        (tmp_path / "main.mkv").write_bytes(b"x" * 10000)
        (tmp_path / "extra.mkv").write_bytes(b"x" * 100)

        job = unittest.mock.MagicMock()
        job.video_type = "movie"
        job.config.MAINFEATURE = True
        job.config.EXTRAS_SUB = "extras"

        files = ["main.mkv", "extra.mkv"]

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils:
            mock_utils.find_largest_file.return_value = "main.mkv"
            skip_transcode_movie(files, job, str(tmp_path))

            # Only main.mkv should be moved (extras skipped due to MAINFEATURE=True)
            assert mock_utils.move_files.call_count == 1

    def test_extras_sub_none_skips_extras(self, tmp_path):
        from arm.ripper.arm_ripper import skip_transcode_movie

        (tmp_path / "main.mkv").write_bytes(b"x" * 10000)
        (tmp_path / "extra.mkv").write_bytes(b"x" * 100)

        job = unittest.mock.MagicMock()
        job.video_type = "movie"
        job.config.MAINFEATURE = False
        job.config.EXTRAS_SUB = "none"

        files = ["main.mkv", "extra.mkv"]

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils:
            mock_utils.find_largest_file.return_value = "main.mkv"
            skip_transcode_movie(files, job, str(tmp_path))

            # Only main.mkv moved; extra skipped because EXTRAS_SUB is "none"
            assert mock_utils.move_files.call_count == 1
