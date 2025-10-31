"""
Example usage of the AI Fitness Coach
Demonstrates the core functionality without needing a running API server
"""
from datetime import datetime, date, timedelta
from models import (
    Workout, WorkoutMetrics, Goal, RaceDistance, RunType
)
from ai_coach import AICoach
from training_load import TrainingLoadCalculator
from utils import format_pace, format_distance, format_duration
import os

# Make sure you have ANTHROPIC_API_KEY in your .env file
# or set it here: os.environ["ANTHROPIC_API_KEY"] = "your-key"


def create_sample_workouts() -> list[Workout]:
    """Create sample workout history for the last 30 days"""
    workouts = []
    base_date = datetime.now() - timedelta(days=30)

    # Week 1 - Base building
    workouts.extend([
        Workout(
            id="w1",
            date=base_date,
            run_type=RunType.EASY,
            metrics=WorkoutMetrics(
                distance=6000.0,  # 6km
                moving_time=2160.0,  # 36 minutes
                elapsed_time=2160.0,
                average_speed=2.78,  # ~6:00/km pace
                average_heartrate=145
            ),
            perceived_effort=4,
            notes="Morning easy run"
        ),
        Workout(
            id="w2",
            date=base_date + timedelta(days=2),
            run_type=RunType.TEMPO,
            metrics=WorkoutMetrics(
                distance=8000.0,
                moving_time=2400.0,  # 40 min
                elapsed_time=2400.0,
                average_speed=3.33,  # ~5:00/km
                average_heartrate=165,
                total_elevation_gain=50.0
            ),
            perceived_effort=7,
            notes="Tempo run felt challenging but good"
        ),
        Workout(
            id="w3",
            date=base_date + timedelta(days=4),
            run_type=RunType.LONG,
            metrics=WorkoutMetrics(
                distance=15000.0,  # 15km
                moving_time=5400.0,  # 90 min
                elapsed_time=5520.0,
                average_speed=2.78,
                average_heartrate=150,
                total_elevation_gain=120.0
            ),
            perceived_effort=6,
            notes="Long run, felt strong"
        )
    ])

    # Week 2 - Building
    week2_start = base_date + timedelta(days=7)
    workouts.extend([
        Workout(
            id="w4",
            date=week2_start,
            run_type=RunType.EASY,
            metrics=WorkoutMetrics(
                distance=7000.0,
                moving_time=2520.0,
                elapsed_time=2520.0,
                average_speed=2.78,
                average_heartrate=143
            ),
            perceived_effort=3
        ),
        Workout(
            id="w5",
            date=week2_start + timedelta(days=2),
            run_type=RunType.INTERVALS,
            metrics=WorkoutMetrics(
                distance=10000.0,
                moving_time=3000.0,
                elapsed_time=3300.0,  # includes rest intervals
                average_speed=3.33,
                max_speed=4.17,  # ~4:00/km
                average_heartrate=170,
                max_heartrate=185
            ),
            perceived_effort=8,
            notes="6x800m @ 3:20, felt great on intervals"
        ),
        Workout(
            id="w6",
            date=week2_start + timedelta(days=5),
            run_type=RunType.LONG,
            metrics=WorkoutMetrics(
                distance=18000.0,
                moving_time=6480.0,
                elapsed_time=6600.0,
                average_speed=2.78,
                average_heartrate=152,
                total_elevation_gain=180.0
            ),
            perceived_effort=7,
            notes="Long run, last 5k felt tough"
        )
    ])

    # Week 3 - Peak
    week3_start = base_date + timedelta(days=14)
    workouts.extend([
        Workout(
            id="w7",
            date=week3_start + timedelta(days=1),
            run_type=RunType.RECOVERY,
            metrics=WorkoutMetrics(
                distance=5000.0,
                moving_time=2100.0,
                elapsed_time=2100.0,
                average_speed=2.38,  # slow recovery pace
                average_heartrate=135
            ),
            perceived_effort=2,
            notes="Easy recovery run"
        ),
        Workout(
            id="w8",
            date=week3_start + timedelta(days=3),
            run_type=RunType.TEMPO,
            metrics=WorkoutMetrics(
                distance=10000.0,
                moving_time=3000.0,
                elapsed_time=3000.0,
                average_speed=3.33,
                average_heartrate=168
            ),
            perceived_effort=7,
            notes="Solid tempo effort"
        ),
        Workout(
            id="w9",
            date=week3_start + timedelta(days=6),
            run_type=RunType.LONG,
            metrics=WorkoutMetrics(
                distance=20000.0,  # 20km
                moving_time=7200.0,  # 2 hours
                elapsed_time=7320.0,
                average_speed=2.78,
                average_heartrate=155,
                total_elevation_gain=200.0
            ),
            perceived_effort=8,
            notes="Longest run so far, feeling tired but accomplished"
        )
    ])

    # Week 4 - Recent
    week4_start = base_date + timedelta(days=21)
    workouts.extend([
        Workout(
            id="w10",
            date=week4_start + timedelta(days=1),
            run_type=RunType.EASY,
            metrics=WorkoutMetrics(
                distance=8000.0,
                moving_time=2880.0,
                elapsed_time=2880.0,
                average_speed=2.78,
                average_heartrate=147
            ),
            perceived_effort=4
        ),
        Workout(
            id="w11",
            date=week4_start + timedelta(days=3),
            run_type=RunType.HILL_REPEATS,
            metrics=WorkoutMetrics(
                distance=8000.0,
                moving_time=3000.0,
                elapsed_time=3300.0,
                average_speed=2.67,
                average_heartrate=172,
                max_heartrate=188,
                total_elevation_gain=250.0
            ),
            perceived_effort=9,
            notes="8x hill repeats, tough but good"
        )
    ])

    return workouts


