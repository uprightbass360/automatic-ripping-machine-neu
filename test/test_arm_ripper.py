"""Tests for arm_ripper.py dispatch logic and notification functions."""
import unittest.mock


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


class TestRipVisualMedia:
    """Test simplified rip_visual_media() flow: rip -> persist -> notify."""

    def _make_job(self, **overrides):
        """Build a mock job with configurable attributes."""
        job = unittest.mock.MagicMock()
        job.title = overrides.get('title', 'Test Movie')
        job.disctype = overrides.get('disctype', 'bluray')
        job.config.NOTIFY_RIP = overrides.get('notify_rip', True)
        job.config.NOTIFY_TRANSCODE = overrides.get('notify_transcode', True)
        job.config.MAINFEATURE = overrides.get('mainfeature', False)
        job.errors = overrides.get('errors', None)
        job.build_final_path.return_value = '/home/arm/media/completed/movies/Test Movie (2024)'
        return job

    def test_rip_calls_makemkv(self):
        from arm.ripper.arm_ripper import rip_visual_media

        job = self._make_job()

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils, \
             unittest.mock.patch('arm.ripper.arm_ripper.makemkv') as mock_mkv, \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            mock_utils.check_for_dupe_folder.return_value = '/home/arm/media/completed/movies/Test Movie (2024)'
            mock_mkv.makemkv.return_value = '/home/arm/media/raw/Test Movie (2024)'

            rip_visual_media(False, job, "test.log", 0)

            mock_mkv.makemkv.assert_called_once_with(job)

    def test_rip_persists_raw_path(self):
        from arm.ripper.arm_ripper import rip_visual_media

        job = self._make_job()
        raw_path = '/home/arm/media/raw/Test Movie (2024)'

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils, \
             unittest.mock.patch('arm.ripper.arm_ripper.makemkv') as mock_mkv, \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            mock_utils.check_for_dupe_folder.return_value = '/home/arm/media/completed/movies/Test Movie (2024)'
            mock_mkv.makemkv.return_value = raw_path

            rip_visual_media(False, job, "test.log", 0)

            # Verify raw_path was persisted to DB
            raw_path_calls = [
                c for c in mock_utils.database_updater.call_args_list
                if 'raw_path' in c[0][0]
            ]
            assert len(raw_path_calls) == 1
            assert raw_path_calls[0][0][0]['raw_path'] == raw_path

    def test_rip_sends_notification_on_completion(self):
        from arm.ripper.arm_ripper import rip_visual_media

        job = self._make_job(notify_rip=True)

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils, \
             unittest.mock.patch('arm.ripper.arm_ripper.makemkv') as mock_mkv, \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            mock_utils.check_for_dupe_folder.return_value = '/home/arm/media/completed/movies/Test Movie (2024)'
            mock_mkv.makemkv.return_value = '/home/arm/media/raw/Test Movie (2024)'

            rip_visual_media(False, job, "test.log", 0)

            # At least one notify call for rip complete
            assert mock_utils.notify.call_count >= 1

    def test_makemkv_error_raises_ripper_exception(self):
        from arm.ripper.arm_ripper import rip_visual_media
        from arm.ripper.utils import RipperException
        from arm.ripper.makemkv import UpdateKeyRunTimeError

        job = self._make_job()

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils, \
             unittest.mock.patch('arm.ripper.arm_ripper.makemkv') as mock_mkv, \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            mock_utils.check_for_dupe_folder.return_value = '/home/arm/media/completed/movies/Test Movie (2024)'
            mock_utils.RipperException = RipperException
            mock_mkv.UpdateKeyRunTimeError = UpdateKeyRunTimeError
            mock_mkv.makemkv.side_effect = RuntimeError("MakeMKV crashed")

            try:
                rip_visual_media(False, job, "test.log", 0)
                assert False, "Expected RipperException"
            except RipperException:
                pass

    def test_no_rip_notification_when_disabled(self):
        from arm.ripper.arm_ripper import rip_visual_media

        job = self._make_job(notify_rip=False)

        with unittest.mock.patch('arm.ripper.arm_ripper.utils') as mock_utils, \
             unittest.mock.patch('arm.ripper.arm_ripper.makemkv') as mock_mkv, \
             unittest.mock.patch('arm.ripper.arm_ripper.db'):
            mock_utils.check_for_dupe_folder.return_value = '/home/arm/media/completed/movies/Test Movie (2024)'
            mock_mkv.makemkv.return_value = '/home/arm/media/raw/Test Movie (2024)'

            rip_visual_media(False, job, "test.log", 0)

            # Only notify_exit should call notify (for NOTIFY_TRANSCODE), not rip notification
            rip_complete_calls = [
                c for c in mock_utils.notify.call_args_list
                if 'rip complete' in str(c).lower()
            ]
            assert len(rip_complete_calls) == 0
