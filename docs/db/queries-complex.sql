-- 10 complex PostgreSQL reports for NutriAgent.

-- 1. Average plan calories by user goal.
SELECT u.goal, AVG(d.total_calories) AS avg_daily_calories
FROM users u
JOIN meal_plans p ON p.user_id = u.id
JOIN meal_plan_days d ON d.meal_plan_id = p.id
WHERE p.status = 'ready'
GROUP BY u.goal
ORDER BY u.goal;

-- 2. Top used recipes in generated plans.
SELECT r.id, r.title, COUNT(*) AS used_count
FROM meal_plan_meals m
JOIN recipes r ON r.id = m.recipe_id
GROUP BY r.id, r.title
ORDER BY used_count DESC, r.title
LIMIT 10;

-- 3. Daily calorie deviation from user target.
SELECT
    u.email,
    p.id AS meal_plan_id,
    d.day_number,
    u.target_calories,
    d.total_calories,
    d.total_calories - u.target_calories AS deviation_kcal
FROM users u
JOIN meal_plans p ON p.user_id = u.id
JOIN meal_plan_days d ON d.meal_plan_id = p.id
WHERE u.target_calories IS NOT NULL
ORDER BY ABS(d.total_calories - u.target_calories) DESC;

-- 4. Full macro report for one plan.
SELECT
    d.day_number,
    m.meal_type,
    m.planned_time,
    m.title_snapshot,
    m.calories,
    m.protein,
    m.fat,
    m.carbs
FROM meal_plan_days d
JOIN meal_plan_meals m ON m.day_id = d.id
WHERE d.meal_plan_id = :meal_plan_id
ORDER BY d.day_number, m.planned_time;

-- 5. Source acceptance rate.
SELECT
    sc.domain,
    COUNT(*) AS total_sources,
    COUNT(*) FILTER (WHERE sc.status = 'accepted') AS accepted_sources,
    ROUND(COUNT(*) FILTER (WHERE sc.status = 'accepted')::numeric / NULLIF(COUNT(*), 0) * 100, 2)
        AS accepted_pct
FROM source_candidates sc
GROUP BY sc.domain
ORDER BY accepted_pct DESC NULLS LAST, total_sources DESC;

-- 6. Average generation duration by mode.
SELECT
    mode,
    COUNT(*) AS runs,
    AVG(finished_at - started_at) AS avg_duration
FROM generation_runs
WHERE finished_at IS NOT NULL
GROUP BY mode
ORDER BY avg_duration DESC;

-- 7. Users whose restrictions exclude many recipes.
SELECT
    u.email,
    COUNT(DISTINCT ua.allergen) AS allergies_count,
    COUNT(DISTINCT ud.disease) AS diseases_count,
    COUNT(DISTINCT di.ingredient) AS disliked_count
FROM users u
LEFT JOIN user_allergies ua ON ua.user_id = u.id
LEFT JOIN user_diseases ud ON ud.user_id = u.id
LEFT JOIN user_disliked_ingredients di ON di.user_id = u.id
GROUP BY u.id, u.email
ORDER BY (COUNT(DISTINCT ua.allergen) + COUNT(DISTINCT ud.disease) + COUNT(DISTINCT di.ingredient)) DESC;

-- 8. Catalog coverage by meal type.
SELECT
    meal_type,
    COUNT(*) AS recipes_count,
    AVG(calories) AS avg_calories,
    MIN(calories) AS min_calories,
    MAX(calories) AS max_calories
FROM recipes
GROUP BY meal_type
ORDER BY recipes_count DESC;

-- 9. Most edited meal plans.
SELECT
    p.id AS meal_plan_id,
    u.email,
    COUNT(e.id) AS events_count,
    MAX(e.created_at) AS last_event_at
FROM meal_plans p
JOIN users u ON u.id = p.user_id
LEFT JOIN meal_plan_events e ON e.meal_plan_id = p.id
GROUP BY p.id, u.email
ORDER BY events_count DESC, last_event_at DESC NULLS LAST;

-- 10. Ingredients required for one plan shopping list.
SELECT
    LOWER(i.ingredient_name) AS ingredient,
    i.unit,
    SUM(i.amount) AS total_amount
FROM meal_plan_days d
JOIN meal_plan_meals m ON m.day_id = d.id
JOIN meal_plan_meal_ingredients i ON i.meal_id = m.id
WHERE d.meal_plan_id = :meal_plan_id
GROUP BY LOWER(i.ingredient_name), i.unit
ORDER BY ingredient;