def main():
    """Run example demonstration"""
    print("=" * 80)
    print("AI FITNESS COACH - EXAMPLE DEMONSTRATION")
    print("=" * 80)
    print()

    # Initialize
    print("Initializing AI Coach...")
    coach = AICoach()
    calc = TrainingLoadCalculator()
    print("✓ AI Coach initialized")
    print()

    # Create sample data
    print("Creating sample workout history (last 30 days)...")
    workouts = create_sample_workouts()
    print(f"✓ Created {len(workouts)} sample workouts")
    print()

    # Show workout summary
    print("WORKOUT HISTORY:")
    print("-" * 80)
    for w in sorted(workouts, key=lambda x: x.date)[-5:]:  # Show last 5
        pace = format_pace(w.metrics.average_speed) if w.metrics.average_speed else "N/A"
        print(f"{w.date.strftime('%Y-%m-%d')} | {w.run_type.value.title():12} | "
              f"{format_distance(w.metrics.distance):10} | {pace:10} | RPE: {w.perceived_effort or '-'}")
    print()

    # Calculate training load
    print("TRAINING LOAD METRICS:")
    print("-" * 80)
    threshold_pace = calc.estimate_threshold_pace(workouts)
    if threshold_pace:
        print(f"Estimated Threshold Pace: {format_pace(threshold_pace)}")

    current_load = calc.get_current_training_load(workouts, threshold_pace)
    if current_load:
        print(f"CTL (Fitness):  {current_load.ctl:.1f}")
        print(f"ATL (Fatigue):  {current_load.atl:.1f}")
        print(f"TSB (Form):     {current_load.tsb:.1f}")
        print(f"Status:         {calc.interpret_tsb(current_load.tsb)}")
    print()

    # Analyze fitness
    print("FITNESS ASSESSMENT:")
    print("-" * 80)
    fitness_assessment = coach.analyze_fitness_level(workouts, threshold_pace)
    print(fitness_assessment)
    print()

    # Create goal
    print("GOAL SETUP:")
    print("-" * 80)
    race_date = date.today() + timedelta(days=120)  # Race in ~4 months
    goal = Goal(
        race_distance=RaceDistance.MARATHON,
        race_date=race_date,
        target_time_seconds=10800,  # 3:00:00 marathon
    )
    print(f"Race:        {goal.race_distance.value.replace('_', ' ').title()}")
    print(f"Date:        {goal.race_date}")
    print(f"Target:      {format_duration(goal.target_time_seconds)}")
    print(f"Target Pace: {format_pace(goal.target_speed_mps)}")
    print()

    # Generate training program
    print("GENERATING TRAINING PROGRAM...")
    print("-" * 80)
    print("This may take 30-60 seconds as Claude analyzes your history and creates")
    print("a personalized training plan...")
    print()

    program = coach.generate_training_program(
        goal=goal,
        workout_history=workouts,
        threshold_pace_mps=threshold_pace
    )

    print(f"✓ Generated {program.total_weeks}-week training program")
    print()

    # Show program overview
    print("TRAINING PROGRAM OVERVIEW:")
    print("-" * 80)
    print(f"Start Date:   {program.start_date}")
    print(f"Total Weeks:  {program.total_weeks}")
    print()
    print("RATIONALE:")
    print(program.rationale)
    print()

    # Show first 2 weeks in detail
    print("FIRST 2 WEEKS:")
    print("=" * 80)
    for week in program.weeks[:2]:
        print(f"\nWEEK {week.week_number} | {week.phase.value.upper()} PHASE")
        print(f"Dates: {week.start_date} to {week.end_date}")
        print(f"Total Distance: {format_distance(week.total_distance)}")
        print(f"Focus: {week.focus}")
        print()
        print("Workouts:")
        print("-" * 80)

        for workout in week.workouts:
            target = ""
            if workout.target_distance:
                target = f"{format_distance(workout.target_distance)}"
            elif workout.target_duration:
                target = f"{format_duration(workout.target_duration)}"

            pace_str = ""
            if workout.target_speed:
                pace_str = f"@ {format_pace(workout.target_speed)}"

            print(f"  {workout.date.strftime('%a %m/%d')} | "
                  f"{workout.run_type.value.title():12} | "
                  f"Zone {workout.intensity_zone.value} | "
                  f"{target:10} {pace_str}")
            print(f"           {workout.description}")
            if workout.notes:
                print(f"           Note: {workout.notes}")
            print()

    # Show weekly progression
    print("\nWEEKLY DISTANCE PROGRESSION:")
    print("-" * 80)
    for week in program.weeks:
        bar_length = int(week.total_distance / 1000)  # Scale for display
        bar = "█" * bar_length
        print(f"Week {week.week_number:2d} ({week.phase.value:8}): {bar} "
              f"{format_distance(week.total_distance)}")

    print()
    print("=" * 80)
    print("EXAMPLE COMPLETE!")
    print()
    print("Next steps:")
    print("1. Set up database: alembic upgrade head")
    print("2. Start API server: python app.py")
    print("3. Try the REST API endpoints")
    print("4. Integrate with fitness devices (Strava, Garmin, etc.)")
    print("=" * 80)


if __name__ == "__main__":
    main()
