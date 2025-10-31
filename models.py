"""
Core data models for AI Fitness Coach
"""
from datetime import datetime, date
from typing import Optional, List, Literal
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class RunType(str, Enum):
    """Types of running workouts"""
    EASY = "easy"
    RECOVERY = "recovery"
    LONG = "long"
    TEMPO = "tempo"
    INTERVALS = "intervals"
    HILL_REPEATS = "hill_repeats"
    PROGRESSION = "progression"
    RACE = "race"
    REST = "rest"


class TrainingPhase(str, Enum):
    """Training cycle phases"""
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"
    RECOVERY = "recovery"


class RaceDistance(str, Enum):
    """Supported race distances"""
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    ULTRA_50K = "ultra_50k"
    ULTRA_50MI = "ultra_50mi"
    ULTRA_100K = "ultra_100k"
    ULTRA_100MI = "ultra_100mi"


class IntensityZone(int, Enum):
    """Training intensity zones (1-5)"""
    RECOVERY = 1
    EASY = 2
    MODERATE = 3
    THRESHOLD = 4
    HARD = 5


class WorkoutMetrics(BaseModel):
    """Metrics captured during a workout (matches Strava API format)"""
    distance: float = Field(gt=0, description="Distance in meters")
    moving_time: float = Field(gt=0, description="Moving time in seconds")
    elapsed_time: float = Field(gt=0, description="Total elapsed time in seconds")
    total_elevation_gain: Optional[float] = Field(None, ge=0, description="Elevation gain in meters")

    # Speed/pace in meters per second (Strava format)
    average_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    max_speed: Optional[float] = Field(None, ge=0, description="Max speed in m/s")

    # Heart rate
    average_heartrate: Optional[float] = Field(None, ge=0, le=250, description="Average heart rate (bpm)")
    max_heartrate: Optional[int] = Field(None, ge=0, le=250, description="Max heart rate (bpm)")

    # Cadence
    average_cadence: Optional[float] = Field(None, ge=0, description="Average cadence (steps/min)")

    # Power
    average_watts: Optional[float] = Field(None, ge=0, description="Average power in watts")
    max_watts: Optional[int] = Field(None, ge=0, description="Max power in watts")

    # Other
    calories: Optional[float] = Field(None, ge=0, description="Calories burned")

    @field_validator('average_speed', mode='before')
    @classmethod
    def calculate_speed_if_missing(cls, v, info):
        """Calculate average speed from distance and time if not provided"""
        if v is None and 'distance' in info.data and 'moving_time' in info.data:
            if info.data['moving_time'] > 0:
                return info.data['distance'] / info.data['moving_time']
        return v


class WorkoutStreams(BaseModel):
    """Time-series data for a workout (GPS, HR, cadence, etc.)"""
    # Time series - all arrays should be same length
    time: Optional[List[int]] = Field(None, description="Time in seconds from start")
    distance: Optional[List[float]] = Field(None, description="Cumulative distance in meters")
    latlng: Optional[List[List[float]]] = Field(None, description="GPS coordinates [[lat, lng], ...]")
    altitude: Optional[List[float]] = Field(None, description="Elevation in meters")
    velocity_smooth: Optional[List[float]] = Field(None, description="Smoothed speed in m/s")
    heartrate: Optional[List[int]] = Field(None, description="Heart rate in bpm")
    cadence: Optional[List[int]] = Field(None, description="Cadence in steps/min")
    watts: Optional[List[int]] = Field(None, description="Power in watts")
    temp: Optional[List[int]] = Field(None, description="Temperature in celsius")
    grade_smooth: Optional[List[float]] = Field(None, description="Grade/gradient as percentage")


class Workout(BaseModel):
    """A completed workout"""
    id: str
    date: datetime
    run_type: RunType
    metrics: WorkoutMetrics
    streams: Optional[WorkoutStreams] = Field(None, description="Detailed time-series data")
    perceived_effort: Optional[int] = Field(None, ge=1, le=10, description="RPE (1-10 scale)")
    notes: Optional[str] = None
    source: Optional[str] = Field(None, description="Data source (strava, garmin, etc)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "workout_123",
                "date": "2025-10-15T06:30:00",
                "run_type": "easy",
                "metrics": {
                    "distance": 8000.0,
                    "moving_time": 2880.0,
                    "elapsed_time": 2880.0,
                    "average_speed": 2.78,
                    "average_heartrate": 145
                },
                "perceived_effort": 4,
                "notes": "Felt good, legs a bit tired",
                "source": "strava"
            }
        }


