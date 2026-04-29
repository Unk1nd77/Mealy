-- PostgreSQL role sketch for NutriAgent.
-- Adjust passwords/secrets outside version control.

CREATE ROLE nutri_admin;
CREATE ROLE nutri_app;
CREATE ROLE nutri_nutritionist;
CREATE ROLE nutri_readonly;

GRANT CONNECT ON DATABASE nutriagent TO nutri_admin, nutri_app, nutri_nutritionist, nutri_readonly;
GRANT USAGE ON SCHEMA public TO nutri_admin, nutri_app, nutri_nutritionist, nutri_readonly;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nutri_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nutri_admin;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    users,
    user_allergies,
    user_preferences,
    user_disliked_ingredients,
    user_diseases,
    meal_schedule_slots,
    meal_plans,
    meal_plan_days,
    meal_plan_meals,
    meal_plan_meal_ingredients,
    meal_plan_events,
    generation_runs,
    generation_run_steps
TO nutri_app;

GRANT SELECT ON
    recipes,
    recipe_ingredients,
    recipe_tags,
    recipe_allergens
TO nutri_app;

GRANT SELECT, INSERT, UPDATE ON
    recipes,
    recipe_ingredients,
    recipe_tags,
    recipe_allergens,
    recipe_candidates,
    recipe_candidate_reviews,
    source_candidates
TO nutri_nutritionist;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO nutri_readonly;
