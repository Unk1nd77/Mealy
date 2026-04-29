"""add normalized domain tables

Revision ID: 9f0a1b2c3d4e
Revises: e5a1c2d3f4b5
Create Date: 2026-04-28 22:20:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f0a1b2c3d4e"
down_revision: Union[str, None] = "e5a1c2d3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "recipes",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "meal_plans",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "user_allergies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allergen", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "allergen", name="uq_user_allergies_user_allergen"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preference", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "preference", name="uq_user_preferences_user_preference"),
    )
    op.create_table(
        "user_disliked_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ingredient", name="uq_user_dislikes_user_ingredient"),
    )
    op.create_table(
        "user_diseases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("disease", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "disease", name="uq_user_diseases_user_disease"),
    )
    op.create_table(
        "meal_schedule_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_order", sa.Integer(), nullable=False),
        sa.Column("meal_type", sa.String(length=50), nullable=False),
        sa.Column("planned_time", sa.Time(), nullable=False),
        sa.Column("calories_pct", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("slot_order >= 1", name="ck_meal_schedule_slots_slot_order"),
        sa.CheckConstraint(
            "calories_pct > 0 AND calories_pct <= 100",
            name="ck_meal_schedule_slots_calories_pct",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "meal_type", "planned_time", name="uq_meal_schedule_slot"),
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.CheckConstraint("position >= 1", name="ck_recipe_ingredients_position"),
        sa.CheckConstraint("amount >= 0", name="ck_recipe_ingredients_amount"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "position", name="uq_recipe_ingredients_position"),
    )
    op.create_table(
        "recipe_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "tag", name="uq_recipe_tags_recipe_tag"),
    )
    op.create_table(
        "recipe_allergens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allergen", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "allergen", name="uq_recipe_allergens_recipe_allergen"),
    )

    op.create_table(
        "meal_plan_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meal_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=True),
        sa.Column("total_calories", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_protein", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_fat", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_carbs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meal_plan_id"], ["meal_plans.id"], ondelete="CASCADE"),
        sa.CheckConstraint("day_number >= 1", name="ck_meal_plan_days_day_number"),
        sa.CheckConstraint("total_calories >= 0", name="ck_meal_plan_days_calories"),
        sa.CheckConstraint("total_protein >= 0", name="ck_meal_plan_days_protein"),
        sa.CheckConstraint("total_fat >= 0", name="ck_meal_plan_days_fat"),
        sa.CheckConstraint("total_carbs >= 0", name="ck_meal_plan_days_carbs"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meal_plan_id", "day_number", name="uq_meal_plan_days_plan_day"),
    )
    op.create_table(
        "meal_plan_meals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("meal_type", sa.String(length=50), nullable=False),
        sa.Column("planned_time", sa.Time(), nullable=True),
        sa.Column("title_snapshot", sa.String(length=255), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein", sa.Float(), nullable=False),
        sa.Column("fat", sa.Float(), nullable=False),
        sa.Column("carbs", sa.Float(), nullable=False),
        sa.Column("portion_factor", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["day_id"], ["meal_plan_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.CheckConstraint("calories >= 0", name="ck_meal_plan_meals_calories"),
        sa.CheckConstraint("protein >= 0", name="ck_meal_plan_meals_protein"),
        sa.CheckConstraint("fat >= 0", name="ck_meal_plan_meals_fat"),
        sa.CheckConstraint("carbs >= 0", name="ck_meal_plan_meals_carbs"),
        sa.CheckConstraint("portion_factor > 0", name="ck_meal_plan_meals_portion_factor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "meal_plan_meal_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("ingredient_name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meal_id"], ["meal_plan_meals.id"], ondelete="CASCADE"),
        sa.CheckConstraint("position >= 1", name="ck_meal_plan_meal_ingredients_position"),
        sa.CheckConstraint("amount >= 0", name="ck_meal_plan_meal_ingredients_amount"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meal_id", "position", name="uq_meal_plan_meal_ingredients_position"),
    )
    op.create_table(
        "meal_plan_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meal_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False, server_default="system"),
        sa.Column("old_meal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("new_meal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meal_plan_id"], ["meal_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["new_meal_id"], ["meal_plan_meals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["old_meal_id"], ["meal_plan_meals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "generation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meal_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("quality_status", sa.String(length=50), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["meal_plan_id"], ["meal_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "generation_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    for table_name in (
        "user_allergies",
        "user_preferences",
        "user_disliked_ingredients",
        "user_diseases",
        "meal_schedule_slots",
        "recipe_ingredients",
        "recipe_tags",
        "recipe_allergens",
        "meal_plan_days",
        "meal_plan_meals",
        "meal_plan_meal_ingredients",
        "meal_plan_events",
        "generation_runs",
        "generation_run_steps",
    ):
        fk_columns = {
            "user_allergies": "user_id",
            "user_preferences": "user_id",
            "user_disliked_ingredients": "user_id",
            "user_diseases": "user_id",
            "meal_schedule_slots": "user_id",
            "recipe_ingredients": "recipe_id",
            "recipe_tags": "recipe_id",
            "recipe_allergens": "recipe_id",
            "meal_plan_days": "meal_plan_id",
            "meal_plan_meals": "day_id",
            "meal_plan_meal_ingredients": "meal_id",
            "meal_plan_events": "meal_plan_id",
            "generation_runs": "user_id",
            "generation_run_steps": "generation_run_id",
        }
        op.create_index(f"ix_{table_name}_{fk_columns[table_name]}", table_name, [fk_columns[table_name]])

    op.create_index("ix_recipe_ingredients_name", "recipe_ingredients", ["name"])
    op.create_index("ix_recipe_tags_tag", "recipe_tags", ["tag"])
    op.create_index("ix_recipe_allergens_allergen", "recipe_allergens", ["allergen"])
    op.create_index("ix_meal_plan_meals_recipe_id", "meal_plan_meals", ["recipe_id"])
    op.create_index("ix_generation_runs_task_id", "generation_runs", ["task_id"])
    op.create_index("ix_generation_runs_status", "generation_runs", ["status"])

    _create_triggers()
    _backfill_normalized_tables()


def downgrade() -> None:
    _drop_triggers()

    op.drop_index("ix_generation_runs_status", table_name="generation_runs")
    op.drop_index("ix_generation_runs_task_id", table_name="generation_runs")
    op.drop_index("ix_meal_plan_meals_recipe_id", table_name="meal_plan_meals")
    op.drop_index("ix_recipe_allergens_allergen", table_name="recipe_allergens")
    op.drop_index("ix_recipe_tags_tag", table_name="recipe_tags")
    op.drop_index("ix_recipe_ingredients_name", table_name="recipe_ingredients")

    for table_name, fk_column in reversed(
        (
            ("user_allergies", "user_id"),
            ("user_preferences", "user_id"),
            ("user_disliked_ingredients", "user_id"),
            ("user_diseases", "user_id"),
            ("meal_schedule_slots", "user_id"),
            ("recipe_ingredients", "recipe_id"),
            ("recipe_tags", "recipe_id"),
            ("recipe_allergens", "recipe_id"),
            ("meal_plan_days", "meal_plan_id"),
            ("meal_plan_meals", "day_id"),
            ("meal_plan_meal_ingredients", "meal_id"),
            ("meal_plan_events", "meal_plan_id"),
            ("generation_runs", "user_id"),
            ("generation_run_steps", "generation_run_id"),
        )
    ):
        op.drop_index(f"ix_{table_name}_{fk_column}", table_name=table_name)

    op.drop_table("generation_run_steps")
    op.drop_table("generation_runs")
    op.drop_table("meal_plan_events")
    op.drop_table("meal_plan_meal_ingredients")
    op.drop_table("meal_plan_meals")
    op.drop_table("meal_plan_days")
    op.drop_table("recipe_allergens")
    op.drop_table("recipe_tags")
    op.drop_table("recipe_ingredients")
    op.drop_table("meal_schedule_slots")
    op.drop_table("user_diseases")
    op.drop_table("user_disliked_ingredients")
    op.drop_table("user_preferences")
    op.drop_table("user_allergies")
    op.drop_column("meal_plans", "updated_at")
    op.drop_column("recipes", "updated_at")
    op.drop_column("users", "updated_at")


def _create_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table_name in ("users", "recipes", "meal_plans", "meal_plan_days", "meal_plan_meals"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION recalculate_meal_plan_day_totals()
        RETURNS trigger AS $$
        DECLARE
            target_day_id uuid;
        BEGIN
            target_day_id = COALESCE(NEW.day_id, OLD.day_id);

            UPDATE meal_plan_days
            SET
                total_calories = COALESCE((SELECT SUM(calories) FROM meal_plan_meals WHERE day_id = target_day_id), 0),
                total_protein = COALESCE((SELECT SUM(protein) FROM meal_plan_meals WHERE day_id = target_day_id), 0),
                total_fat = COALESCE((SELECT SUM(fat) FROM meal_plan_meals WHERE day_id = target_day_id), 0),
                total_carbs = COALESCE((SELECT SUM(carbs) FROM meal_plan_meals WHERE day_id = target_day_id), 0),
                updated_at = now()
            WHERE id = target_day_id;

            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_meal_plan_meals_recalculate_day_totals
        AFTER INSERT OR UPDATE OR DELETE ON meal_plan_meals
        FOR EACH ROW EXECUTE FUNCTION recalculate_meal_plan_day_totals();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_meal_plan_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status IS DISTINCT FROM NEW.status
               OR OLD.start_date IS DISTINCT FROM NEW.start_date
               OR OLD.end_date IS DISTINCT FROM NEW.end_date THEN
                INSERT INTO meal_plan_events (id, meal_plan_id, event_type, actor_type, reason)
                VALUES (gen_random_uuid(), NEW.id, 'meal_plan_updated', 'database_trigger',
                        CONCAT('status=', OLD.status, '->', NEW.status));
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_meal_plans_audit_update
        AFTER UPDATE ON meal_plans
        FOR EACH ROW EXECUTE FUNCTION audit_meal_plan_update();
        """
    )


