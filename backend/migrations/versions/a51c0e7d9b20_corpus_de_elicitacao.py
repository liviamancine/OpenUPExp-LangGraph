"""corpus de elicitação por execução

Revision ID: a51c0e7d9b20
Revises: cdd2292fc6ba
Create Date: 2026-10-20 00:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a51c0e7d9b20'
down_revision: Union[str, Sequence[str], None] = 'cdd2292fc6ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # reference: base de referência do projeto; elicitation: material de elicitação de uma execução (2.2.1)
    op.add_column('corpus_version', sa.Column('purpose', sa.String(length=20), nullable=False,
                                              server_default='reference'))
    op.add_column('corpus_version', sa.Column('run_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_corpus_version_run', 'corpus_version', 'run', ['run_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_corpus_version_run', 'corpus_version', type_='foreignkey')
    op.drop_column('corpus_version', 'run_id')
    op.drop_column('corpus_version', 'purpose')
