"""Convert Job.status, Job.source_type, Track.status, Track.skip_reason,
Config.RIPMETHOD to db.Enum; split transcode_failed:<msg> Track rows into
status + error.

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-05-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


# Allowed value sets - duplicated here intentionally so the migration
# is self-contained and doesn't depend on importable Python enums
# (which may have drifted by the time someone runs an old migration).
JOB_STATE_VALUES = (
    'success', 'fail', 'waiting', 'identifying', 'ready', 'ripping',
    'info', 'copying', 'ejecting', 'transcoding', 'waiting_transcode',
)
SOURCE_TYPE_VALUES = ('disc', 'folder')
TRACK_STATUS_VALUES = (
    'pending', 'ripping', 'encoding', 'success',
    'transcoded', 'transcode_failed',
)
SKIP_REASON_VALUES = (
    'too_short', 'too_long', 'makemkv_skipped',
    'user_disabled', 'below_main_feature',
)
RIPMETHOD_VALUES = ('mkv', 'backup', 'backup_dvd')


def _assert_clean(conn, table, column, allowed):
    """Raise loudly if the table contains values outside the allowed set."""
    rows = conn.execute(
        sa.text(
            f'SELECT DISTINCT {column} FROM {table} '
            f'WHERE {column} IS NOT NULL'
        )
    ).fetchall()
    bad = [r[0] for r in rows if r[0] not in allowed]
    if bad:
        raise RuntimeError(
            f'{table}.{column} contains values not in the new enum: {bad}. '
            f'Allowed: {sorted(allowed)}. Fix the rows manually before '
            f'running this migration.'
        )


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Track.status backfill: split 'transcode_failed: <msg>' rows.
    #    The error text is preserved in the existing Track.error column,
    #    which is db.Text (no length cap).
    conn.execute(sa.text("""
        UPDATE track
        SET error = CASE
                      WHEN error IS NULL OR error = ''
                      THEN SUBSTR(status, LENGTH('transcode_failed: ') + 1)
                      ELSE error
                    END,
            status = 'transcode_failed'
        WHERE status LIKE 'transcode_failed:%'
    """))

    # 2. Pre-checks: refuse to migrate if any column has an out-of-band
    #    value. Better to fail loudly here than to silently truncate or
    #    coerce; the operator can then clean up the row manually and
    #    retry.
    _assert_clean(conn, 'job', 'status', JOB_STATE_VALUES)
    _assert_clean(conn, 'job', 'source_type', SOURCE_TYPE_VALUES)
    _assert_clean(conn, 'track', 'status', TRACK_STATUS_VALUES)
    _assert_clean(conn, 'track', 'skip_reason', SKIP_REASON_VALUES)
    _assert_clean(conn, 'config', 'RIPMETHOD', RIPMETHOD_VALUES)

    # 3. Column-type conversions. native_enum=False means no DDL ENUM
    #    type is created; the constraint is enforced via a CHECK clause
    #    that batch_alter_table emits.
    with op.batch_alter_table('job') as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.String(32),
            type_=sa.Enum(*JOB_STATE_VALUES, name='job_state_enum',
                          native_enum=False, validate_strings=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            'source_type',
            existing_type=sa.String(16),
            type_=sa.Enum(*SOURCE_TYPE_VALUES, name='job_source_type_enum',
                          native_enum=False, validate_strings=True),
            existing_nullable=False,
            existing_server_default='disc',
        )

    with op.batch_alter_table('track') as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.String(32),
            type_=sa.Enum(*TRACK_STATUS_VALUES, name='track_status_enum',
                          native_enum=False, validate_strings=True),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'skip_reason',
            existing_type=sa.String(32),
            type_=sa.Enum(*SKIP_REASON_VALUES, name='track_skip_reason_enum',
                          native_enum=False, validate_strings=True),
            existing_nullable=True,
        )

    with op.batch_alter_table('config') as batch_op:
        batch_op.alter_column(
            'RIPMETHOD',
            existing_type=sa.String(25),
            type_=sa.Enum(*RIPMETHOD_VALUES, name='config_ripmethod_enum',
                          native_enum=False, validate_strings=True),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Revert columns to plain String. Track.status backfill is NOT
    reversed - the error text stays in Track.error (where it should
    have been all along)."""
    with op.batch_alter_table('config') as batch_op:
        batch_op.alter_column(
            'RIPMETHOD',
            type_=sa.String(25),
            existing_nullable=True,
        )
    with op.batch_alter_table('track') as batch_op:
        batch_op.alter_column(
            'skip_reason',
            type_=sa.String(32),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'status',
            type_=sa.String(32),
            existing_nullable=True,
        )
    with op.batch_alter_table('job') as batch_op:
        batch_op.alter_column(
            'source_type',
            type_=sa.String(16),
            existing_nullable=False,
            existing_server_default='disc',
        )
        batch_op.alter_column(
            'status',
            type_=sa.String(32),
            existing_nullable=False,
        )