def _drop_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_meal_plans_audit_update ON meal_plans")
    op.execute("DROP FUNCTION IF EXISTS audit_meal_plan_update()")
    op.execute("DROP TRIGGER IF EXISTS trg_meal_plan_meals_recalculate_day_totals ON meal_plan_meals")
    op.execute("DROP FUNCTION IF EXISTS recalculate_meal_plan_day_totals()")
    for table_name in ("users", "recipes", "meal_plans", "meal_plan_days", "meal_plan_meals"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")


def _backfill_normalized_tables() -> None:
    op.execute(
        """
        INSERT INTO user_allergies (id, user_id, allergen)
        SELECT gen_random_uuid(), users.id, trim(value)
        FROM users, jsonb_array_elements_text(COALESCE(users.allergies, '[]'::jsonb)) AS value
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO user_preferences (id, user_id, preference)
        SELECT gen_random_uuid(), users.id, trim(value)
        FROM users, jsonb_array_elements_text(COALESCE(users.preferences, '[]'::jsonb)) AS value
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO user_disliked_ingredients (id, user_id, ingredient)
        SELECT gen_random_uuid(), users.id, trim(value)
        FROM users, jsonb_array_elements_text(COALESCE(users.disliked_ingredients, '[]'::jsonb)) AS value
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO user_diseases (id, user_id, disease)
        SELECT gen_random_uuid(), users.id, trim(value)
        FROM users, jsonb_array_elements_text(COALESCE(users.diseases, '[]'::jsonb)) AS value
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO meal_schedule_slots (id, user_id, slot_order, meal_type, planned_time, calories_pct)
        SELECT gen_random_uuid(), users.id, slot.ordinality, slot.type, slot.time::time, slot.calories_pct
        FROM users
        CROSS JOIN LATERAL ROWS FROM (
            jsonb_to_recordset(COALESCE(users.meal_schedule, '[]'::jsonb))
                AS (type text, time text, calories_pct int)
        ) WITH ORDINALITY AS slot(type, time, calories_pct, ordinality)
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO recipe_ingredients (id, recipe_id, position, name, amount, unit)
        SELECT gen_random_uuid(), recipes.id, ingredient.ordinality, ingredient.name,
               ingredient.amount, ingredient.unit
        FROM recipes
        CROSS JOIN LATERAL ROWS FROM (
            jsonb_to_recordset(COALESCE(recipes.ingredients, '[]'::jsonb))
                AS (name text, amount float, unit text)
        ) WITH ORDINALITY AS ingredient(name, amount, unit, ordinality)
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO recipe_tags (id, recipe_id, tag)
        SELECT gen_random_uuid(), recipes.id, trim(tag)
        FROM recipes, unnest(COALESCE(recipes.tags, ARRAY[]::varchar[])) AS tag
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO recipe_allergens (id, recipe_id, allergen)
        SELECT gen_random_uuid(), recipes.id, trim(allergen)
        FROM recipes, unnest(COALESCE(recipes.allergens, ARRAY[]::varchar[])) AS allergen
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO meal_plan_days (
            id, meal_plan_id, day_number, plan_date, total_calories, total_protein, total_fat, total_carbs
        )
        SELECT gen_random_uuid(), meal_plans.id, day.day_number,
               meal_plans.start_date + (day.day_number - 1),
               COALESCE(day.total_calories, 0), COALESCE(day.total_protein, 0),
               COALESCE(day.total_fat, 0), COALESCE(day.total_carbs, 0)
        FROM meal_plans
        CROSS JOIN LATERAL jsonb_to_recordset(COALESCE(meal_plans.plan_data->'days', '[]'::jsonb))
            AS day(day_number int, total_calories float, total_protein float, total_fat float, total_carbs float, meals jsonb)
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO meal_plan_meals (
            id, day_id, recipe_id, meal_type, planned_time, title_snapshot,
            calories, protein, fat, carbs, portion_factor
        )
        SELECT gen_random_uuid(), meal_plan_days.id,
               CASE
                   WHEN meal.recipe_id ~ '^[0-9a-fA-F-]{36}$' THEN meal.recipe_id::uuid
                   ELSE NULL
               END,
               meal.type, NULLIF(meal.time, '')::time, meal.title,
               COALESCE(meal.calories, 0), COALESCE(meal.protein, 0),
               COALESCE(meal.fat, 0), COALESCE(meal.carbs, 0),
               COALESCE(meal.portion_factor, 1)
        FROM meal_plans
        JOIN meal_plan_days ON meal_plan_days.meal_plan_id = meal_plans.id
        JOIN LATERAL jsonb_to_recordset(COALESCE(meal_plans.plan_data->'days', '[]'::jsonb))
            AS day(day_number int, meals jsonb) ON day.day_number = meal_plan_days.day_number
        CROSS JOIN LATERAL jsonb_to_recordset(COALESCE(day.meals, '[]'::jsonb))
            AS meal(type text, time text, recipe_id text, title text, calories float, protein float,
                    fat float, carbs float, portion_factor float, ingredients_summary jsonb);
        """
    )
    op.execute(
        """
        INSERT INTO meal_plan_meal_ingredients (id, meal_id, position, ingredient_name, amount, unit)
        SELECT gen_random_uuid(), meal_plan_meals.id, ingredient.ordinality,
               ingredient.name, ingredient.amount, ingredient.unit
        FROM meal_plans
        JOIN meal_plan_days ON meal_plan_days.meal_plan_id = meal_plans.id
        JOIN LATERAL jsonb_to_recordset(COALESCE(meal_plans.plan_data->'days', '[]'::jsonb))
            AS day(day_number int, meals jsonb) ON day.day_number = meal_plan_days.day_number
        JOIN LATERAL jsonb_to_recordset(COALESCE(day.meals, '[]'::jsonb))
            AS meal(type text, time text, recipe_id text, title text, calories float, protein float,
                    fat float, carbs float, portion_factor float, ingredients_summary jsonb)
            ON true
        JOIN meal_plan_meals
            ON meal_plan_meals.day_id = meal_plan_days.id
           AND meal_plan_meals.meal_type = meal.type
           AND meal_plan_meals.title_snapshot = meal.title
           AND meal_plan_meals.calories = COALESCE(meal.calories, 0)
        CROSS JOIN LATERAL ROWS FROM (
            jsonb_to_recordset(COALESCE(meal.ingredients_summary, '[]'::jsonb))
                AS (name text, amount float, unit text)
        ) WITH ORDINALITY AS ingredient(name, amount, unit, ordinality)
        ON CONFLICT DO NOTHING;
        """
    )
