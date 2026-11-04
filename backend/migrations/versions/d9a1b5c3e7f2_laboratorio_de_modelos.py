"""laboratório de modelos: comparações, tentativas e notas

Revision ID: d9a1b5c3e7f2
Revises: c4d8e2a9f1b3
Create Date: 2026-10-20 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd9a1b5c3e7f2'
down_revision: Union[str, Sequence[str], None] = 'c4d8e2a9f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        'lab_comparison',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_task_execution_id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.String(length=20), nullable=False),
        sa.Column('baml_src_sha', sa.String(length=64), nullable=True),
        sa.Column('source_baml_src_sha', sa.String(length=64), nullable=True),
        sa.Column('package_sha256', sa.String(length=64), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_task_execution_id'], ['task_execution.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['run.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'lab_trial',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('comparison_id', sa.UUID(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('profile_snapshot', JSONB, nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('output', JSONB, nullable=False),
        sa.Column('metrics', JSONB, nullable=False),
        sa.Column('calls', JSONB, nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['comparison_id'], ['lab_comparison.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'lab_rating',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('trial_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('nota', sa.Integer(), nullable=False),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['trial_id'], ['lab_trial.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trial_id', 'user_id', name='uq_lab_rating_user'),
    )


def downgrade() -> None:
    op.drop_table('lab_rating')
    op.drop_table('lab_trial')
    op.drop_table('lab_comparison')
