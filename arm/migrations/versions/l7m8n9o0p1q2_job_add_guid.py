"""job: add guid column for GUID-based work paths

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-04-06

"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = 'l7m8n9o0p1q2'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job') as batch_op:
        batch_op.add_column(sa.Column('guid', sa.String(36), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT job_id FROM job WHERE guid IS NULL"))
    for row in rows:
        conn.execute(
            sa.text("UPDATE job SET guid = :guid WHERE job_id = :id"),
            {"guid": str(uuid.uuid4()), "id": row[0]},
        )

    with op.batch_alter_table('job') as batch_op:
        batch_op.alter_column('guid', nullable=False)
        batch_op.create_unique_constraint('uq_job_guid', ['guid'])


def downgrade():
    with op.batch_alter_table('job') as batch_op:
        batch_op.drop_constraint('uq_job_guid', type_='unique')
        batch_op.drop_column('guid')
