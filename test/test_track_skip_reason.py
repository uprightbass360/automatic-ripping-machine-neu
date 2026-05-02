"""Tests for the new skip_reason column on Track."""

from arm.database import db


def test_track_skip_reason_default_null(app_context, sample_job):
    from arm.models.track import Track

    t = Track(
        job_id=sample_job.job_id,
        track_number="0",
        length=5712,
        aspect_ratio="16:9",
        fps=23.976,
        main_feature=True,
        source="MakeMKV",
        basename="title_00",
        filename="title_00.mkv",
    )
    db.session.add(t)
    db.session.commit()
    assert t.skip_reason is None


def test_track_skip_reason_set_to_too_short(app_context, sample_job):
    from arm.models.track import Track

    t = Track(
        job_id=sample_job.job_id, track_number="1", length=33,
        aspect_ratio="16:9", fps=23.976, main_feature=False,
        source="MakeMKV", basename="title_01", filename="title_01.mkv",
    )
    t.skip_reason = "too_short"
    t.process = False
    db.session.add(t)
    db.session.commit()

    rows = db.session.query(Track).filter_by(skip_reason="too_short").all()
    assert len(rows) == 1


def test_process_single_tracks_sets_too_short(app_context, sample_job, tmp_path):
    """When a track is below MINLENGTH, process_single_tracks sets
    process=False and skip_reason='too_short'."""
    from unittest.mock import patch
    from arm.models.track import Track
    from arm.ripper import makemkv

    sample_job.config.MINLENGTH = "600"
    sample_job.config.MAXLENGTH = "5000"
    sample_job.config.MKV_ARGS = ""

    short = Track(
        job_id=sample_job.job_id, track_number="0", length=33,
        aspect_ratio="16:9", fps=23.976, main_feature=False,
        source="MakeMKV", basename="t0", filename="t0.mkv",
    )
    db.session.add(short)
    db.session.commit()
    db.session.refresh(sample_job)

    with patch.object(makemkv, "run", return_value=iter([])):
        makemkv.process_single_tracks(sample_job, str(tmp_path), "auto")

    db.session.refresh(short)
    assert short.process is False
    assert short.skip_reason == "too_short"


def test_process_single_tracks_sets_too_long(app_context, sample_job, tmp_path):
    from unittest.mock import patch
    from arm.models.track import Track
    from arm.ripper import makemkv

    sample_job.config.MINLENGTH = "600"
    sample_job.config.MAXLENGTH = "5000"
    sample_job.config.MKV_ARGS = ""

    long_track = Track(
        job_id=sample_job.job_id, track_number="0", length=12345,
        aspect_ratio="16:9", fps=23.976, main_feature=False,
        source="MakeMKV", basename="t0", filename="t0.mkv",
    )
    db.session.add(long_track)
    db.session.commit()
    db.session.refresh(sample_job)

    with patch.object(makemkv, "run", return_value=iter([])):
        makemkv.process_single_tracks(sample_job, str(tmp_path), "auto")

    db.session.refresh(long_track)
    assert long_track.process is False
    assert long_track.skip_reason == "too_long"


def test_folder_prescan_auto_disable_sets_too_short(app_context, sample_job):
    """The folder-import prescan auto-disable should set both enabled=False
    AND skip_reason='too_short' on tracks below MINLENGTH."""
    from arm.models.track import Track
    from arm.api.v1.folder import auto_disable_short_tracks

    for n, length in [("0", 4568), ("1", 33), ("2", 22)]:
        db.session.add(Track(
            job_id=sample_job.job_id, track_number=n, length=length,
            aspect_ratio="16:9", fps=23.976, main_feature=False,
            source="MakeMKV", basename=f"t{n}", filename=f"t{n}.mkv",
        ))
    db.session.commit()

    auto_disable_short_tracks(sample_job, minlength=600)

    rows = {t.track_number: t for t in db.session.query(Track).filter_by(job_id=sample_job.job_id)}
    assert rows["0"].enabled is True
    assert rows["0"].skip_reason is None
    assert rows["1"].enabled is False
    assert rows["1"].skip_reason == "too_short"
    assert rows["2"].enabled is False
    assert rows["2"].skip_reason == "too_short"
