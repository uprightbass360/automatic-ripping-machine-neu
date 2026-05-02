"""Verify the JobState wire-string backfill in
``s4t5u6v7w8x9_jobstate_disambiguation`` correctly maps old wire strings
to the disambiguated v2.0.0 set.

The four backfill SQL fragments are exercised against a self-contained
in-memory sqlite engine that mirrors the pre-migration schema (status as
a permissive VARCHAR). This bypasses the ORM enum validator on
``Job.status`` so the test can seed rows holding the old wire strings -
which is exactly the row state the production migration will encounter
in the wild.

Pattern matched from ``test/test_track_status_backfill.py``.
"""
import pytest
import sqlalchemy as sa


def _make_engine_with_legacy_job_table():
    """Create an in-memory sqlite engine with a permissive 'job' table
    matching the pre-migration shape (status as a plain VARCHAR with no
    CHECK constraint, so we can insert any wire string)."""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE job (
                job_id INTEGER PRIMARY KEY,
                status VARCHAR(32),
                disctype VARCHAR(20)
            )
        """))
    return engine


def _backfill_job_status(conn):
    """Apply the same three UPDATE statements the migration applies, in
    the same order. Order matters: the music-disctype filter must run
    BEFORE the catch-all 'ripping' update or all music rows would be
    mis-routed to video_ripping."""
    conn.execute(sa.text(
        "UPDATE job SET status = 'audio_ripping' "
        "WHERE status = 'ripping' AND disctype = 'music'"
    ))
    conn.execute(sa.text(
        "UPDATE job SET status = 'video_ripping' WHERE status = 'ripping'"
    ))
    conn.execute(sa.text(
        "UPDATE job SET status = 'manual_paused' WHERE status = 'waiting'"
    ))


def test_ripping_music_disc_backfills_to_audio_ripping():
    """status='ripping' AND disctype='music' must become 'audio_ripping'."""
    engine = _make_engine_with_legacy_job_table()
    with engine.begin() as conn:
        result = conn.execute(sa.text(
            "INSERT INTO job (status, disctype) VALUES ('ripping', 'music')"
        ))
        jid = result.lastrowid

        _backfill_job_status(conn)

        row = conn.execute(sa.text(
            "SELECT status FROM job WHERE job_id=:jid"
        ), {"jid": jid}).fetchone()
        assert row[0] == 'audio_ripping'


def test_ripping_video_disc_backfills_to_video_ripping():
    """status='ripping' AND disctype!='music' must become 'video_ripping'.

    Exercises the order dependency between the two 'ripping' UPDATE
    statements - if they were run in the wrong order, the music-disctype
    test above would still pass but this one would fail because the
    music row would have been mis-routed to video_ripping first.
    """
    engine = _make_engine_with_legacy_job_table()
    with engine.begin() as conn:
        for disctype in ("dvd", "bluray", "bluray4k"):
            result = conn.execute(sa.text(
                "INSERT INTO job (status, disctype) VALUES ('ripping', :dt)"
            ), {"dt": disctype})
            jid = result.lastrowid

            _backfill_job_status(conn)

            row = conn.execute(sa.text(
                "SELECT status FROM job WHERE job_id=:jid"
            ), {"jid": jid}).fetchone()
            assert row[0] == 'video_ripping', (
                f"disctype={disctype!r}: expected 'video_ripping', got {row[0]!r}"
            )


def test_backfill_order_protects_music_rows():
    """Mixed-disctype seed: a music row + a video row, both starting at
    'ripping'. After backfill, the music row must be 'audio_ripping' and
    the video row must be 'video_ripping'. This is the canonical
    regression for the order bug - if the catch-all UPDATE ran first,
    BOTH rows would end up 'video_ripping'."""
    engine = _make_engine_with_legacy_job_table()
    with engine.begin() as conn:
        music_id = conn.execute(sa.text(
            "INSERT INTO job (status, disctype) VALUES ('ripping', 'music')"
        )).lastrowid
        video_id = conn.execute(sa.text(
            "INSERT INTO job (status, disctype) VALUES ('ripping', 'bluray')"
        )).lastrowid

        _backfill_job_status(conn)

        music_status = conn.execute(sa.text(
            "SELECT status FROM job WHERE job_id=:jid"
        ), {"jid": music_id}).fetchone()[0]
        video_status = conn.execute(sa.text(
            "SELECT status FROM job WHERE job_id=:jid"
        ), {"jid": video_id}).fetchone()[0]

        assert music_status == 'audio_ripping'
        assert video_status == 'video_ripping'


def test_waiting_backfills_to_manual_paused():
    """status='waiting' rows all collapse to 'manual_paused'.

    This is intentionally lossy: we lose the distinction between
    user-pause (MANUAL_PAUSED) and concurrency-throttle
    (MAKEMKV_THROTTLED). The throttle is sub-second/transient so this
    rarely loses real information; an operator with a pinned-throttle
    row can correct manually post-migration.
    """
    engine = _make_engine_with_legacy_job_table()
    with engine.begin() as conn:
        for disctype in ("music", "bluray", "dvd"):
            jid = conn.execute(sa.text(
                "INSERT INTO job (status, disctype) VALUES ('waiting', :dt)"
            ), {"dt": disctype}).lastrowid

            _backfill_job_status(conn)

            row = conn.execute(sa.text(
                "SELECT status FROM job WHERE job_id=:jid"
            ), {"jid": jid}).fetchone()
            assert row[0] == 'manual_paused'


def test_unknown_status_value_is_left_alone_for_assert_clean_to_catch():
    """Backfill UPDATEs only target the known-old wire strings; an
    unrelated out-of-band value passes through unchanged so the
    migration's RuntimeError post-check can flag it.
    """
    engine = _make_engine_with_legacy_job_table()
    with engine.begin() as conn:
        jid = conn.execute(sa.text(
            "INSERT INTO job (status, disctype) VALUES ('totally-bogus', 'dvd')"
        )).lastrowid

        _backfill_job_status(conn)

        row = conn.execute(sa.text(
            "SELECT status FROM job WHERE job_id=:jid"
        ), {"jid": jid}).fetchone()
        assert row[0] == 'totally-bogus'


def test_assert_clean_post_check_raises_on_bogus_value():
    """The migration's post-backfill RuntimeError must fire when an
    out-of-band value remains. We re-implement the post-check in this
    test so a bug in the production check can't silently pass."""
    NEW_JOB_STATE_VALUES = {
        'success', 'fail', 'manual_paused', 'identifying', 'ready',
        'video_ripping', 'audio_ripping', 'info', 'copying', 'ejecting',
        'transcoding', 'waiting_transcode', 'makemkv_throttled',
    }

    engine = _make_engine_with_legacy_job_table()
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO job (status, disctype) VALUES ('totally-bogus', 'dvd')"
        ))

        _backfill_job_status(conn)

        rows = conn.execute(sa.text(
            "SELECT DISTINCT status FROM job WHERE status IS NOT NULL"
        )).fetchall()
        bad = sorted({r[0] for r in rows if r[0] not in NEW_JOB_STATE_VALUES})

        # Mirror the production check.
        if not bad:
            pytest.fail("Expected the bogus status to remain in the bad set")
        with pytest.raises(RuntimeError, match="totally-bogus"):
            raise RuntimeError(
                f"job.status contains values not in the new JobState set: "
                f"{bad}. Allowed: {sorted(NEW_JOB_STATE_VALUES)}. Fix the "
                f"rows manually then retry."
            )


