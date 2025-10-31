"""
AI Coach - Claude-powered training program generation and evaluation
"""
import os
import json
from typing import List, Optional
from datetime import datetime, date, timedelta
import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv

from models import (
    Workout, Goal, TrainingProgram, WeeklyPlan, PlannedWorkout,
    WorkoutEvaluation, WeeklyEvaluation, RaceDistance, TrainingPhase,
    RunType, IntensityZone
)
from utils import format_pace, format_distance, format_duration
from training_load import TrainingLoadCalculator, TrainingLoad

load_dotenv()


class AICoach:
    """AI-powered fitness coach using Claude"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI Coach with Anthropic API key"""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in environment or passed to constructor")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.training_load_calc = TrainingLoadCalculator()

    def analyze_fitness_level(
        self,
        workout_history: List[Workout],
        threshold_pace_mps: Optional[float] = None,
        threshold_heartrate: Optional[float] = None
    ) -> str:
        """
        Analyze recent workout history to assess current fitness level

        Args:
            workout_history: List of recent workouts (last 30+ days)
            threshold_pace_mps: Optional threshold pace for TSS calculation
            threshold_heartrate: Optional threshold HR for TSS calculation

        Returns:
            Text assessment of current fitness level
        """
        if not workout_history:
            return "No workout history available. Starting from beginner level."

        # Calculate training load metrics
        if threshold_pace_mps is None:
            threshold_pace_mps = self.training_load_calc.estimate_threshold_pace(workout_history)

        current_load = self.training_load_calc.get_current_training_load(
            workout_history,
            threshold_pace_mps,
            threshold_heartrate
        )

        # Prepare workout summary for Claude
        workout_summary = self._summarize_workouts(workout_history)

        # Add training load context
        load_summary = ""
        if current_load:
            tsb_interpretation = self.training_load_calc.interpret_tsb(current_load.tsb)
            load_summary = f"""
TRAINING LOAD METRICS (TrainingPeaks methodology):
- CTL (Chronic Training Load/Fitness): {current_load.ctl:.1f}
- ATL (Acute Training Load/Fatigue): {current_load.atl:.1f}
- TSB (Training Stress Balance/Form): {current_load.tsb:.1f} - {tsb_interpretation}
- Recent TSS: {current_load.tss:.1f}

Interpretation:
- CTL represents fitness built over ~6 weeks
- ATL represents fatigue from last ~7 days
- TSB (CTL - ATL) indicates freshness/form
  * +15 to +25: Optimal race readiness
  * -10 to -30: Productive training zone
  * < -30: Risk of overtraining
"""

        prompt = f"""You are an expert running coach. Analyze this athlete's recent workout history and provide a comprehensive fitness assessment.

Recent Workout History:
{workout_summary}
{load_summary}

Provide:
1. Current fitness level (beginner/intermediate/advanced)
2. Weekly mileage capacity
3. Strengths and weaknesses
4. Recent training consistency
5. Key metrics (average pace, typical run distance, etc.)
6. Training load analysis (CTL/ATL/TSB implications)

Keep the assessment concise but informative (3-4 paragraphs)."""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        return message.content[0].text if isinstance(message.content[0], TextBlock) else str(message.content[0])

    def generate_training_program(
        self,
        goal: Goal,
        workout_history: List[Workout],
        start_date: Optional[date] = None,
        threshold_pace_mps: Optional[float] = None,
        threshold_heartrate: Optional[float] = None
    ) -> TrainingProgram:
        """
        Generate a complete training program based on goal and fitness level

        Args:
            goal: Training goal (race, distance, target time)
            workout_history: Recent workout history for fitness assessment
            start_date: Program start date (defaults to next Monday)
            threshold_pace_mps: Optional threshold pace
            threshold_heartrate: Optional threshold HR

        Returns:
            Complete training program with weekly plans
        """
        # Assess current fitness with training load metrics
        fitness_assessment = self.analyze_fitness_level(
            workout_history,
            threshold_pace_mps,
            threshold_heartrate
        )

        # Calculate program duration and start date
        if start_date is None:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            start_date = today + timedelta(days=days_until_monday if days_until_monday > 0 else 7)

        weeks_until_race = (goal.race_date - start_date).days // 7
        program_weeks = min(max(weeks_until_race, 8), 20)  # 8-20 weeks

        # Prepare context for Claude
        workout_summary = self._summarize_workouts(workout_history)
        goal_description = self._format_goal(goal)

        prompt = f"""You are an expert running coach. Create a detailed {program_weeks}-week training program for this athlete.

ATHLETE PROFILE:
{fitness_assessment}

GOAL:
{goal_description}

RECENT TRAINING:
{workout_summary}

PROGRAM REQUIREMENTS:
- Start Date: {start_date.isoformat()}
- Race Date: {goal.race_date.isoformat()}
- Duration: {program_weeks} weeks
- Phases: Base → Build → Peak → Taper

Create a complete training program with:
1. Overall program rationale and strategy
2. Week-by-week breakdown with:
   - Training phase (base/build/peak/taper/recovery)
   - Weekly focus and goals
   - Total weekly distance
   - Daily workouts with specific details:
     * Type (easy/recovery/long/tempo/intervals/hill_repeats/progression/rest)
     * Intensity zone (1-5)
     * Target distance OR duration
     * Target pace/speed
     * Detailed description
     * Coaching notes

Return ONLY valid JSON matching this structure:
{{
  "rationale": "Overall program explanation...",
  "weeks": [
    {{
      "week_number": 1,
      "start_date": "2025-11-03",
      "end_date": "2025-11-09",
      "phase": "base",
      "total_distance": 25000.0,
      "focus": "Building aerobic base...",
      "workouts": [
        {{
          "date": "2025-11-03",
          "run_type": "easy",
          "intensity_zone": 2,
          "target_distance": 6000.0,
          "target_duration": null,
          "target_speed": 2.5,
          "description": "Easy 6km run at conversational pace",
          "notes": "Focus on form and breathing"
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- All distances in METERS
- All durations in SECONDS
- All speeds in METERS PER SECOND
- Dates in YYYY-MM-DD format
- Include 3-6 runs per week + rest days
- Progress gradually (10% rule)
- Include variety (easy runs, tempo, intervals, long runs)
"""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse Claude's response
        response_text = message.content[0].text if isinstance(message.content[0], TextBlock) else str(message.content[0])

        # Extract JSON from response (Claude might include explanatory text)
        program_data = self._extract_json(response_text)

        # Convert to TrainingProgram object
        weeks = []
        for week_data in program_data["weeks"]:
            workouts = [
                PlannedWorkout(
                    date=date.fromisoformat(w["date"]),
                    run_type=RunType(w["run_type"]),
                    intensity_zone=IntensityZone(w["intensity_zone"]),
                    target_distance=w.get("target_distance"),
                    target_duration=w.get("target_duration"),
                    target_speed=w.get("target_speed"),
                    description=w["description"],
                    notes=w.get("notes")
                )
                for w in week_data["workouts"]
            ]

            weeks.append(WeeklyPlan(
                week_number=week_data["week_number"],
                start_date=date.fromisoformat(week_data["start_date"]),
                end_date=date.fromisoformat(week_data["end_date"]),
                phase=TrainingPhase(week_data["phase"]),
                total_distance=week_data["total_distance"],
                workouts=workouts,
                focus=week_data["focus"]
            ))

        program = TrainingProgram(
            id=f"program_{datetime.now().timestamp()}",
            goal=goal,
            start_date=start_date,
            weeks=weeks,
            total_weeks=program_weeks,
            rationale=program_data["rationale"]
        )

        return program

    def evaluate_workout(
        self,
        planned: PlannedWorkout,
        actual: Optional[Workout]
    ) -> WorkoutEvaluation:
        """
        Evaluate a completed workout against the plan

        Args:
            planned: The planned workout
            actual: The actual completed workout (None if skipped)

        Returns:
            Workout evaluation with feedback and adherence score
        """
        if actual is None:
            return WorkoutEvaluation(
                planned=planned,
                actual=None,
                completed=False,
                adherence_score=0.0,
                feedback="Workout was not completed. Consider making up this workout if possible, or adjust the upcoming schedule.",
                adjustments_needed=True
            )

        # Prepare comparison for Claude
        planned_summary = self._format_planned_workout(planned)
        actual_summary = self._format_actual_workout(actual)

        prompt = f"""You are an expert running coach. Evaluate this athlete's workout performance.

PLANNED WORKOUT:
{planned_summary}

ACTUAL WORKOUT:
{actual_summary}

Provide:
1. Adherence score (0-100): How well did they follow the plan?
2. Feedback: Constructive analysis of the performance
3. Adjustments needed: Should we modify upcoming workouts? (true/false)

Consider:
- Distance/duration variance
- Pace/intensity adherence
- Effort level (RPE)
- Context from notes

Return ONLY valid JSON:
{{
  "adherence_score": 85.0,
  "feedback": "Great job completing...",
  "adjustments_needed": false
}}"""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text if isinstance(message.content[0], TextBlock) else str(message.content[0])
        eval_data = self._extract_json(response_text)

        return WorkoutEvaluation(
            planned=planned,
            actual=actual,
            completed=True,
            adherence_score=eval_data["adherence_score"],
            feedback=eval_data["feedback"],
            adjustments_needed=eval_data["adjustments_needed"]
        )

    def evaluate_week(
        self,
        week_plan: WeeklyPlan,
        workout_evaluations: List[WorkoutEvaluation]
    ) -> WeeklyEvaluation:
        """
        Evaluate a completed week of training

        Args:
            week_plan: The weekly plan
            workout_evaluations: Evaluations for each workout

        Returns:
            Weekly evaluation with summary and recommendations
        """
        completed_count = sum(1 for e in workout_evaluations if e.completed)
        completion_rate = (completed_count / len(workout_evaluations)) * 100

        total_distance = sum(
            e.actual.metrics.distance
            for e in workout_evaluations
            if e.actual is not None
        )

        # Prepare week summary for Claude
        week_summary = self._format_week_summary(week_plan, workout_evaluations)

        prompt = f"""You are an expert running coach. Evaluate this athlete's training week.

WEEK SUMMARY:
{week_summary}

Provide:
1. Weekly feedback: Overall performance analysis
2. Recommended adjustments: Specific changes for upcoming weeks
3. Fatigue assessment: Signs of overtraining or undertraining

Consider:
- Completion rate
- Total volume vs planned
- Consistency of adherence scores
- Patterns in missed workouts
- Recovery indicators

Return ONLY valid JSON:
{{
  "weekly_feedback": "This week showed...",
  "recommended_adjustments": "Consider...",
  "fatigue_assessment": "Athlete appears..."
}}"""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=768,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text if isinstance(message.content[0], TextBlock) else str(message.content[0])
        eval_data = self._extract_json(response_text)

        return WeeklyEvaluation(
            week_plan=week_plan,
            workout_evaluations=workout_evaluations,
            completion_rate=completion_rate,
            total_distance_actual=total_distance,
            weekly_feedback=eval_data["weekly_feedback"],
            recommended_adjustments=eval_data.get("recommended_adjustments"),
            fatigue_assessment=eval_data.get("fatigue_assessment")
        )

    # Helper methods

    def _summarize_workouts(self, workouts: List[Workout]) -> str:
        """Create a text summary of workout history"""
        if not workouts:
            return "No recent workouts"

        lines = []
        for w in sorted(workouts, key=lambda x: x.date, reverse=True)[:20]:  # Last 20 workouts
            pace = format_pace(w.metrics.average_speed) if w.metrics.average_speed else "N/A"
            distance = format_distance(w.metrics.distance)
            duration = format_duration(w.metrics.moving_time)
            lines.append(
                f"- {w.date.date()}: {w.run_type.value.title()} | "
                f"{distance} in {duration} | Pace: {pace} | "
                f"RPE: {w.perceived_effort or 'N/A'}"
            )

        return "\n".join(lines)

    def _format_goal(self, goal: Goal) -> str:
        """Format goal as readable text"""
        distance_map = {
            RaceDistance.FIVE_K: "5K",
            RaceDistance.TEN_K: "10K",
            RaceDistance.HALF_MARATHON: "Half Marathon",
            RaceDistance.MARATHON: "Marathon",
            RaceDistance.ULTRA_50K: "50K Ultra",
            RaceDistance.ULTRA_50MI: "50-Mile Ultra",
            RaceDistance.ULTRA_100K: "100K Ultra",
            RaceDistance.ULTRA_100MI: "100-Mile Ultra",
        }
        distance_name = distance_map.get(goal.race_distance, goal.race_distance.value)
        target_time = format_duration(goal.target_time_seconds)
        target_pace = format_pace(goal.target_speed_mps) if goal.target_speed_mps else "N/A"

        return f"{distance_name} on {goal.race_date} | Target: {target_time} ({target_pace})"

    def _format_planned_workout(self, workout: PlannedWorkout) -> str:
        """Format planned workout as text"""
        parts = [
            f"Type: {workout.run_type.value.title()}",
            f"Intensity: Zone {workout.intensity_zone.value}",
            f"Description: {workout.description}"
        ]
        if workout.target_distance:
            parts.append(f"Target Distance: {format_distance(workout.target_distance)}")
        if workout.target_duration:
            parts.append(f"Target Duration: {format_duration(workout.target_duration)}")
        if workout.target_speed:
            parts.append(f"Target Pace: {format_pace(workout.target_speed)}")
        if workout.notes:
            parts.append(f"Notes: {workout.notes}")

        return "\n".join(parts)

    def _format_actual_workout(self, workout: Workout) -> str:
        """Format actual workout as text"""
        metrics = workout.metrics
        pace = format_pace(metrics.average_speed) if metrics.average_speed else "N/A"

        parts = [
            f"Type: {workout.run_type.value.title()}",
            f"Distance: {format_distance(metrics.distance)}",
            f"Duration: {format_duration(metrics.moving_time)}",
            f"Pace: {pace}",
        ]

        if metrics.average_heartrate:
            parts.append(f"Avg HR: {metrics.average_heartrate:.0f} bpm")
        if workout.perceived_effort:
            parts.append(f"RPE: {workout.perceived_effort}/10")
        if workout.notes:
            parts.append(f"Notes: {workout.notes}")

        return "\n".join(parts)

    def _format_week_summary(
        self,
        week_plan: WeeklyPlan,
        evaluations: List[WorkoutEvaluation]
    ) -> str:
        """Format week summary for evaluation"""
        lines = [
            f"Week {week_plan.week_number} | Phase: {week_plan.phase.value.title()}",
            f"Focus: {week_plan.focus}",
            f"Planned Distance: {format_distance(week_plan.total_distance)}",
            f"",
            "Workouts:"
        ]

        for eval in evaluations:
            status = "✓ Completed" if eval.completed else "✗ Skipped"
            score = f"({eval.adherence_score:.0f}%)" if eval.completed else ""
            lines.append(f"- {eval.planned.date}: {eval.planned.run_type.value.title()} {status} {score}")

        return "\n".join(lines)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from Claude's response (handles markdown code blocks)"""
        # Try to find JSON in markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        # Remove any leading/trailing whitespace and parse
        return json.loads(text.strip())
