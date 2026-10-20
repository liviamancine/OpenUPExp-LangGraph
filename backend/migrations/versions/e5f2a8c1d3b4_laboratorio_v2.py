"""laboratório v2: estratégia e repetição por tentativa; gabaritos

Revision ID: e5f2a8c1d3b4
Revises: d9a1b5c3e7f2
Create Date: 2026-10-20 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e5f2a8c1d3b4'
down_revision: Union[str, Sequence[str], None] = 'd9a1b5c3e7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lab_trial', sa.Column('strategy', sa.String(length=10), nullable=True))
    op.add_column('lab_trial', sa.Column('repeticao', sa.Integer(), nullable=False, server_default='1'))
    op.create_table(
        'lab_gold',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.String(length=20), nullable=False),
        sa.Column('artifact_type', sa.String(length=80), nullable=False),
        sa.Column('itens', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('autoria', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['app_user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'task_id', 'artifact_type', name='uq_lab_gold'),
    )


def downgrade() -> None:
    op.drop_table('lab_gold')
    op.drop_column('lab_trial', 'repeticao')
    op.drop_column('lab_trial', 'strategy')
