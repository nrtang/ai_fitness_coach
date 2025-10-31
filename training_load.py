"""
Training Load Calculations - TSS, CTL, ATL, TSB
Based on TrainingPeaks methodology
"""
from typing import List, Tuple, Optional
from datetime import date, timedelta
from dataclasses import dataclass
from models import Workout, WorkoutMetrics


@dataclass
class TrainingLoad:
    """Training load metrics for a specific date"""
    date: date
    tss: float  # Training Stress Score for the day
    ctl: float  # Chronic Training Load (Fitness)
    atl: float  # Acute Training Load (Fatigue)
    tsb: float  # Training Stress Balance (Form)


class TrainingLoadCalculator:
    """Calculate training load metrics (TSS, CTL, ATL, TSB)"""

    # Time constants for exponentially weighted moving averages
    CTL_TIME_CONSTANT = 42  # days (fitness)
    ATL_TIME_CONSTANT = 7   # days (fatigue)

    def __init__(self, threshold_pace_mps: Optional[float] = None):
        """
        Initialize calculator

        Args:
            threshold_pace_mps: Functional Threshold Pace in meters per second
                              (fastest pace sustainable for 1 hour)
        """
        self.threshold_pace_mps = threshold_pace_mps

    def calculate_tss(
        self,
        duration_seconds: float,
        average_speed_mps: float,
        threshold_pace_mps: Optional[float] = None
    ) -> float:
        """
        Calculate Training Stress Score (TSS) for a workout

        Simplified formula:
        TSS = (duration_hours * IF^2 * 100)

        Where IF (Intensity Factor) = average_speed / threshold_speed

        Args:
            duration_seconds: Workout duration in seconds
            average_speed_mps: Average speed in meters per second
            threshold_pace_mps: Threshold pace (overrides instance value)

        Returns:
            Training Stress Score
        """
        threshold = threshold_pace_mps or self.threshold_pace_mps

        if not threshold or threshold <= 0:
            # Fallback: estimate TSS from duration and rough intensity
            # ~50 TSS per hour for moderate effort
            return (duration_seconds / 3600.0) * 50.0

        # Calculate Intensity Factor (IF)
        intensity_factor = average_speed_mps / threshold

        # Calculate TSS
        duration_hours = duration_seconds / 3600.0
        tss = duration_hours * (intensity_factor ** 2) * 100.0

        return max(0.0, tss)

    def calculate_tss_with_elevation(
        self,
        duration_seconds: float,
        distance_meters: float,
        elevation_gain_meters: float,
        threshold_pace_mps: Optional[float] = None
    ) -> float:
        """
        Calculate TSS with elevation adjustment (simplified NGP approach)

        Normalized Graded Pace (NGP) accounts for hills by adding equivalent
        flat running distance for vertical gain.

        Rule of thumb: 10m elevation gain ≈ 100m horizontal distance

        Args:
            duration_seconds: Workout duration
            distance_meters: Actual distance covered
            elevation_gain_meters: Total elevation gain
            threshold_pace_mps: Threshold pace

        Returns:
            Training Stress Score adjusted for elevation
        """
        # Adjust distance for elevation gain
        elevation_penalty = elevation_gain_meters * 10.0
        normalized_distance = distance_meters + elevation_penalty

        # Calculate normalized speed
        normalized_speed_mps = normalized_distance / duration_seconds if duration_seconds > 0 else 0

        return self.calculate_tss(duration_seconds, normalized_speed_mps, threshold_pace_mps)

    def calculate_hrss(
        self,
        duration_seconds: float,
        average_heartrate: float,
        threshold_heartrate: float
    ) -> float:
        """
        Calculate Heart Rate Training Stress Score (hrTSS)

        Similar to TSS but based on heart rate instead of pace

        Args:
            duration_seconds: Workout duration
            average_heartrate: Average heart rate (bpm)
            threshold_heartrate: Lactate threshold heart rate (bpm)

        Returns:
            Heart Rate Training Stress Score
        """
        if threshold_heartrate <= 0:
            return (duration_seconds / 3600.0) * 50.0

        # Calculate HR Intensity Factor
        hr_intensity_factor = average_heartrate / threshold_heartrate

        # Calculate hrTSS
        duration_hours = duration_seconds / 3600.0
        hrss = duration_hours * (hr_intensity_factor ** 2) * 100.0

        return max(0.0, hrss)

    def calculate_workout_tss(
        self,
        workout: Workout,
        threshold_pace_mps: Optional[float] = None,
        threshold_heartrate: Optional[float] = None
    ) -> float:
        """
        Calculate TSS for a workout, choosing best available method

        Priority:
        1. Pace-based with elevation (if available)
        2. Pace-based (if threshold pace available)
        3. Heart rate-based (if HR data and threshold available)
        4. Duration-based estimation

        Args:
            workout: Workout object
            threshold_pace_mps: Override threshold pace
            threshold_heartrate: Threshold heart rate for hrTSS

        Returns:
            Training Stress Score
        """
        metrics = workout.metrics
        threshold_pace = threshold_pace_mps or self.threshold_pace_mps

        # Method 1: Pace + elevation
        if (threshold_pace and metrics.average_speed and
            metrics.total_elevation_gain is not None):
            return self.calculate_tss_with_elevation(
                metrics.moving_time,
                metrics.distance,
                metrics.total_elevation_gain,
                threshold_pace
            )

        # Method 2: Pace-based
        if threshold_pace and metrics.average_speed:
            return self.calculate_tss(
                metrics.moving_time,
                metrics.average_speed,
                threshold_pace
            )

        # Method 3: Heart rate-based
        if threshold_heartrate and metrics.average_heartrate:
            return self.calculate_hrss(
                metrics.moving_time,
                metrics.average_heartrate,
                threshold_heartrate
            )

        # Method 4: Estimation based on duration
        return (metrics.moving_time / 3600.0) * 50.0

    def calculate_ctl_atl_tsb(
        self,
        tss_history: List[Tuple[date, float]],
        initial_ctl: float = 0.0,
        initial_atl: float = 0.0
    ) -> List[TrainingLoad]:
        """
        Calculate CTL, ATL, and TSB over time using exponentially weighted moving averages

        Formulas:
        - CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) * (1 / CTL_TIME_CONSTANT)
        - ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) * (1 / ATL_TIME_CONSTANT)
        - TSB = CTL - ATL

        Args:
            tss_history: List of (date, tss) tuples, sorted by date
            initial_ctl: Starting CTL value
            initial_atl: Starting ATL value

        Returns:
            List of TrainingLoad objects with daily metrics
        """
        if not tss_history:
            return []

        # Sort by date to ensure chronological order
        tss_history = sorted(tss_history, key=lambda x: x[0])

        # Fill in missing days with 0 TSS
        start_date = tss_history[0][0]
        end_date = tss_history[-1][0]

        # Create a dictionary for quick TSS lookup
        tss_dict = {d: tss for d, tss in tss_history}

        # Calculate CTL/ATL for each day
        results = []
        current_date = start_date
        ctl = initial_ctl
        atl = initial_atl

        while current_date <= end_date:
            # Get TSS for this day (0 if no workout)
            tss = tss_dict.get(current_date, 0.0)

            # Update CTL (42-day EWMA)
            ctl = ctl + (tss - ctl) * (1.0 / self.CTL_TIME_CONSTANT)

            # Update ATL (7-day EWMA)
            atl = atl + (tss - atl) * (1.0 / self.ATL_TIME_CONSTANT)

            # Calculate TSB (form)
            tsb = ctl - atl

            results.append(TrainingLoad(
                date=current_date,
                tss=tss,
                ctl=ctl,
                atl=atl,
                tsb=tsb
            ))

            current_date += timedelta(days=1)

        return results

    def estimate_threshold_pace(self, recent_workouts: List[Workout]) -> Optional[float]:
        """
        Estimate functional threshold pace from recent tempo/threshold workouts

        Look for tempo runs or races and estimate FTP as ~95-100% of that pace

        Args:
            recent_workouts: Recent workout history (last 4-8 weeks)

        Returns:
            Estimated threshold pace in m/s, or None if insufficient data
        """
        from models import RunType

        # Find tempo, threshold, or race workouts
        tempo_workouts = [
            w for w in recent_workouts
            if w.run_type in [RunType.TEMPO, RunType.RACE, RunType.INTERVALS]
            and w.metrics.average_speed
            and w.metrics.moving_time >= 1200  # At least 20 minutes
        ]

        if not tempo_workouts:
            return None

        # Take fastest sustained pace from tempo/race workouts
        max_pace = max(w.metrics.average_speed for w in tempo_workouts)

        # FTP is typically 95-100% of best tempo pace
        # Use 97% as a reasonable estimate
        estimated_ftp = max_pace * 0.97

        return estimated_ftp

    def get_current_training_load(
        self,
        workouts: List[Workout],
        threshold_pace_mps: Optional[float] = None,
        threshold_heartrate: Optional[float] = None
    ) -> Optional[TrainingLoad]:
        """
        Get current training load metrics from workout history

        Args:
            workouts: All workouts (should include at least 42 days for accurate CTL)
            threshold_pace_mps: Threshold pace for TSS calculation
            threshold_heartrate: Threshold HR for TSS calculation

        Returns:
            Most recent TrainingLoad object, or None if no workouts
        """
        if not workouts:
            return None

        # Calculate TSS for each workout
        tss_history = []
        for workout in workouts:
            tss = self.calculate_workout_tss(
                workout,
                threshold_pace_mps,
                threshold_heartrate
            )
            tss_history.append((workout.date.date(), tss))

        # Calculate CTL/ATL/TSB
        load_history = self.calculate_ctl_atl_tsb(tss_history)

        # Return most recent
        return load_history[-1] if load_history else None

    def interpret_tsb(self, tsb: float) -> str:
        """
        Interpret Training Stress Balance (form) value

        Args:
            tsb: TSB value

        Returns:
            Interpretation string
        """
        if tsb > 25:
            return "Highly rested - may be losing fitness"
        elif tsb > 15:
            return "Well rested - optimal race readiness"
        elif tsb > 5:
            return "Rested - good for racing"
        elif tsb > -10:
            return "Fresh - productive training zone"
        elif tsb > -30:
            return "Optimal training - building fitness"
        elif tsb > -50:
            return "Heavy training - monitor for overtraining"
        else:
            return "Very fatigued - risk of overtraining"
