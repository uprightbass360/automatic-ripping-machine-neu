"""Verify the transcode_failed:<msg> backfill splits status from error."""
import unittest.mock


def test_backfill_splits_prefix_and_message(app_context):
    """When a Track had status='transcode_failed: oh no' before the
    migration, the new schema must hold status='transcode_failed' and
    error='oh no'."""
    from arm.database import db
    from arm.models.job import Job
    from arm.models.track import Track
    from arm_contracts.enums import TrackStatus
    import sqlalchemy as sa

    with unittest.mock.patch.object(Job, 'parse_udev'), \
         unittest.mock.patch.object(Job, 'get_pid'):
        job = Job('/dev/sr0')
    job.status = "ready"
    db.session.add(job)
    db.session.flush()

    # Force a "legacy" status value into Track via raw SQL so we
    # bypass the new enum validator and simulate pre-migration data.
    db.session.execute(sa.text(
        "INSERT INTO track (job_id, track_number, length, aspect_ratio, "
        "fps, main_feature, basename, filename, source, status, error) "
        "VALUES (:jid, '1', 0, '', 0.0, 0, 'b', 'f', 'x', "
        "'transcode_failed: encoder crashed at frame 1234', NULL)"
    ), {"jid": job.job_id})
    db.session.commit()

    # Apply the same backfill the migration applies.
    db.session.execute(sa.text("""
        UPDATE track
        SET error = CASE
                      WHEN error IS NULL OR error = ''
                      THEN SUBSTR(status, LENGTH('transcode_failed: ') + 1)
                      ELSE error
                    END,
            status = 'transcode_failed'
        WHERE status LIKE 'transcode_failed:%'
    """))
    db.session.commit()

    row = db.session.execute(sa.text(
        "SELECT status, error FROM track WHERE job_id=:jid"
    ), {"jid": job.job_id}).fetchone()
    assert row[0] == TrackStatus.transcode_failed.value
    assert row[1] == "encoder crashed at frame 1234"


def test_backfill_job_status_nulls_to_identifying():
    """A pre-migration Job row with status=NULL must be backfilled to
    'identifying' before the NOT NULL flip. The migration's _assert_clean
    pre-check filters WHERE col IS NOT NULL, so NULL rows are invisible
    to it and would otherwise trip the new NOT NULL constraint
    mid-ALTER. 'identifying' matches the new Job.__init__ default.

    This test uses a self-contained sqlite engine with a permissive
    pre-migration schema (status nullable) so it can simulate the exact
    NULL-row condition the production migration will encounter. Using
    the post-migration models from app_context would prevent the
    NULL-row insert that this test exists to cover.
    """
    from arm_contracts.enums import JobState
    import sqlalchemy as sa

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        # Pre-migration shape: status is a nullable string column.
        conn.execute(sa.text(
            "CREATE TABLE job (job_id INTEGER PRIMARY KEY, status VARCHAR(32))"
        ))
        result = conn.execute(sa.text(
            "INSERT INTO job (status) VALUES (NULL)"
        ))
        job_id = result.lastrowid

        # Sanity: confirm the row really landed with NULL.
        pre = conn.execute(sa.text(
            "SELECT status FROM job WHERE job_id=:jid"
        ), {"jid": job_id}).fetchone()
        assert pre[0] is None

        # Apply the same backfill the migration applies.
        conn.execute(sa.text(
            "UPDATE job SET status = 'identifying' WHERE status IS NULL"
        ))

        row = conn.execute(sa.text(
            "SELECT status FROM job WHERE job_id=:jid"
        ), {"jid": job_id}).fetchone()
        assert row[0] == JobState.IDENTIFYING.value


def test_backfill_remaps_legacy_track_status_fail_to_failed():
    """Pre-disambiguation, the music-rip failure path wrote
    JobState.FAILURE.value ('fail') into track.status. The TrackStatus
    enum has no 'fail' member - the right value is 'failed' (the new
    member added in s4t5u6v7w8x9). Real production rows from before the
    fix were observed on hifi 2026-05-03 (12 rows in job_id=123).

    The r3s4t5u6v7w8 backfill must remap them so the column constraint
    accepts them; otherwise the migration's _assert_clean pre-check
    blocks the upgrade.
    """
    from arm_contracts.enums import TrackStatus
    import sqlalchemy as sa

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        # Pre-migration shape: status is a nullable string column.
        conn.execute(sa.text(
            "CREATE TABLE track (track_id INTEGER PRIMARY KEY, "
            "status VARCHAR(32))"
        ))
        # Seed 3 rows with the legacy 'fail' value (mirroring the prod
        # artifact: multiple tracks from a single failed music job).
        conn.execute(sa.text(
            "INSERT INTO track (status) VALUES ('fail'), ('fail'), ('fail')"
        ))

        # Apply the same backfill the migration applies. Mirrors
        # arm/migrations/versions/r3s4t5u6v7w8_enum_columns.py upgrade()
        # step 1c.
        conn.execute(
            sa.text("UPDATE track SET status = :new WHERE status = :old"),
            {"old": "fail", "new": "failed"},
        )

        rows = conn.execute(sa.text(
            "SELECT status, COUNT(*) FROM track GROUP BY status"
        )).fetchall()
        assert rows == [(TrackStatus.failed.value, 3)]
