"""People and weigh-in records."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UTCDateTime(TypeDecorator):
    """Store naive UTC; return timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


PERSON_COLORS = (
    "#1f6b57",
    "#c45c26",
    "#3d5a80",
    "#9b4d7a",
    "#b08900",
    "#4a6741",
    "#6b4f3a",
    "#2f6f8f",
)


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="lb")
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str] = mapped_column(String(16), nullable=False, default="unspecified")
    color: Mapped[str] = mapped_column(String(16), nullable=False, default=PERSON_COLORS[0])
    goal_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    measurements: Mapped[list[Measurement]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="Measurement.recorded_at.desc()",
    )
    activities: Mapped[list[Activity]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="Activity.started_at.desc()",
    )
    workouts: Mapped[list[Workout]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="Workout.started_at.desc()",
    )
    checkins: Mapped[list[Checkin]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="Checkin.on_date.desc()",
    )
    meals: Mapped[list[Meal]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="Meal.eaten_at.desc()",
    )


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    had_food: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    had_water: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_bathroom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="measurements")

    @property
    def is_fasting_interval(self) -> bool:
        return (
            self.interval_known
            and not self.had_food
            and not self.had_water
            and not self.used_bathroom
        )

    @property
    def has_weight(self) -> bool:
        return self.weight_kg is not None

    @property
    def has_waist(self) -> bool:
        return self.waist_cm is not None


ACTIVITY_TYPES = ("run", "walk", "hike", "bike", "other")

DEFAULT_EXERCISES = (
    "Squat",
    "Bench press",
    "Deadlift",
    "Overhead press",
    "Row",
    "Pull-up",
    "Push-up",
    "Lunge",
    "Romanian deadlift",
    "Farmer carry",
    "Plank",
    "Hip hinge",
)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="run")
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="activities")


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="workouts")
    sets: Mapped[list[Set]] = relationship(
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="Set.position",
    )


class Set(Base):
    __tablename__ = "sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    workout: Mapped[Workout] = relationship(back_populates="sets")


MEAL_SLOTS = ("breakfast", "lunch", "dinner", "snack")
MEAL_SIZES = ("light", "normal", "heavy")


class Checkin(Base):
    """One sparse day log per person. Fields can be filled in later."""

    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("person_id", "on_date", name="uq_checkin_person_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    sleep_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    energy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soreness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="checkins")


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    eaten_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    slot: Mapped[str] = mapped_column(String(16), nullable=False, default="snack")
    size: Mapped[str | None] = mapped_column(String(16), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="meals")
