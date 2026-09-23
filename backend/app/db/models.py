import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

DEFAULT_MEAL_SCHEDULE = [
    {"type": "breakfast", "time": "08:00", "calories_pct": 25},
    {"type": "lunch", "time": "13:00", "calories_pct": 35},
    {"type": "dinner", "time": "19:00", "calories_pct": 30},
    {"type": "snack", "time": "16:00", "calories_pct": 10},
]


class Gender(str, enum.Enum):
    male = "male"
    female = "female"


class ActivityLevel(str, enum.Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class Goal(str, enum.Enum):
    lose = "lose"
    maintain = "maintain"
    gain = "gain"


class MealPlanStatus(str, enum.Enum):
    pending = "PENDING"
    generating = "GENERATING"
    ready = "READY"
    failed = "FAILED"


class RecipeCandidateStatus(str, enum.Enum):
    pending = "PENDING"
    review = "REVIEW"
    accepted = "ACCEPTED"
    rejected = "REJECTED"


class RecipeReviewVerdict(str, enum.Enum):
    accept = "ACCEPT"
    review = "REVIEW"
    reject = "REJECT"


class SourceCandidateStatus(str, enum.Enum):
    pending = "PENDING"
    accepted = "ACCEPTED"
    rejected = "REJECTED"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    age = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=False)
    height_cm = Column(Float, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    activity_level = Column(Enum(ActivityLevel), nullable=False)
    goal = Column(Enum(Goal), nullable=False)

    target_calories = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meal_plans = relationship("MealPlan", back_populates="user")
    normalized_allergies = relationship(
        "UserAllergy",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    normalized_preferences = relationship(
        "UserPreference",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    normalized_disliked_ingredients = relationship(
        "UserDislikedIngredient",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    normalized_diseases = relationship(
        "UserDisease",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    meal_schedule_slots = relationship(
        "MealScheduleSlot",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="MealScheduleSlot.slot_order",
    )


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)

    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(String(255), nullable=True)
    embedding_updated_at = Column(DateTime, nullable=True)
    meal_type = Column(String(50), nullable=True)
    ingredients_short = Column(String(500), nullable=True)
    prep_time_min = Column(Integer, nullable=True)
    category = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    normalized_ingredients = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.position",
    )
    normalized_tags = relationship(
        "RecipeTag",
        back_populates="recipe",
        cascade="all, delete-orphan",
    )
    normalized_allergens = relationship(
        "RecipeAllergen",
        back_populates="recipe",
        cascade="all, delete-orphan",
    )

    @property
    def ingredients(self) -> list[dict]:
        return [
            {"name": item.name, "amount": item.amount, "unit": item.unit}
            for item in self.normalized_ingredients
        ]

    @property
    def tags(self) -> list[str]:
        return [item.tag for item in self.normalized_tags]

    @property
    def allergens(self) -> list[str]:
        return [item.allergen for item in self.normalized_allergens]


class RecipeCandidate(Base):
    __tablename__ = "recipe_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(String(1000), nullable=True)
    source_type = Column(String(100), nullable=True)
    source_snapshot = Column(JSONB, nullable=True)
    provenance = Column(JSONB, nullable=True)
    payload = Column(JSONB, nullable=False)
    normalized_payload = Column(JSONB, nullable=True)
    validation_report = Column(JSONB, nullable=True)
    status = Column(
        Enum(RecipeCandidateStatus),
        default=RecipeCandidateStatus.pending,
        nullable=False,
    )
    submitted_by = Column(String(100), nullable=True)
    admitted_recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    admitted_recipe = relationship("Recipe")
    reviews = relationship(
        "RecipeCandidateReview",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class SourceCandidate(Base):
    __tablename__ = "source_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String(1000), nullable=False)
    domain = Column(String(255), nullable=False)
    source_type = Column(String(100), nullable=False)
    discovery_query = Column(String(255), nullable=True)
    discovery_payload = Column(JSONB, nullable=True)
    source_snapshot = Column(JSONB, nullable=True)
    provenance = Column(JSONB, nullable=True)
    validation_report = Column(JSONB, nullable=True)
    status = Column(
        Enum(SourceCandidateStatus),
        default=SourceCandidateStatus.pending,
        nullable=False,
    )
    discovered_by = Column(String(100), nullable=True)
    linked_candidate_id = Column(
        UUID(as_uuid=True), ForeignKey("recipe_candidates.id"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    linked_candidate = relationship("RecipeCandidate")


class RecipeCandidateReview(Base):
    __tablename__ = "recipe_candidate_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("recipe_candidates.id"), nullable=False)
    reviewer = Column(String(100), nullable=True)
    verdict = Column(Enum(RecipeReviewVerdict), nullable=False)
    reason_codes = Column(ARRAY(String), default=list)
    notes = Column(Text, nullable=True)
    review_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("RecipeCandidate", back_populates="reviews")


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(MealPlanStatus), default=MealPlanStatus.pending, nullable=False)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="meal_plans")
    days = relationship(
        "MealPlanDay",
        back_populates="meal_plan",
        cascade="all, delete-orphan",
        order_by="MealPlanDay.day_number",
    )
    events = relationship(
        "MealPlanEvent",
        back_populates="meal_plan",
        cascade="all, delete-orphan",
    )


class UserAllergy(Base):
    __tablename__ = "user_allergies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    allergen = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="normalized_allergies")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    preference = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="normalized_preferences")


class UserDislikedIngredient(Base):
    __tablename__ = "user_disliked_ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ingredient = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="normalized_disliked_ingredients")


class UserDisease(Base):
    __tablename__ = "user_diseases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    disease = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="normalized_diseases")


class MealScheduleSlot(Base):
    __tablename__ = "meal_schedule_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slot_order = Column(Integer, nullable=False)
    meal_type = Column(String(50), nullable=False)
    planned_time = Column(Time, nullable=False)
    calories_pct = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="meal_schedule_slots")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    )
    position = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    recipe = relationship("Recipe", back_populates="normalized_ingredients")


class RecipeTag(Base):
    __tablename__ = "recipe_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    recipe = relationship("Recipe", back_populates="normalized_tags")


class RecipeAllergen(Base):
    __tablename__ = "recipe_allergens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    )
    allergen = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    recipe = relationship("Recipe", back_populates="normalized_allergens")


class MealPlanDay(Base):
    __tablename__ = "meal_plan_days"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meal_plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_number = Column(Integer, nullable=False)
    plan_date = Column(Date, nullable=True)
    total_calories = Column(Float, nullable=False, default=0)
    total_protein = Column(Float, nullable=False, default=0)
    total_fat = Column(Float, nullable=False, default=0)
    total_carbs = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meal_plan = relationship("MealPlan", back_populates="days")
    meals = relationship(
        "MealPlanMeal",
        back_populates="day",
        cascade="all, delete-orphan",
        order_by="MealPlanMeal.planned_time",
    )


class MealPlanMeal(Base):
    __tablename__ = "meal_plan_meals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meal_plan_days.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"))
    meal_type = Column(String(50), nullable=False)
    planned_time = Column(Time, nullable=True)
    title_snapshot = Column(String(255), nullable=False)
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)
    portion_factor = Column(Float, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    day = relationship("MealPlanDay", back_populates="meals")
    recipe = relationship("Recipe")
    ingredients = relationship(
        "MealPlanMealIngredient",
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealPlanMealIngredient.position",
    )


class MealPlanMealIngredient(Base):
    __tablename__ = "meal_plan_meal_ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meal_plan_meals.id", ondelete="CASCADE"),
        nullable=False,
    )
    position = Column(Integer, nullable=False)
    ingredient_name = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    meal = relationship("MealPlanMeal", back_populates="ingredients")


class MealPlanEvent(Base):
    __tablename__ = "meal_plan_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meal_plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(50), nullable=False)
    actor_type = Column(String(50), nullable=False, default="system")
    old_meal_id = Column(UUID(as_uuid=True), ForeignKey("meal_plan_meals.id", ondelete="SET NULL"))
    new_meal_id = Column(UUID(as_uuid=True), ForeignKey("meal_plan_meals.id", ondelete="SET NULL"))
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meal_plan = relationship("MealPlan", back_populates="events")


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    meal_plan_id = Column(UUID(as_uuid=True), ForeignKey("meal_plans.id", ondelete="SET NULL"))
    task_id = Column(String(255), nullable=True)
    mode = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    quality_status = Column(String(50), nullable=True)
    model_name = Column(String(255), nullable=True)
    prompt_version = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    user = relationship("User")
    meal_plan = relationship("MealPlan")
    steps = relationship(
        "GenerationRunStep",
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )


class GenerationRunStep(Base):
    __tablename__ = "generation_run_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    generation_run = relationship("GenerationRun", back_populates="steps")
