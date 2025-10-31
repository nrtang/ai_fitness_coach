"""
SQLAlchemy database models
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Date, Boolean,
    ForeignKey, Text, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship
from database import Base
from models import RunType, TrainingPhase, RaceDistance, IntensityZone
import enum


class User(Base):
    """User/Athlete account"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # User preferences
    unit_preference = Column(String, default="imperial")  # "metric" or "imperial"

    # Relationships
    workouts = relationship("Workout", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    training_programs = relationship("TrainingProgram", back_populates="user", cascade="all, delete-orphan")
    strava_connection = relationship("StravaConnection", back_populates="user", uselist=False, cascade="all, delete-orphan")


class StravaConnection(Base):
    """Strava OAuth connection for a user"""
    __tablename__ = "strava_connections"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Strava athlete info
    strava_athlete_id = Column(Integer, nullable=False, unique=True, index=True)

    # OAuth tokens
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(Integer, nullable=False)  # Unix timestamp

    # Sync status
    last_sync = Column(DateTime, nullable=True)
    sync_enabled = Column(Boolean, default=True)

    # Timestamps
    connected_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="strava_connection")


class Workout(Base):
    """Completed workout"""
    __tablename__ = "workouts"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    run_type = Column(SQLEnum(RunType), nullable=False)

    # Metrics (store as JSON for flexibility)
    metrics = Column(JSON, nullable=False)

    # Optional streams data (can be large, store as JSON)
    streams = Column(JSON, nullable=True)

    # Additional fields
    perceived_effort = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    source = Column(String, nullable=True)  # strava, garmin, etc

    # Strava-specific
    strava_activity_id = Column(String, nullable=True, unique=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="workouts")


class Goal(Base):
    """Training goal"""
    __tablename__ = "goals"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    race_distance = Column(SQLEnum(RaceDistance), nullable=False)
    race_date = Column(Date, nullable=False, index=True)
    target_time_seconds = Column(Float, nullable=False)
    target_speed_mps = Column(Float, nullable=True)

    current_fitness_level = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Status
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="goals")
    training_programs = relationship("TrainingProgram", back_populates="goal")


class TrainingProgram(Base):
    """Training program"""
    __tablename__ = "training_programs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    goal_id = Column(String, ForeignKey("goals.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    total_weeks = Column(Integer, nullable=False)
    rationale = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="training_programs")
    goal = relationship("Goal", back_populates="training_programs")
    weekly_plans = relationship("WeeklyPlan", back_populates="training_program", cascade="all, delete-orphan")


class WeeklyPlan(Base):
    """Weekly training plan"""
    __tablename__ = "weekly_plans"

    id = Column(String, primary_key=True)
    training_program_id = Column(String, ForeignKey("training_programs.id"), nullable=False, index=True)

    week_number = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    phase = Column(SQLEnum(TrainingPhase), nullable=False)
    total_distance = Column(Float, nullable=False)
    focus = Column(Text, nullable=False)

    # Relationships
    training_program = relationship("TrainingProgram", back_populates="weekly_plans")
    planned_workouts = relationship("PlannedWorkout", back_populates="weekly_plan", cascade="all, delete-orphan")


class PlannedWorkout(Base):
    """Planned workout"""
    __tablename__ = "planned_workouts"

    id = Column(String, primary_key=True)
    weekly_plan_id = Column(String, ForeignKey("weekly_plans.id"), nullable=False, index=True)

    date = Column(Date, nullable=False, index=True)
    run_type = Column(SQLEnum(RunType), nullable=False)
    intensity_zone = Column(SQLEnum(IntensityZone), nullable=False)

    target_distance = Column(Float, nullable=True)
    target_duration = Column(Float, nullable=True)
    target_speed = Column(Float, nullable=True)

    description = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)

    # Completion tracking
    completed = Column(Boolean, default=False)
    actual_workout_id = Column(String, ForeignKey("workouts.id"), nullable=True)

    # Relationships
    weekly_plan = relationship("WeeklyPlan", back_populates="planned_workouts")


class WorkoutEvaluation(Base):
    """Evaluation of completed workout vs plan"""
    __tablename__ = "workout_evaluations"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    planned_workout_id = Column(String, ForeignKey("planned_workouts.id"), nullable=False)
    actual_workout_id = Column(String, ForeignKey("workouts.id"), nullable=True)

    completed = Column(Boolean, nullable=False)
    adherence_score = Column(Float, nullable=False)
    feedback = Column(Text, nullable=False)
    adjustments_needed = Column(Boolean, nullable=False)

    evaluated_at = Column(DateTime, default=datetime.utcnow)


class WeeklyEvaluation(Base):
    """Evaluation of completed week"""
    __tablename__ = "weekly_evaluations"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    weekly_plan_id = Column(String, ForeignKey("weekly_plans.id"), nullable=False)

    completion_rate = Column(Float, nullable=False)
    total_distance_actual = Column(Float, nullable=False)
    weekly_feedback = Column(Text, nullable=False)
    recommended_adjustments = Column(Text, nullable=True)
    fatigue_assessment = Column(Text, nullable=True)

    evaluated_at = Column(DateTime, default=datetime.utcnow)
