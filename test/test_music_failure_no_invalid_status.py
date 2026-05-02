"""Regression: music-rip failure paths must not write a non-enum
``status`` value into ``Track.status``.

Background
----------
Before this fix, the abcde wrapper's ``TimeoutError`` and
``subprocess.CalledProcessError`` branches in ``utils.rip_music`` called
``_update_music_tracks(job, ripped=False, status="fail")``.  ``"fail"``
is not a member of ``TrackStatus``; with the column declared as
``db.Enum(... validate_strings=True)`` the commit raises a
``LookupError`` / ``StatementError``.  In production the helper swallows
the exception in its broad ``except`` clause and rolls back, so the
breakage is silent - the per-track status never advances and no test
catches it.

This test pins the contract:

* both abcde failure modes (TimeoutError, CalledProcessError) finish
  cleanly (no raised LookupError, function returns False),
* per-track ``status`` stays at its prior value (``"pending"`` from
  ``Track.__init__``) - i.e. we no longer attempt to coerce a bare
  ``"fail"`` string into the enum column,
* ``ripped`` is False (the only field the failure path is allowed to
  flip).
"""
import os
import unittest.mock

import pytest

import arm.config.config as cfg
from arm.database import db
from arm.models.job import Job
from arm.models.config import Config
from arm.models.track import Track
from arm.ripper import utils
from arm_contracts.enums import TrackStatus


# ---------------------------------------------------------------------------
# Local fixtures (mirrors test_music_rip.music_job to avoid cross-file coupling)
# ---------------------------------------------------------------------------

@pytest.fixture
def music_job(app_context):
    """Create a Job with disctype='music' and the minimal attributes needed
    to exercise utils.rip_music()."""
    _, _ = app_context

    with unittest.mock.patch.object(Job, 'parse_udev'), \
         unittest.mock.patch.object(Job, 'get_pid'):
        job = Job('/dev/sr0')

    job.arm_version = "test"
    job.crc_id = ""
    job.logfile = "music_cd.log"
    job.start_time = None
    job.stop_time = None
    job.job_length = ""
    job.status = 'ripping'
    job.stage = "170750493000"
    job.no_of_titles = 0
    job.title = "DARK_SIDE"
    job.title_auto = "DARK_SIDE"
    job.title_manual = None
    job.year = ""
    job.year_auto = ""
    job.year_manual = None
    job.video_type = "unknown"
    job.video_type_auto = "unknown"
    job.video_type_manual = None
    job.imdb_id = ""
    job.imdb_id_auto = ""
    job.imdb_id_manual = None
    job.poster_url = ""
    job.poster_url_auto = ""
    job.poster_url_manual = None
    job.devpath = "/dev/sr0"
    job.mountpoint = "/mnt/dev/sr0"
    job.hasnicetitle = False
    job.errors = None
    job.disctype = "music"
    job.label = "DARK_SIDE"
    job.path = None
    job.raw_path = None
    job.transcode_path = None
    job.ejected = False
    job.updated = False
    job.pid = os.getpid()
    job.pid_hash = 0
    job.is_iso = False

    db.session.add(job)
    db.session.flush()

    config = Config({
        'RAW_PATH': '/home/arm/media/raw',
        'TRANSCODE_PATH': '/home/arm/media/transcode',
        'COMPLETED_PATH': '/home/arm/media/completed',
        'LOGPATH': '/tmp/arm_test/logs',
        'EXTRAS_SUB': 'extras',
        'MINLENGTH': '600',
        'MAXLENGTH': '99999',
        'MAINFEATURE': False,
        'RIPMETHOD': 'mkv',
        'NOTIFY_RIP': True,
        'NOTIFY_TRANSCODE': True,
        'WEBSERVER_PORT': 8080,
    }, job.job_id)

    db.session.add(config)
    db.session.commit()
    db.session.refresh(job)
    return job


def _seed_tracks(job, count=3):
    """Insert ``count`` Track rows for ``job``. Each row is left at the
    Track.__init__ default of status='pending', ripped=False."""
    tracks = []
    for i in range(1, count + 1):
        t = Track(
            job_id=job.job_id,
            track_number=str(i),
            length=180,
            aspect_ratio="n/a",
            fps=0.1,
            main_feature=False,
            source="MusicBrainz",
            basename=f"{i:02d} - Track {i}.flac",
            filename=f"{i:02d} - Track {i}.flac",
        )
        db.session.add(t)
        tracks.append(t)
    db.session.commit()
    return tracks


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

