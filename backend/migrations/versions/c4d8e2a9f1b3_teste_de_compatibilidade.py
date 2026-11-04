"""resultado do teste de compatibilidade por perfil de inferência

Revision ID: c4d8e2a9f1b3
Revises: b7e3f1c2d4a6
Create Date: 2026-10-20 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4d8e2a9f1b3'
down_revision: Union[str, Sequence[str], None] = 'b7e3f1c2d4a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inference_profile', sa.Column('checks', postgresql.JSONB(astext_type=sa.Text()),
                                                 nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column('inference_profile', 'checks')
