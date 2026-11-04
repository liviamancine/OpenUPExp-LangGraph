"""modelos de linguagem e perfis de inferência

Revision ID: b7e3f1c2d4a6
Revises: a51c0e7d9b20
Create Date: 2026-10-20 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b7e3f1c2d4a6'
down_revision: Union[str, Sequence[str], None] = 'a51c0e7d9b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_model',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('base_url', sa.String(length=300), nullable=True),
        sa.Column('model', sa.String(length=160), nullable=False),
        sa.Column('api_key_env', sa.String(length=80), nullable=True),
        sa.Column('local', sa.Boolean(), nullable=False),
        sa.Column('protected', sa.Boolean(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_table(
        'inference_profile',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('protected', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['llm_model.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('uq_inference_profile_default', 'inference_profile', ['is_default'], unique=True,
                    postgresql_where=sa.text('is_default'))


def downgrade() -> None:
    op.drop_index('uq_inference_profile_default', table_name='inference_profile')
    op.drop_table('inference_profile')
    op.drop_table('llm_model')