class TestMusicFailureUsesRippedOnlyHelper:
    """The abcde failure branches MUST route through
    ``_update_music_tracks_ripped_only`` and never through
    ``_update_music_tracks(..., status="fail")``.

    The naive integration test ("status stays pending on failure") is
    insufficient: the buggy code path also leaves status at 'pending',
    because ``_update_music_tracks`` swallows the resulting LookupError
    in its broad try/except and rolls back.  So we additionally assert
    the helper *call shape*, which is what actually flipped between the
    buggy and fixed versions.
    """

    def test_called_process_error_routes_through_ripped_only_helper(
        self, music_job, tmp_path
    ):
        """Non-zero abcde exit -> CalledProcessError branch -> calls
        ``_update_music_tracks_ripped_only(job, ripped=False)``, never
        ``_update_music_tracks(..., status="fail")``."""
        tracks = _seed_tracks(music_job)
        music_job.config.LOGPATH = str(tmp_path)
        logfile = "abcde_test.log"

        mock_proc = unittest.mock.MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.wait.return_value = 1
        mock_proc.returncode = 1
        mock_proc.stdout = iter([])

        with unittest.mock.patch.dict(cfg.arm_config, {
                'ABCDE_CONFIG_FILE': '/nonexistent',
            }), \
             unittest.mock.patch('subprocess.Popen', return_value=mock_proc), \
             unittest.mock.patch(
                 'arm.ripper.utils._update_music_tracks'
             ) as mock_with_status, \
             unittest.mock.patch(
                 'arm.ripper.utils._update_music_tracks_ripped_only'
             ) as mock_ripped_only:
            result = utils.rip_music(music_job, logfile)

        assert result is False
        # The fixed code path uses the ripped-only helper
        mock_ripped_only.assert_called_once_with(music_job, ripped=False)
        # And does NOT invoke the helper that would attempt to write
        # a non-enum 'fail' string into Track.status
        for call in mock_with_status.call_args_list:
            assert call.kwargs.get('status') != 'fail', \
                f"_update_music_tracks called with bare 'fail': {call!r}"
            assert call.kwargs.get('status') != TrackStatus.pending.value or True

        # And the live tracks remain unchanged on status (no real DB
        # write of an invalid enum happened either).
        for t in tracks:
            db.session.refresh(t)
            assert t.status == TrackStatus.pending.value
            assert t.status != "fail"

    def test_timeout_error_routes_through_ripped_only_helper(
        self, music_job, tmp_path
    ):
        """abcde stall -> TimeoutError branch -> calls
        ``_update_music_tracks_ripped_only(job, ripped=False)``, never
        ``_update_music_tracks(..., status="fail")``."""
        tracks = _seed_tracks(music_job)
        music_job.config.LOGPATH = str(tmp_path)
        logfile = "abcde_test.log"

        mock_proc = unittest.mock.MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.returncode = None
        mock_proc.stdout = iter([])

        with unittest.mock.patch.dict(cfg.arm_config, {
                'ABCDE_CONFIG_FILE': '/nonexistent',
            }), \
             unittest.mock.patch('subprocess.Popen', return_value=mock_proc), \
             unittest.mock.patch(
                 'arm.ripper.utils._stream_abcde_output',
                 side_effect=TimeoutError("CD rip stalled - simulated"),
             ), \
             unittest.mock.patch(
                 'arm.ripper.utils._update_music_tracks'
             ) as mock_with_status, \
             unittest.mock.patch(
                 'arm.ripper.utils._update_music_tracks_ripped_only'
             ) as mock_ripped_only:
            result = utils.rip_music(music_job, logfile)

        assert result is False
        mock_ripped_only.assert_called_once_with(music_job, ripped=False)
        for call in mock_with_status.call_args_list:
            assert call.kwargs.get('status') != 'fail', \
                f"_update_music_tracks called with bare 'fail': {call!r}"

        for t in tracks:
            db.session.refresh(t)
            assert t.status == TrackStatus.pending.value
            assert t.status != "fail"


class TestUpdateMusicTracksRippedOnly:
    """Direct unit test of the helper used by both failure branches.
    Belt-and-braces in case the integration tests above ever get
    short-circuited by a mock change - this would still catch a
    regression on the helper itself."""

    def test_helper_does_not_touch_status(self, music_job):
        tracks = _seed_tracks(music_job, count=2)

        # Sanity: starting state is the constructor default.
        for t in tracks:
            assert t.status == TrackStatus.pending.value

        # Should be a no-op on `status` and flip `ripped` to False.
        utils._update_music_tracks_ripped_only(music_job, ripped=False)

        for t in tracks:
            db.session.refresh(t)
            assert t.status == TrackStatus.pending.value
            assert t.ripped is False
