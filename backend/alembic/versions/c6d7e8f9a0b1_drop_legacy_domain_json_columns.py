"""drop legacy domain json columns

Revision ID: c6d7e8f9a0b1
Revises: 9f0a1b2c3d4e
Create Date: 2026-04-28 23:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "9f0a1b2c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("meal_plans", "plan_data")
    op.drop_column("recipes", "allergens")
    op.drop_column("recipes", "tags")
    op.drop_column("recipes", "ingredients")
    op.drop_column("users", "meal_schedule")
    op.drop_column("users", "diseases")
    op.drop_column("users", "disliked_ingredients")
    op.drop_column("users", "preferences")
    op.drop_column("users", "allergies")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "allergies",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "disliked_ingredients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "diseases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "meal_schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "recipes",
        sa.Column(
            "ingredients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "recipes",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=True,
            server_default="{}",
        ),
    )
    op.add_column(
        "recipes",
        sa.Column(
            "allergens",
            postgresql.ARRAY(sa.String()),
            nullable=True,
            server_default="{}",
        ),
    )
    op.add_column(
        "meal_plans",
        sa.Column("plan_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
