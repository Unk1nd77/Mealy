"""ensure pgvector extension

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    pass
