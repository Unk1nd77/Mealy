-- NutriAgent normalized PostgreSQL schema overview.
-- Executable migrations live in backend/alembic/versions.

CREATE TABLE users (
    id uuid PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    password_hash varchar(255) NOT NULL,
    age integer NOT NULL,
    weight_kg double precision NOT NULL,
    height_cm double precision NOT NULL,
    gender varchar NOT NULL,
    activity_level varchar NOT NULL,
    goal varchar NOT NULL,
    target_calories integer,
    created_at timestamp,
    updated_at timestamp NOT NULL DEFAULT now()
);

CREATE TABLE user_allergies (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    allergen varchar(100) NOT NULL,
    UNIQUE (user_id, allergen)
);

CREATE TABLE user_preferences (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preference varchar(100) NOT NULL,
    UNIQUE (user_id, preference)
);

CREATE TABLE user_disliked_ingredients (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ingredient varchar(100) NOT NULL,
    UNIQUE (user_id, ingredient)
);

CREATE TABLE user_diseases (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    disease varchar(100) NOT NULL,
    UNIQUE (user_id, disease)
);

CREATE TABLE meal_schedule_slots (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slot_order integer NOT NULL CHECK (slot_order >= 1),
    meal_type varchar(50) NOT NULL,
    planned_time time NOT NULL,
    calories_pct integer NOT NULL CHECK (calories_pct > 0 AND calories_pct <= 100),
    UNIQUE (user_id, meal_type, planned_time)
);

CREATE TABLE recipes (
    id uuid PRIMARY KEY,
    title varchar(255) NOT NULL,
    description text,
    calories double precision NOT NULL CHECK (calories >= 0),
    protein double precision NOT NULL CHECK (protein >= 0),
    fat double precision NOT NULL CHECK (fat >= 0),
    carbs double precision NOT NULL CHECK (carbs >= 0),
    embedding vector(1536),
    meal_type varchar(50),
    ingredients_short varchar(500),
    prep_time_min integer,
    category varchar(100),
    created_at timestamp,
    updated_at timestamp NOT NULL DEFAULT now()
);

CREATE TABLE recipe_ingredients (
    id uuid PRIMARY KEY,
    recipe_id uuid NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position integer NOT NULL CHECK (position >= 1),
    name varchar(255) NOT NULL,
    amount double precision NOT NULL CHECK (amount >= 0),
    unit varchar(50) NOT NULL,
    UNIQUE (recipe_id, position)
);

CREATE TABLE recipe_tags (
    id uuid PRIMARY KEY,
    recipe_id uuid NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag varchar(100) NOT NULL,
    UNIQUE (recipe_id, tag)
);

CREATE TABLE recipe_allergens (
    id uuid PRIMARY KEY,
    recipe_id uuid NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    allergen varchar(100) NOT NULL,
    UNIQUE (recipe_id, allergen)
);

CREATE TABLE meal_plans (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    status varchar NOT NULL,
    start_date date,
    end_date date,
    created_at timestamp,
    updated_at timestamp NOT NULL DEFAULT now(),
    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE meal_plan_days (
    id uuid PRIMARY KEY,
    meal_plan_id uuid NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    day_number integer NOT NULL CHECK (day_number >= 1),
    plan_date date,
    total_calories double precision NOT NULL DEFAULT 0 CHECK (total_calories >= 0),
    total_protein double precision NOT NULL DEFAULT 0 CHECK (total_protein >= 0),
    total_fat double precision NOT NULL DEFAULT 0 CHECK (total_fat >= 0),
    total_carbs double precision NOT NULL DEFAULT 0 CHECK (total_carbs >= 0),
    UNIQUE (meal_plan_id, day_number)
);

CREATE TABLE meal_plan_meals (
    id uuid PRIMARY KEY,
    day_id uuid NOT NULL REFERENCES meal_plan_days(id) ON DELETE CASCADE,
    recipe_id uuid REFERENCES recipes(id) ON DELETE SET NULL,
    meal_type varchar(50) NOT NULL,
    planned_time time,
    title_snapshot varchar(255) NOT NULL,
    calories double precision NOT NULL CHECK (calories >= 0),
    protein double precision NOT NULL CHECK (protein >= 0),
    fat double precision NOT NULL CHECK (fat >= 0),
    carbs double precision NOT NULL CHECK (carbs >= 0),
    portion_factor double precision NOT NULL DEFAULT 1 CHECK (portion_factor > 0)
);

CREATE TABLE meal_plan_meal_ingredients (
    id uuid PRIMARY KEY,
    meal_id uuid NOT NULL REFERENCES meal_plan_meals(id) ON DELETE CASCADE,
    position integer NOT NULL CHECK (position >= 1),
    ingredient_name varchar(255) NOT NULL,
    amount double precision NOT NULL CHECK (amount >= 0),
    unit varchar(50) NOT NULL,
    UNIQUE (meal_id, position)
);

CREATE TABLE meal_plan_events (
    id uuid PRIMARY KEY,
    meal_plan_id uuid NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    event_type varchar(50) NOT NULL,
    actor_type varchar(50) NOT NULL DEFAULT 'system',
    old_meal_id uuid REFERENCES meal_plan_meals(id) ON DELETE SET NULL,
    new_meal_id uuid REFERENCES meal_plan_meals(id) ON DELETE SET NULL,
    reason text,
    created_at timestamp NOT NULL DEFAULT now()
);

CREATE TABLE generation_runs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meal_plan_id uuid REFERENCES meal_plans(id) ON DELETE SET NULL,
    task_id varchar(255),
    mode varchar(50) NOT NULL,
    status varchar(50) NOT NULL,
    quality_status varchar(50),
    model_name varchar(255),
    prompt_version varchar(100),
    error_message text,
    started_at timestamp NOT NULL DEFAULT now(),
    finished_at timestamp
);

CREATE TABLE generation_run_steps (
    id uuid PRIMARY KEY,
    generation_run_id uuid NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
    step_key varchar(100) NOT NULL,
    status varchar(50) NOT NULL,
    message text,
    started_at timestamp NOT NULL DEFAULT now(),
    finished_at timestamp
);
