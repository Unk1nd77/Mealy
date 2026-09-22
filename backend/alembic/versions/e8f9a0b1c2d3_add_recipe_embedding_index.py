"""add recipe embedding metadata and HNSW index

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("embedding_model", sa.String(length=255), nullable=True))
    op.add_column("recipes", sa.Column("embedding_updated_at", sa.DateTime(), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recipes_embedding_hnsw "
        "ON recipes USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_recipes_embedding_hnsw")
    op.drop_column("recipes", "embedding_updated_at")
    op.drop_column("recipes", "embedding_model")
