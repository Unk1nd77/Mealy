-- 10 simple PostgreSQL queries for NutriAgent.

-- 1. Users with fat-loss goal.
SELECT id, email, target_calories
FROM users
WHERE goal = 'lose';

-- 2. Recipes under 500 kcal.
SELECT id, title, calories
FROM recipes
WHERE calories < 500
ORDER BY calories;

-- 3. Breakfast recipes.
SELECT id, title, calories
FROM recipes
WHERE meal_type = 'breakfast';

-- 4. Recipes containing a specific allergen.
SELECT r.id, r.title, a.allergen
FROM recipes r
JOIN recipe_allergens a ON a.recipe_id = r.id
WHERE a.allergen = 'milk';

-- 5. Ingredients for one recipe.
SELECT ri.position, ri.name, ri.amount, ri.unit
FROM recipe_ingredients ri
WHERE ri.recipe_id = :recipe_id
ORDER BY ri.position;

-- 6. Meal plans for one user.
SELECT id, status, start_date, end_date
FROM meal_plans
WHERE user_id = :user_id
ORDER BY created_at DESC;

-- 7. Days in one plan.
SELECT day_number, plan_date, total_calories, total_protein, total_fat, total_carbs
FROM meal_plan_days
WHERE meal_plan_id = :meal_plan_id
ORDER BY day_number;

-- 8. Meals in one day.
SELECT meal_type, planned_time, title_snapshot, calories
FROM meal_plan_meals
WHERE day_id = :day_id
ORDER BY planned_time;

-- 9. Recipe candidates waiting for review.
SELECT id, source_url, source_type, created_at
FROM recipe_candidates
WHERE status = 'review'
ORDER BY created_at DESC;

-- 10. Generation runs by status.
SELECT id, task_id, mode, status, started_at
FROM generation_runs
WHERE status = 'FAILED'
ORDER BY started_at DESC;
