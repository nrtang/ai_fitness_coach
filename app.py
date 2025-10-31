"""
Main application - FastAPI REST API for AI Fitness Coach
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta
import uuid

from database import get_db, init_db
from db_models import (
    User as DBUser,
    Workout as DBWorkout,
    Goal as DBGoal,
    TrainingProgram as DBTrainingProgram,
    WeeklyPlan as DBWeeklyPlan,
    PlannedWorkout as DBPlannedWorkout,
    WorkoutEvaluation as DBWorkoutEvaluation,
    StravaConnection as DBStravaConnection
)
from models import (
    Workout, WorkoutMetrics, Goal, TrainingProgram,
    RaceDistance, RunType
)
from ai_coach import AICoach
from training_load import TrainingLoadCalculator
from strava_client import StravaClient
import json
import os

# Initialize FastAPI app
app = FastAPI(
    title="AI Fitness Coach",
    description="AI-powered training program generator and workout evaluator",
    version="1.0.0"
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI Coach and Strava client
ai_coach = AICoach()
training_load_calc = TrainingLoadCalculator()
strava_client = StravaClient()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


# Serve the web UI
@app.get("/")
async def root():
    """Serve the main web UI"""
    return FileResponse("static/index.html")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AI Fitness Coach"}


# User endpoints
@app.post("/users")
async def create_user(
    email: str,
    name: str,
    unit_preference: str = "imperial",
    db: Session = Depends(get_db)
):
    """Create a new user"""
    # Check if user exists
    existing = db.query(DBUser).filter(DBUser.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = DBUser(
        id=f"user_{uuid.uuid4().hex}",
        email=email,
        name=name,
        unit_preference=unit_preference
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "unit_preference": user.unit_preference
    }


@app.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    """Get user by ID"""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "unit_preference": user.unit_preference
    }


# Workout endpoints
@app.post("/users/{user_id}/workouts")
async def create_workout(
    user_id: str,
    workout_data: dict,
    db: Session = Depends(get_db)
):
    """Create a new workout for a user"""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    workout = DBWorkout(
        id=f"workout_{uuid.uuid4().hex}",
        user_id=user_id,
        date=datetime.fromisoformat(workout_data["date"]),
        run_type=RunType(workout_data["run_type"]),
        metrics=workout_data["metrics"],
        streams=workout_data.get("streams"),
        perceived_effort=workout_data.get("perceived_effort"),
        notes=workout_data.get("notes"),
        source=workout_data.get("source")
    )

    db.add(workout)
    db.commit()
    db.refresh(workout)

    return {"id": workout.id, "message": "Workout created successfully"}


@app.get("/users/{user_id}/workouts")
async def get_workouts(
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get workouts for a user"""
    query = db.query(DBWorkout).filter(DBWorkout.user_id == user_id)

    if start_date:
        query = query.filter(DBWorkout.date >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(DBWorkout.date <= datetime.fromisoformat(end_date))

    workouts = query.order_by(DBWorkout.date.desc()).limit(limit).all()

    return [
        {
            "id": w.id,
            "date": w.date.isoformat(),
            "run_type": w.run_type.value,
            "metrics": w.metrics,
            "perceived_effort": w.perceived_effort,
            "notes": w.notes,
            "source": w.source
        }
        for w in workouts
    ]


# Goal endpoints
@app.post("/users/{user_id}/goals")
async def create_goal(
    user_id: str,
    goal_data: dict,
    db: Session = Depends(get_db)
):
    """Create a new goal for a user"""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Deactivate existing active goals
    db.query(DBGoal).filter(
        DBGoal.user_id == user_id,
        DBGoal.is_active == True
    ).update({"is_active": False})

    goal = DBGoal(
        id=f"goal_{uuid.uuid4().hex}",
        user_id=user_id,
        race_distance=RaceDistance(goal_data["race_distance"]),
        race_date=date.fromisoformat(goal_data["race_date"]),
        target_time_seconds=goal_data["target_time_seconds"],
        target_speed_mps=goal_data.get("target_speed_mps"),
        is_active=True
    )

    db.add(goal)
    db.commit()
    db.refresh(goal)

    return {"id": goal.id, "message": "Goal created successfully"}


@app.get("/users/{user_id}/goals/active")
async def get_active_goal(user_id: str, db: Session = Depends(get_db)):
    """Get active goal for a user"""
    goal = db.query(DBGoal).filter(
        DBGoal.user_id == user_id,
        DBGoal.is_active == True
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="No active goal found")

    return {
        "id": goal.id,
        "race_distance": goal.race_distance.value,
        "race_date": goal.race_date.isoformat(),
        "target_time_seconds": goal.target_time_seconds,
        "target_speed_mps": goal.target_speed_mps,
        "current_fitness_level": goal.current_fitness_level
    }


# Training program endpoints
@app.post("/users/{user_id}/training-programs/generate")
async def generate_training_program(
    user_id: str,
    start_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate a new training program based on user's goal and workout history"""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get active goal
    goal_db = db.query(DBGoal).filter(
        DBGoal.user_id == user_id,
        DBGoal.is_active == True
    ).first()
    if not goal_db:
        raise HTTPException(status_code=404, detail="No active goal found")

    # Convert to Pydantic model
    goal = Goal(
        race_distance=goal_db.race_distance,
        race_date=goal_db.race_date,
        target_time_seconds=goal_db.target_time_seconds,
        target_speed_mps=goal_db.target_speed_mps
    )

    # Get recent workout history (last 60 days)
    cutoff_date = datetime.now() - timedelta(days=60)
    workouts_db = db.query(DBWorkout).filter(
        DBWorkout.user_id == user_id,
        DBWorkout.date >= cutoff_date
    ).order_by(DBWorkout.date).all()

    # Convert to Pydantic models
    workouts = [
        Workout(
            id=w.id,
            date=w.date,
            run_type=w.run_type,
            metrics=WorkoutMetrics(**w.metrics),
            perceived_effort=w.perceived_effort,
            notes=w.notes,
            source=w.source
        )
        for w in workouts_db
    ]

    # Estimate threshold pace if not set
    threshold_pace = training_load_calc.estimate_threshold_pace(workouts) if workouts else None

    # Generate training program
    program_start = date.fromisoformat(start_date) if start_date else None
    program = ai_coach.generate_training_program(
        goal=goal,
        workout_history=workouts,
        start_date=program_start,
        threshold_pace_mps=threshold_pace
    )

    # Save to database
    # Deactivate existing programs
    db.query(DBTrainingProgram).filter(
        DBTrainingProgram.user_id == user_id,
        DBTrainingProgram.is_active == True
    ).update({"is_active": False})

    program_db = DBTrainingProgram(
        id=f"program_{uuid.uuid4().hex}",
        user_id=user_id,
        goal_id=goal_db.id,
        start_date=program.start_date,
        total_weeks=program.total_weeks,
        rationale=program.rationale,
        is_active=True
    )
    db.add(program_db)

    # Save weekly plans
    for week in program.weeks:
        week_db = DBWeeklyPlan(
            id=f"week_{uuid.uuid4().hex}",
            training_program_id=program_db.id,
            week_number=week.week_number,
            start_date=week.start_date,
            end_date=week.end_date,
            phase=week.phase,
            total_distance=week.total_distance,
            focus=week.focus
        )
        db.add(week_db)

        # Save planned workouts
        for workout in week.workouts:
            planned_db = DBPlannedWorkout(
                id=f"planned_{uuid.uuid4().hex}",
                weekly_plan_id=week_db.id,
                date=workout.date,
                run_type=workout.run_type,
                intensity_zone=workout.intensity_zone,
                target_distance=workout.target_distance,
                target_duration=workout.target_duration,
                target_speed=workout.target_speed,
                description=workout.description,
                notes=workout.notes
            )
            db.add(planned_db)

    db.commit()

    # Update goal with fitness assessment
    goal_db.current_fitness_level = ai_coach.analyze_fitness_level(workouts, threshold_pace)
    db.commit()

    return {
        "program_id": program_db.id,
        "message": "Training program generated successfully",
        "total_weeks": program.total_weeks,
        "start_date": program.start_date.isoformat(),
        "rationale": program.rationale
    }


@app.get("/users/{user_id}/training-programs/active")
async def get_active_program(user_id: str, db: Session = Depends(get_db)):
    """Get active training program with weekly plans"""
    program = db.query(DBTrainingProgram).filter(
        DBTrainingProgram.user_id == user_id,
        DBTrainingProgram.is_active == True
    ).first()

    if not program:
        raise HTTPException(status_code=404, detail="No active training program found")

    # Get weekly plans
    weeks = db.query(DBWeeklyPlan).filter(
        DBWeeklyPlan.training_program_id == program.id
    ).order_by(DBWeeklyPlan.week_number).all()

    return {
        "id": program.id,
        "start_date": program.start_date.isoformat(),
        "total_weeks": program.total_weeks,
        "rationale": program.rationale,
        "weeks": [
            {
                "week_number": w.week_number,
                "start_date": w.start_date.isoformat(),
                "end_date": w.end_date.isoformat(),
                "phase": w.phase.value,
                "total_distance": w.total_distance,
                "focus": w.focus
            }
            for w in weeks
        ]
    }


@app.get("/training-programs/{program_id}/weeks/{week_number}")
async def get_week_details(
    program_id: str,
    week_number: int,
    db: Session = Depends(get_db)
):
    """Get detailed workouts for a specific week"""
    week = db.query(DBWeeklyPlan).filter(
        DBWeeklyPlan.training_program_id == program_id,
        DBWeeklyPlan.week_number == week_number
    ).first()

    if not week:
        raise HTTPException(status_code=404, detail="Week not found")

    # Get planned workouts
    workouts = db.query(DBPlannedWorkout).filter(
        DBPlannedWorkout.weekly_plan_id == week.id
    ).order_by(DBPlannedWorkout.date).all()

    return {
        "week_number": week.week_number,
        "start_date": week.start_date.isoformat(),
        "end_date": week.end_date.isoformat(),
        "phase": week.phase.value,
        "total_distance": week.total_distance,
        "focus": week.focus,
        "workouts": [
            {
                "id": w.id,
                "date": w.date.isoformat(),
                "run_type": w.run_type.value,
                "intensity_zone": w.intensity_zone.value,
                "target_distance": w.target_distance,
                "target_duration": w.target_duration,
                "target_speed": w.target_speed,
                "description": w.description,
                "notes": w.notes,
                "completed": w.completed
            }
            for w in workouts
        ]
    }


# Training load endpoints
@app.get("/users/{user_id}/training-load")
async def get_training_load(
    user_id: str,
    days: int = 42,
    db: Session = Depends(get_db)
):
    """Get training load metrics (CTL/ATL/TSB) for user"""
    cutoff_date = datetime.now() - timedelta(days=days)
    workouts_db = db.query(DBWorkout).filter(
        DBWorkout.user_id == user_id,
        DBWorkout.date >= cutoff_date
    ).order_by(DBWorkout.date).all()

    # Convert to Pydantic models
    workouts = [
        Workout(
            id=w.id,
            date=w.date,
            run_type=w.run_type,
            metrics=WorkoutMetrics(**w.metrics),
            perceived_effort=w.perceived_effort,
            notes=w.notes,
            source=w.source
        )
        for w in workouts_db
    ]

    if not workouts:
        return {
            "message": "No workouts found",
            "ctl": 0,
            "atl": 0,
            "tsb": 0
        }

    # Calculate training load
    threshold_pace = training_load_calc.estimate_threshold_pace(workouts)
    current_load = training_load_calc.get_current_training_load(
        workouts,
        threshold_pace_mps=threshold_pace
    )

    if not current_load:
        return {
            "message": "Unable to calculate training load",
            "ctl": 0,
            "atl": 0,
            "tsb": 0
        }

    return {
        "date": current_load.date.isoformat(),
        "tss": round(current_load.tss, 1),
        "ctl": round(current_load.ctl, 1),
        "atl": round(current_load.atl, 1),
        "tsb": round(current_load.tsb, 1),
        "tsb_interpretation": training_load_calc.interpret_tsb(current_load.tsb),
        "threshold_pace_mps": threshold_pace
    }


# Evaluation endpoints
@app.post("/workouts/{planned_workout_id}/evaluate")
async def evaluate_workout(
    planned_workout_id: str,
    actual_workout_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Evaluate a workout against the plan"""
    planned = db.query(DBPlannedWorkout).filter(
        DBPlannedWorkout.id == planned_workout_id
    ).first()

    if not planned:
        raise HTTPException(status_code=404, detail="Planned workout not found")

    # Get actual workout if provided
    actual_workout = None
    if actual_workout_id:
        actual_db = db.query(DBWorkout).filter(
            DBWorkout.id == actual_workout_id
        ).first()
        if actual_db:
            actual_workout = Workout(
                id=actual_db.id,
                date=actual_db.date,
                run_type=actual_db.run_type,
                metrics=WorkoutMetrics(**actual_db.metrics),
                perceived_effort=actual_db.perceived_effort,
                notes=actual_db.notes,
                source=actual_db.source
            )

    # Convert planned to Pydantic
    from models import PlannedWorkout, IntensityZone
    planned_workout = PlannedWorkout(
        date=planned.date,
        run_type=planned.run_type,
        intensity_zone=planned.intensity_zone,
        target_distance=planned.target_distance,
        target_duration=planned.target_duration,
        target_speed=planned.target_speed,
        description=planned.description,
        notes=planned.notes
    )

    # Evaluate
    evaluation = ai_coach.evaluate_workout(planned_workout, actual_workout)

    # Save evaluation
    eval_db = DBWorkoutEvaluation(
        id=f"eval_{uuid.uuid4().hex}",
        user_id=db.query(DBWeeklyPlan).join(DBPlannedWorkout).join(DBTrainingProgram).filter(
            DBPlannedWorkout.id == planned_workout_id
        ).first().training_program.user_id,
        planned_workout_id=planned_workout_id,
        actual_workout_id=actual_workout_id,
        completed=evaluation.completed,
        adherence_score=evaluation.adherence_score,
        feedback=evaluation.feedback,
        adjustments_needed=evaluation.adjustments_needed
    )
    db.add(eval_db)

    # Update planned workout completion status
    if actual_workout_id:
        planned.completed = True
        planned.actual_workout_id = actual_workout_id

    db.commit()

    return {
        "evaluation_id": eval_db.id,
        "completed": evaluation.completed,
        "adherence_score": evaluation.adherence_score,
        "feedback": evaluation.feedback,
        "adjustments_needed": evaluation.adjustments_needed
    }


# Strava integration endpoints
@app.get("/strava/connect")
async def strava_connect(user_id: str):
    """
    Get Strava authorization URL to connect user account

    Args:
        user_id: User ID to connect Strava account to

    Returns:
        Authorization URL to redirect user to
    """
    # Use user_id as state for CSRF protection
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8000/strava/callback")
    auth_url = strava_client.get_authorization_url(
        redirect_uri=redirect_uri,
        state=user_id
    )

    return {
        "authorization_url": auth_url,
        "message": "Redirect user to this URL to authorize Strava access"
    }


@app.get("/strava/callback")
async def strava_callback(
    code: str,
    state: str,
    scope: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Strava OAuth callback endpoint

    Args:
        code: Authorization code from Strava
        state: User ID passed in state parameter
        scope: Granted scopes
        db: Database session

    Returns:
        Success message with connection details
    """
    user_id = state

    # Verify user exists
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Exchange code for tokens
    token_data = await strava_client.exchange_code_for_token(code)

    # Check if connection already exists
    existing_connection = db.query(DBStravaConnection).filter(
        DBStravaConnection.user_id == user_id
    ).first()

    if existing_connection:
        # Update existing connection
        existing_connection.access_token = token_data["access_token"]
        existing_connection.refresh_token = token_data["refresh_token"]
        existing_connection.expires_at = token_data["expires_at"]
        existing_connection.strava_athlete_id = token_data["athlete"]["id"]
        existing_connection.updated_at = datetime.utcnow()
    else:
        # Create new connection
        connection = DBStravaConnection(
            id=f"strava_{uuid.uuid4().hex}",
            user_id=user_id,
            strava_athlete_id=token_data["athlete"]["id"],
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=token_data["expires_at"]
        )
        db.add(connection)

    db.commit()

    return {
        "message": "Strava account connected successfully",
        "athlete": {
            "id": token_data["athlete"]["id"],
            "firstname": token_data["athlete"]["firstname"],
            "lastname": token_data["athlete"]["lastname"]
        }
    }


@app.post("/users/{user_id}/strava/sync")
async def sync_strava_activities(
    user_id: str,
    days_back: int = 30,
    include_streams: bool = False,
    db: Session = Depends(get_db)
):
    """
    Sync activities from Strava for a user

    Args:
        user_id: User ID
        days_back: Number of days of history to sync
        include_streams: Whether to fetch detailed GPS/HR streams
        db: Database session

    Returns:
        Sync summary with number of activities synced
    """
    # Get user's Strava connection
    connection = db.query(DBStravaConnection).filter(
        DBStravaConnection.user_id == user_id,
        DBStravaConnection.sync_enabled == True
    ).first()

    if not connection:
        raise HTTPException(
            status_code=404,
            detail="No Strava connection found for this user"
        )

    # Refresh token if needed
    if connection.expires_at <= int(datetime.now().timestamp()):
        token_data = await strava_client.refresh_access_token(connection.refresh_token)
        connection.access_token = token_data["access_token"]
        connection.refresh_token = token_data["refresh_token"]
        connection.expires_at = token_data["expires_at"]
        db.commit()

    # Sync activities
    after_date = datetime.now() - timedelta(days=days_back)
    workouts = await strava_client.sync_activities(
        access_token=connection.access_token,
        user_id=user_id,
        after=after_date,
        include_streams=include_streams
    )

    # Save workouts to database
    new_count = 0
    updated_count = 0

    for workout in workouts:
        strava_activity_id = str(workout.id).replace("strava_", "")

        # Check if workout already exists
        existing = db.query(DBWorkout).filter(
            DBWorkout.strava_activity_id == strava_activity_id
        ).first()

        if existing:
            # Update existing workout
            existing.date = workout.date
            existing.run_type = workout.run_type
            existing.metrics = workout.metrics.model_dump()
            if workout.streams:
                existing.streams = workout.streams.model_dump()
            existing.notes = workout.notes
            updated_count += 1
        else:
            # Create new workout
            workout_db = DBWorkout(
                id=f"workout_{uuid.uuid4().hex}",
                user_id=user_id,
                date=workout.date,
                run_type=workout.run_type,
                metrics=workout.metrics.model_dump(),
                streams=workout.streams.model_dump() if workout.streams else None,
                notes=workout.notes,
                source="strava",
                strava_activity_id=strava_activity_id
            )
            db.add(workout_db)
            new_count += 1

    # Update last sync time
    connection.last_sync = datetime.utcnow()
    db.commit()

    return {
        "message": "Strava sync completed",
        "new_activities": new_count,
        "updated_activities": updated_count,
        "total_synced": new_count + updated_count,
        "last_sync": connection.last_sync.isoformat()
    }


@app.get("/users/{user_id}/strava/status")
async def get_strava_connection_status(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get Strava connection status for a user"""
    connection = db.query(DBStravaConnection).filter(
        DBStravaConnection.user_id == user_id
    ).first()

    if not connection:
        return {
            "connected": False,
            "message": "No Strava connection found"
        }

    return {
        "connected": True,
        "strava_athlete_id": connection.strava_athlete_id,
        "last_sync": connection.last_sync.isoformat() if connection.last_sync else None,
        "sync_enabled": connection.sync_enabled,
        "connected_at": connection.connected_at.isoformat()
    }


@app.delete("/users/{user_id}/strava/disconnect")
async def disconnect_strava(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Disconnect Strava account from user"""
    connection = db.query(DBStravaConnection).filter(
        DBStravaConnection.user_id == user_id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="No Strava connection found")

    db.delete(connection)
    db.commit()

    return {"message": "Strava account disconnected successfully"}


# Strava webhook endpoints (for real-time activity updates)
@app.get("/strava/webhook")
async def strava_webhook_verify(
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: str = None
):
    """
    Strava webhook verification endpoint

    Strava will call this with a challenge to verify the webhook
    """
    verify_token = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "STRAVA_WEBHOOK")

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return {"hub.challenge": hub_challenge}

    raise HTTPException(status_code=403, detail="Invalid verification token")


@app.post("/strava/webhook")
async def strava_webhook_event(
    event_data: dict,
    db: Session = Depends(get_db)
):
    """
    Strava webhook event handler

    Receives real-time updates when athletes create/update activities
    """
    # Extract event details
    object_type = event_data.get("object_type")
    aspect_type = event_data.get("aspect_type")
    object_id = event_data.get("object_id")
    owner_id = event_data.get("owner_id")

    # Only process activity events
    if object_type != "activity":
        return {"message": "Event ignored - not an activity"}

    # Find user with this Strava athlete ID
    connection = db.query(DBStravaConnection).filter(
        DBStravaConnection.strava_athlete_id == owner_id,
        DBStravaConnection.sync_enabled == True
    ).first()

    if not connection:
        return {"message": "User not found or sync disabled"}

    # Handle create/update events
    if aspect_type in ["create", "update"]:
        # Refresh token if needed
        if connection.expires_at <= int(datetime.now().timestamp()):
            token_data = await strava_client.refresh_access_token(connection.refresh_token)
            connection.access_token = token_data["access_token"]
            connection.refresh_token = token_data["refresh_token"]
            connection.expires_at = token_data["expires_at"]
            db.commit()

        # Fetch activity details
        try:
            activity = await strava_client.get_activity_details(
                connection.access_token,
                object_id
            )

            # Only process runs
            if activity.get("type") == "Run":
                workout = strava_client.convert_activity_to_workout(
                    activity,
                    connection.user_id
                )

                strava_activity_id = str(object_id)

                # Check if exists
                existing = db.query(DBWorkout).filter(
                    DBWorkout.strava_activity_id == strava_activity_id
                ).first()

                if existing:
                    # Update
                    existing.date = workout.date
                    existing.run_type = workout.run_type
                    existing.metrics = workout.metrics.model_dump()
                    existing.notes = workout.notes
                else:
                    # Create
                    workout_db = DBWorkout(
                        id=f"workout_{uuid.uuid4().hex}",
                        user_id=connection.user_id,
                        date=workout.date,
                        run_type=workout.run_type,
                        metrics=workout.metrics.model_dump(),
                        notes=workout.notes,
                        source="strava",
                        strava_activity_id=strava_activity_id
                    )
                    db.add(workout_db)

                db.commit()
                return {"message": "Activity synced successfully"}

        except Exception as e:
            return {"message": f"Error syncing activity: {str(e)}"}

    # Handle delete events
    elif aspect_type == "delete":
        workout = db.query(DBWorkout).filter(
            DBWorkout.strava_activity_id == str(object_id)
        ).first()

        if workout:
            db.delete(workout)
            db.commit()
            return {"message": "Activity deleted"}

    return {"message": "Event processed"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