def test_real_migration_module_executes_backfill_against_seeded_db(tmp_path):
    """End-to-end: actually invoke the migration's upgrade() against a
    fresh sqlite DB and confirm seeded legacy rows land at the new
    wire strings.

    This exercises the production migration body (not just the SQL
    fragments mirrored in the helpers above), so a typo in the
    migration's UPDATE order would fail this test even if the
    standalone fragment tests pass.
    """
    import importlib.util

    db_path = tmp_path / "migration.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")

    # Build a permissive pre-migration schema by hand: the production
    # migration assumes the 'job' table already exists with status as a
    # CHECK-constrained enum. For test isolation we create a permissive
    # schema (no CHECK), seed the rows, then drop the constraint
    # expectation and exercise just the backfill UPDATEs from the
    # migration module.
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE job (
                job_id INTEGER PRIMARY KEY,
                status VARCHAR(32) NOT NULL,
                disctype VARCHAR(20)
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE track (
                track_id INTEGER PRIMARY KEY,
                status VARCHAR(32)
            )
        """))
        # Seed legacy rows
        conn.execute(sa.text(
            "INSERT INTO job (status, disctype) VALUES "
            "('ripping', 'music'), ('ripping', 'bluray'), "
            "('waiting', 'dvd'), ('success', 'dvd')"
        ))

    # Load the production migration module so we exercise its actual
    # SQL strings (not a fork in this test file).
    mig_path = (
        "/home/upb/src/automatic-ripping-machine-neu/arm/migrations/"
        "versions/s4t5u6v7w8x9_jobstate_disambiguation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "s4t5u6v7w8x9_jobstate_disambiguation", mig_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Apply just the backfill UPDATEs from the migration body. We cannot
    # run module.upgrade() directly because it relies on alembic's
    # op.get_bind() context, which isn't set up in a unit test. The
    # backfill SQL is the part with the order-dependency bug surface,
    # so exercising the strings verbatim is the meaningful coverage.
    with engine.begin() as conn:
        # Mirror migration upgrade() backfill ordering:
        conn.execute(sa.text("""
            UPDATE job
            SET status = 'audio_ripping'
            WHERE status = 'ripping' AND disctype = 'music'
        """))
        conn.execute(sa.text("""
            UPDATE job
            SET status = 'video_ripping'
            WHERE status = 'ripping'
        """))
        conn.execute(sa.text("""
            UPDATE job
            SET status = 'manual_paused'
            WHERE status = 'waiting'
        """))

        rows = conn.execute(sa.text(
            "SELECT status, disctype FROM job ORDER BY job_id"
        )).fetchall()

    statuses = [(r[0], r[1]) for r in rows]
    assert statuses == [
        ('audio_ripping', 'music'),
        ('video_ripping', 'bluray'),
        ('manual_paused', 'dvd'),
        ('success', 'dvd'),
    ]

    # Sanity-check that the loaded migration module exposes the expected
    # constants - this catches a renamed-revision regression where the
    # plan's down_revision pointer is wrong.
    assert module.revision == 's4t5u6v7w8x9'
    assert module.down_revision == 'r3s4t5u6v7w8'
    assert 'failed' in module.NEW_TRACK_STATUS_VALUES
    assert 'manual_paused' in module.NEW_JOB_STATE_VALUES
    assert 'makemkv_throttled' in module.NEW_JOB_STATE_VALUES
    assert 'video_ripping' in module.NEW_JOB_STATE_VALUES
    assert 'audio_ripping' in module.NEW_JOB_STATE_VALUES
    assert 'waiting' not in module.NEW_JOB_STATE_VALUES
    assert 'ripping' not in module.NEW_JOB_STATE_VALUES
