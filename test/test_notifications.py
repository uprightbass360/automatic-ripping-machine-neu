"""Tests for enhanced bash_notify() with ARM_* env vars (Phase 4)."""
import unittest.mock


class TestBashNotify:
    def test_env_vars_passed_to_subprocess(self, sample_job):
        """Verify ARM_* env vars are set when calling BASH_SCRIPT."""
        from arm.ripper.utils import bash_notify

        sample_job.raw_path = "/home/arm/media/raw/SERIAL_MOM"
        sample_job.path = "/home/arm/media/completed/movies/SERIAL_MOM (1994)"
        sample_job.transcode_path = "/home/arm/media/transcode/movies/SERIAL_MOM (1994)"

        cfg = {'BASH_SCRIPT': '/tmp/test_notify.sh'}

        with unittest.mock.patch('subprocess.run') as mock_run:
            bash_notify(cfg, "ARM notification", "SERIAL_MOM rip complete", sample_job)

            call_args = mock_run.call_args
            env = call_args.kwargs.get('env', {})

            assert env['ARM_JOB_ID'] == str(sample_job.job_id)
            assert env['ARM_TITLE'] == 'SERIAL_MOM'
            assert env['ARM_TITLE_AUTO'] == 'SERIAL_MOM'
            assert env['ARM_YEAR'] == '1994'
            assert env['ARM_RAW_PATH'] == '/home/arm/media/raw/SERIAL_MOM'
            assert env['ARM_PATH'] == '/home/arm/media/completed/movies/SERIAL_MOM (1994)'
            assert env['ARM_VIDEO_TYPE'] == 'movie'
            assert env['ARM_DISCTYPE'] == 'bluray'
            assert env['ARM_TRANSCODE_PATH'] == '/home/arm/media/transcode/movies/SERIAL_MOM (1994)'

    def test_positional_args_preserved(self, sample_job):
        """$1=title and $2=body must still be passed."""
        from arm.ripper.utils import bash_notify

        cfg = {'BASH_SCRIPT': '/tmp/test.sh'}

        with unittest.mock.patch('subprocess.run') as mock_run:
            bash_notify(cfg, "my title", "my body", sample_job)

            args = mock_run.call_args[0][0]
            assert args == ["/usr/bin/env", "bash", "/tmp/test.sh", "my title", "my body"]

    def test_backward_compat_no_job(self):
        """bash_notify still works when called without job (legacy)."""
        from arm.ripper.utils import bash_notify

        cfg = {'BASH_SCRIPT': '/tmp/test.sh'}

        with unittest.mock.patch('subprocess.run') as mock_run:
            bash_notify(cfg, "title", "body")  # no job arg
            mock_run.assert_called_once()

    def test_no_script_configured(self, sample_job):
        """No error when BASH_SCRIPT is empty."""
        from arm.ripper.utils import bash_notify

        cfg = {'BASH_SCRIPT': ''}

        with unittest.mock.patch('subprocess.run') as mock_run:
            bash_notify(cfg, "title", "body", sample_job)
            mock_run.assert_not_called()

    def test_none_values_handled(self, sample_job):
        """None values in job attributes should become empty strings."""
        from arm.ripper.utils import bash_notify

        sample_job.raw_path = None
        sample_job.path = None
        sample_job.transcode_path = None

        cfg = {'BASH_SCRIPT': '/tmp/test.sh'}

        with unittest.mock.patch('subprocess.run') as mock_run:
            bash_notify(cfg, "title", "body", sample_job)

            env = mock_run.call_args.kwargs.get('env', {})
            assert env['ARM_RAW_PATH'] == ''
            assert env['ARM_PATH'] == ''
            assert env['ARM_TRANSCODE_PATH'] == ''
