"""Tests that successful identification writes ExpectedTitle rows."""

from arm.database import db


def test_write_movie_expected_title_creates_row(app_context, sample_job):
    from arm.models.expected_title import ExpectedTitle
    from arm.ripper.identify import _write_movie_expected_title

    _write_movie_expected_title(
        sample_job,
        title="Inception",
        imdb_id="tt1375666",
        runtime_seconds=8880,
        source="omdb",
    )

    rows = db.session.query(ExpectedTitle).filter_by(job_id=sample_job.job_id).all()
    assert len(rows) == 1
    assert rows[0].source == "omdb"
    assert rows[0].title == "Inception"
    assert rows[0].external_id == "tt1375666"
    assert rows[0].runtime_seconds == 8880
    assert rows[0].season is None
    assert rows[0].episode_number is None


def test_write_movie_expected_title_with_null_runtime(app_context, sample_job):
    """CRC fast path provides no runtime; row is still written."""
    from arm.models.expected_title import ExpectedTitle
    from arm.ripper.identify import _write_movie_expected_title

    _write_movie_expected_title(
        sample_job,
        title="Obscure",
        imdb_id="tt0000001",
        runtime_seconds=None,
        source="manual",
    )

    rows = db.session.query(ExpectedTitle).filter_by(job_id=sample_job.job_id).all()
    assert len(rows) == 1
    assert rows[0].runtime_seconds is None
    assert rows[0].source == "manual"


def test_write_movie_expected_title_idempotent(app_context, sample_job):
    """Calling twice replaces, does not duplicate."""
    from arm.models.expected_title import ExpectedTitle
    from arm.ripper.identify import _write_movie_expected_title

    _write_movie_expected_title(
        sample_job, title="V1", imdb_id="tt1", runtime_seconds=5712, source="omdb"
    )
    _write_movie_expected_title(
        sample_job, title="V2", imdb_id="tt2", runtime_seconds=8523, source="tmdb"
    )

    rows = db.session.query(ExpectedTitle).filter_by(job_id=sample_job.job_id).all()
    assert len(rows) == 1
    assert rows[0].title == "V2"
    assert rows[0].source == "tmdb"
    assert rows[0].runtime_seconds == 8523
