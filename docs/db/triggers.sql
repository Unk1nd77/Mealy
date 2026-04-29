-- Trigger functions mirrored by Alembic migrations.

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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

CREATE TRIGGER trg_meal_plan_meals_recalculate_day_totals
AFTER INSERT OR UPDATE OR DELETE ON meal_plan_meals
FOR EACH ROW EXECUTE FUNCTION recalculate_meal_plan_day_totals();

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

CREATE TRIGGER trg_meal_plans_audit_update
AFTER UPDATE ON meal_plans
FOR EACH ROW EXECUTE FUNCTION audit_meal_plan_update();