class Goal(BaseModel):
    """User's training goal"""
    race_distance: RaceDistance
    race_date: date
    target_time_seconds: float = Field(gt=0, description="Target finish time in seconds")
    target_speed_mps: Optional[float] = Field(None, description="Target speed in meters per second")
    current_fitness_level: Optional[str] = Field(None, description="AI assessment of current fitness")
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator('target_speed_mps', mode='before')
    @classmethod
    def calculate_target_speed(cls, v, info):
        """Calculate target speed from time and distance"""
        if v is None and 'race_distance' in info.data and 'target_time_seconds' in info.data:
            distance_map = {
                RaceDistance.FIVE_K: 5000.0,
                RaceDistance.TEN_K: 10000.0,
                RaceDistance.HALF_MARATHON: 21097.5,
                RaceDistance.MARATHON: 42195.0,
                RaceDistance.ULTRA_50K: 50000.0,
                RaceDistance.ULTRA_50MI: 80467.0,
                RaceDistance.ULTRA_100K: 100000.0,
                RaceDistance.ULTRA_100MI: 160934.0,
            }
            distance = distance_map.get(info.data['race_distance'])
            if distance and info.data['target_time_seconds'] > 0:
                return distance / info.data['target_time_seconds']
        return v

    @field_validator('race_date')
    @classmethod
    def validate_future_date(cls, v):
        """Ensure race date is in the future"""
        if v < date.today():
            raise ValueError("Race date must be in the future")
        return v


class PlannedWorkout(BaseModel):
    """A planned workout in the training program"""
    date: date
    run_type: RunType
    intensity_zone: IntensityZone
    target_distance: Optional[float] = Field(None, gt=0, description="Target distance in meters")
    target_duration: Optional[float] = Field(None, gt=0, description="Target duration in seconds")
    target_speed: Optional[float] = Field(None, gt=0, description="Target speed in m/s")
    description: str = Field(description="Detailed workout description")
    notes: Optional[str] = Field(None, description="Additional coaching notes")


class WeeklyPlan(BaseModel):
    """A week of training"""
    week_number: int = Field(ge=1, description="Week number in the program")
    start_date: date
    end_date: date
    phase: TrainingPhase
    total_distance: float = Field(ge=0, description="Total weekly distance in meters")
    workouts: List[PlannedWorkout] = Field(min_length=1, max_length=7)
    focus: str = Field(description="Focus of the week")

    @field_validator('workouts')
    @classmethod
    def validate_workouts_per_week(cls, v):
        """Ensure reasonable number of workouts"""
        if len(v) > 7:
            raise ValueError("Cannot have more than 7 workouts in a week")
        return v


class TrainingProgram(BaseModel):
    """Complete training program"""
    id: str
    goal: Goal
    created_at: datetime = Field(default_factory=datetime.now)
    start_date: date
    weeks: List[WeeklyPlan]
    total_weeks: int = Field(ge=1)
    rationale: str = Field(description="AI explanation of program design")

    @field_validator('total_weeks', mode='before')
    @classmethod
    def calculate_total_weeks(cls, v, info):
        """Calculate total weeks from weeks list"""
        if v is None and 'weeks' in info.data:
            return len(info.data['weeks'])
        return v


class WorkoutEvaluation(BaseModel):
    """Evaluation of a completed workout against planned workout"""
    planned: PlannedWorkout
    actual: Optional[Workout]
    completed: bool
    adherence_score: float = Field(ge=0, le=100, description="0-100 score of plan adherence")
    feedback: str = Field(description="AI feedback on the workout")
    adjustments_needed: bool = Field(description="Whether program adjustments are recommended")


class WeeklyEvaluation(BaseModel):
    """Evaluation of a completed week"""
    week_plan: WeeklyPlan
    workout_evaluations: List[WorkoutEvaluation]
    completion_rate: float = Field(ge=0, le=100, description="Percentage of workouts completed")
    total_distance_actual: float = Field(ge=0)
    weekly_feedback: str = Field(description="AI feedback on the week")
    recommended_adjustments: Optional[str] = Field(None, description="Suggested program changes")
    fatigue_assessment: Optional[str] = Field(None, description="Signs of overtraining/undertraining")
