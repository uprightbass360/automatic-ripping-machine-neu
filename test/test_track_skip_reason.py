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
