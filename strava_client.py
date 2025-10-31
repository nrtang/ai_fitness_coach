"""
Strava API Client - OAuth and activity syncing
"""
import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
from dotenv import load_dotenv

from models import Workout, WorkoutMetrics, WorkoutStreams, RunType

load_dotenv()


class StravaClient:
    """Client for interacting with Strava API"""

    BASE_URL = "https://www.strava.com/api/v3"
    OAUTH_URL = "https://www.strava.com/oauth"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Strava client

        Args:
            client_id: Strava application client ID
            client_secret: Strava application client secret
        """
        self.client_id = client_id or os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("STRAVA_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set"
            )

    def get_authorization_url(self, redirect_uri: str, state: str = "") -> str:
        """
        Get Strava OAuth authorization URL

        Args:
            redirect_uri: URL to redirect to after authorization
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read_all,activity:read",
            "state": state
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.OAUTH_URL}/authorize?{query_string}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_at, athlete info
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.OAUTH_URL}/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token

        Args:
            refresh_token: Refresh token from previous authorization

        Returns:
            New token response with access_token, refresh_token, expires_at
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.OAUTH_URL}/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            return response.json()

    def _ensure_token_valid(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: int
    ) -> tuple[str, str, int]:
        """
        Ensure token is valid, refresh if expired

        Args:
            access_token: Current access token
            refresh_token: Refresh token
            expires_at: Token expiration timestamp

        Returns:
            Tuple of (access_token, refresh_token, expires_at)
        """
        current_time = int(time.time())

        # Refresh if token expires in less than 5 minutes
        if current_time >= (expires_at - 300):
            import asyncio
            token_data = asyncio.run(self.refresh_access_token(refresh_token))
            return (
                token_data["access_token"],
                token_data["refresh_token"],
                token_data["expires_at"]
            )

        return access_token, refresh_token, expires_at

    async def get_athlete(self, access_token: str) -> Dict[str, Any]:
        """
        Get authenticated athlete's profile

        Args:
            access_token: Valid access token

        Returns:
            Athlete profile data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/athlete",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()

    async def get_activities(
        self,
        access_token: str,
        after: Optional[int] = None,
        before: Optional[int] = None,
        page: int = 1,
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get athlete's activities

        Args:
            access_token: Valid access token
            after: Unix timestamp to get activities after
            before: Unix timestamp to get activities before
            page: Page number
            per_page: Activities per page (max 200)

        Returns:
            List of activity summaries
        """
        params = {
            "page": page,
            "per_page": min(per_page, 200)
        }

        if after:
            params["after"] = after
        if before:
            params["before"] = before

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params
            )
            response.raise_for_status()
            return response.json()

    async def get_activity_details(
        self,
        access_token: str,
        activity_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed activity information

        Args:
            access_token: Valid access token
            activity_id: Strava activity ID

        Returns:
            Detailed activity data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()

    async def get_activity_streams(
        self,
        access_token: str,
        activity_id: int,
        keys: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get activity streams (GPS, HR, cadence, etc.)

        Args:
            access_token: Valid access token
            activity_id: Strava activity ID
            keys: Stream types to fetch (time, distance, latlng, altitude, etc.)

        Returns:
            Stream data
        """
        if keys is None:
            keys = [
                "time", "distance", "latlng", "altitude",
                "velocity_smooth", "heartrate", "cadence", "watts", "temp"
            ]

        keys_str = ",".join(keys)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/activities/{activity_id}/streams",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"keys": keys_str, "key_by_type": True}
            )
            response.raise_for_status()
            return response.json()

    def _map_activity_type_to_run_type(self, activity_type: str, name: str) -> RunType:
        """
        Map Strava activity type to our RunType enum

        Args:
            activity_type: Strava activity type
            name: Activity name (may contain hints like "tempo", "interval")

        Returns:
            RunType enum value
        """
        name_lower = name.lower()

        # Check activity name for hints
        if "tempo" in name_lower:
            return RunType.TEMPO
        if "interval" in name_lower or "speed" in name_lower or "track" in name_lower:
            return RunType.INTERVALS
        if "hill" in name_lower:
            return RunType.HILL_REPEATS
        if "long" in name_lower:
            return RunType.LONG
        if "recovery" in name_lower:
            return RunType.RECOVERY
        if "race" in name_lower:
            return RunType.RACE

        # Default to easy for runs
        if activity_type == "Run":
            return RunType.EASY

        # Default
        return RunType.EASY

    def convert_activity_to_workout(
        self,
        activity: Dict[str, Any],
        user_id: str,
        include_streams: bool = False,
        streams_data: Optional[Dict[str, Any]] = None
    ) -> Workout:
        """
        Convert Strava activity to our Workout model

        Args:
            activity: Strava activity data
            user_id: User ID to associate workout with
            include_streams: Whether streams data is included
            streams_data: Optional streams data from get_activity_streams

        Returns:
            Workout object
        """
        # Map run type
        run_type = self._map_activity_type_to_run_type(
            activity.get("type", "Run"),
            activity.get("name", "")
        )

        # Build metrics
        metrics = WorkoutMetrics(
            distance=float(activity["distance"]),
            moving_time=float(activity["moving_time"]),
            elapsed_time=float(activity["elapsed_time"]),
            total_elevation_gain=activity.get("total_elevation_gain"),
            average_speed=activity.get("average_speed"),
            max_speed=activity.get("max_speed"),
            average_heartrate=activity.get("average_heartrate"),
            max_heartrate=activity.get("max_heartrate"),
            average_cadence=activity.get("average_cadence"),
            average_watts=activity.get("average_watts"),
            calories=activity.get("calories")
        )

        # Build streams if provided
        streams = None
        if include_streams and streams_data:
            streams = WorkoutStreams(
                time=streams_data.get("time", {}).get("data"),
                distance=streams_data.get("distance", {}).get("data"),
                latlng=streams_data.get("latlng", {}).get("data"),
                altitude=streams_data.get("altitude", {}).get("data"),
                velocity_smooth=streams_data.get("velocity_smooth", {}).get("data"),
                heartrate=streams_data.get("heartrate", {}).get("data"),
                cadence=streams_data.get("cadence", {}).get("data"),
                watts=streams_data.get("watts", {}).get("data"),
                temp=streams_data.get("temp", {}).get("data"),
                grade_smooth=streams_data.get("grade_smooth", {}).get("data")
            )

        # Create workout
        workout = Workout(
            id=f"strava_{activity['id']}",
            date=datetime.fromisoformat(activity["start_date"].replace("Z", "+00:00")),
            run_type=run_type,
            metrics=metrics,
            streams=streams,
            notes=activity.get("description"),
            source="strava"
        )

        return workout

    async def sync_activities(
        self,
        access_token: str,
        user_id: str,
        after: Optional[datetime] = None,
        include_streams: bool = False
    ) -> List[Workout]:
        """
        Sync activities from Strava

        Args:
            access_token: Valid access token
            user_id: User ID to associate workouts with
            after: Only sync activities after this date
            include_streams: Whether to fetch detailed streams data

        Returns:
            List of Workout objects
        """
        after_timestamp = int(after.timestamp()) if after else None
        workouts = []

        # Fetch activities (paginated)
        page = 1
        while True:
            activities = await self.get_activities(
                access_token,
                after=after_timestamp,
                page=page,
                per_page=100
            )

            if not activities:
                break

            # Filter for runs only
            runs = [a for a in activities if a.get("type") == "Run"]

            for activity in runs:
                # Get detailed activity if we want streams
                if include_streams:
                    try:
                        streams_data = await self.get_activity_streams(
                            access_token,
                            activity["id"]
                        )
                    except Exception:
                        streams_data = None
                else:
                    streams_data = None

                workout = self.convert_activity_to_workout(
                    activity,
                    user_id,
                    include_streams,
                    streams_data
                )
                workouts.append(workout)

            # Check if there are more pages
            if len(activities) < 100:
                break

            page += 1

        return workouts
