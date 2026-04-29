"""merge profile schedule and catalog source heads

Revision ID: e5a1c2d3f4b5
Revises: b4c6d8e0f2a3, d2e4f6a8b0c1
Create Date: 2026-04-28 22:10:00.000000
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "e5a1c2d3f4b5"
down_revision: Union[str, tuple[str, str], None] = ("b4c6d8e0f2a3", "d2e4f6a8b0c1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
