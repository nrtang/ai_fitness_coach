"""
Utility functions for unit conversions and formatting
"""
from typing import Literal

UnitSystem = Literal["metric", "imperial"]


def meters_to_km(meters: float) -> float:
    """Convert meters to kilometers"""
    return meters / 1000.0


def meters_to_miles(meters: float) -> float:
    """Convert meters to miles"""
    return meters / 1609.34


def seconds_to_minutes(seconds: float) -> float:
    """Convert seconds to minutes"""
    return seconds / 60.0


def seconds_to_hours(seconds: float) -> float:
    """Convert seconds to hours"""
    return seconds / 3600.0


def mps_to_pace_per_km(speed_mps: float) -> float:
    """
    Convert meters per second to pace (minutes per kilometer)

    Args:
        speed_mps: Speed in meters per second

    Returns:
        Pace in minutes per kilometer
    """
    if speed_mps <= 0:
        return 0.0
    # 1000 meters / speed gives seconds per km, divide by 60 for minutes
    return (1000.0 / speed_mps) / 60.0


def mps_to_pace_per_mile(speed_mps: float) -> float:
    """
    Convert meters per second to pace (minutes per mile)

    Args:
        speed_mps: Speed in meters per second

    Returns:
        Pace in minutes per mile
    """
    if speed_mps <= 0:
        return 0.0
    # 1609.34 meters / speed gives seconds per mile, divide by 60 for minutes
    return (1609.34 / speed_mps) / 60.0


def pace_per_km_to_mps(pace_min_per_km: float) -> float:
    """
    Convert pace (minutes per kilometer) to meters per second

    Args:
        pace_min_per_km: Pace in minutes per kilometer

    Returns:
        Speed in meters per second
    """
    if pace_min_per_km <= 0:
        return 0.0
    # Convert to seconds per km, then invert to get m/s
    seconds_per_km = pace_min_per_km * 60.0
    return 1000.0 / seconds_per_km


def pace_per_mile_to_mps(pace_min_per_mile: float) -> float:
    """
    Convert pace (minutes per mile) to meters per second

    Args:
        pace_min_per_mile: Pace in minutes per mile

    Returns:
        Speed in meters per second
    """
    if pace_min_per_mile <= 0:
        return 0.0
    # Convert to seconds per mile, then invert to get m/s
    seconds_per_mile = pace_min_per_mile * 60.0
    return 1609.34 / seconds_per_mile


def format_pace(speed_mps: float, unit_system: UnitSystem = "imperial") -> str:
    """
    Format speed as pace string (e.g., "7:30 /mi" or "4:40 /km")

    Args:
        speed_mps: Speed in meters per second
        unit_system: "metric" for km, "imperial" for miles

    Returns:
        Formatted pace string
    """
    if speed_mps <= 0:
        return "0:00"

    if unit_system == "metric":
        pace = mps_to_pace_per_km(speed_mps)
        unit = "/km"
    else:
        pace = mps_to_pace_per_mile(speed_mps)
        unit = "/mi"

    minutes = int(pace)
    seconds = int((pace - minutes) * 60)
    return f"{minutes}:{seconds:02d} {unit}"


def format_distance(meters: float, unit_system: UnitSystem = "imperial") -> str:
    """
    Format distance with appropriate units

    Args:
        meters: Distance in meters
        unit_system: "metric" for km, "imperial" for miles

    Returns:
        Formatted distance string
    """
    if unit_system == "metric":
        km = meters_to_km(meters)
        return f"{km:.2f} km"
    else:
        miles = meters_to_miles(meters)
        return f"{miles:.2f} mi"


def format_duration(seconds: float) -> str:
    """
    Format duration as HH:MM:SS or MM:SS

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_time_hhmmss(seconds: float) -> str:
    """
    Format time as HH:MM:SS (always include hours)

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string in HH:MM:SS
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
