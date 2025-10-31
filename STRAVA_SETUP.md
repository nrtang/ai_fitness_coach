# Strava Integration Setup Guide

This guide walks you through setting up Strava integration for automatic workout syncing.

## Prerequisites

- A Strava account
- Your AI Fitness Coach application running
- Public URL for OAuth callback (localhost works for development)

## Step 1: Create a Strava API Application

1. Go to [Strava API Settings](https://www.strava.com/settings/api)
2. Click "Create App" or use an existing application
3. Fill in the application details:
   - **Application Name**: AI Fitness Coach (or your choice)
   - **Category**: Training
   - **Club**: Leave blank
   - **Website**: Your website URL
   - **Authorization Callback Domain**:
     - For development: `localhost`
     - For production: your domain (e.g., `fitness-coach.com`)
4. Click "Create"

5. Note your credentials:
   - **Client ID**: (e.g., 12345)
   - **Client Secret**: (long string, keep this secret!)

## Step 2: Configure Your Application

1. Copy `.env.example` to `.env` if you haven't already
2. Add your Strava credentials:

```bash
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REDIRECT_URI=http://localhost:8000/strava/callback
STRAVA_WEBHOOK_VERIFY_TOKEN=STRAVA_WEBHOOK
```

For production, update `STRAVA_REDIRECT_URI` to your actual domain:
```bash
STRAVA_REDIRECT_URI=https://your-domain.com/strava/callback
```

## Step 3: Update Database Schema

Run the database migration to add Strava connection tables:

```bash
alembic revision --autogenerate -m "add strava connection"
alembic upgrade head
```

## Step 4: Connect a User's Strava Account

### Using the API

1. **Get the authorization URL**:
```bash
curl "http://localhost:8000/strava/connect?user_id={user_id}"
```

Response:
```json
{
  "authorization_url": "https://www.strava.com/oauth/authorize?client_id=...",
  "message": "Redirect user to this URL to authorize Strava access"
}
```

2. **Redirect the user** to the `authorization_url`

3. **User authorizes** on Strava and is redirected back to your callback URL

4. **Callback is automatically handled** by `/strava/callback` endpoint

5. **Connection confirmed**! The user's Strava account is now connected.

### Authorization Scopes

The application requests these Strava scopes:
- `read`: Read public profile data
- `activity:read_all`: Read all activities (public and private)
- `activity:read`: Read activity data

## Step 5: Sync Activities

### Initial Sync

Sync historical activities for a user:

```bash
curl -X POST "http://localhost:8000/users/{user_id}/strava/sync?days_back=90"
```

Parameters:
- `days_back`: Number of days of history to sync (default: 30)
- `include_streams`: Set to `true` to fetch GPS/HR streams (slower, default: false)

Response:
```json
{
  "message": "Strava sync completed",
  "new_activities": 45,
  "updated_activities": 3,
  "total_synced": 48,
  "last_sync": "2025-10-30T10:30:00"
}
```

### Check Connection Status

```bash
curl "http://localhost:8000/users/{user_id}/strava/status"
```

Response:
```json
{
  "connected": true,
  "strava_athlete_id": 12345,
  "last_sync": "2025-10-30T10:30:00",
  "sync_enabled": true,
  "connected_at": "2025-10-15T08:00:00"
}
```

## Step 6: Setup Webhooks (Optional - Real-time Sync)

Webhooks enable real-time activity syncing when users complete runs.

### Create Webhook Subscription

Use curl or Postman to create a webhook subscription:

```bash
curl -X POST "https://www.strava.com/api/v3/push_subscriptions" \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d callback_url=https://your-domain.com/strava/webhook \
  -d verify_token=STRAVA_WEBHOOK
```

Response:
```json
{
  "id": 123456,
  "application_id": YOUR_CLIENT_ID,
  "callback_url": "https://your-domain.com/strava/webhook"
}
```

### View Webhook Subscription

```bash
curl -G "https://www.strava.com/api/v3/push_subscriptions" \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET
```

### How Webhooks Work

1. User completes a run and uploads to Strava
2. Strava sends webhook event to your `/strava/webhook` endpoint
3. Your app automatically fetches and saves the activity
4. No manual sync needed!

### Webhook Requirements

- **Public URL**: Your callback URL must be publicly accessible (not localhost)
- **HTTPS**: Production webhooks require HTTPS
- **Fast response**: Webhook endpoint must respond within 2 seconds

## API Endpoints Reference

### OAuth Flow

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/strava/connect` | GET | Get authorization URL |
| `/strava/callback` | GET | OAuth callback (automatic) |

### Sync & Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users/{user_id}/strava/sync` | POST | Sync activities |
| `/users/{user_id}/strava/status` | GET | Check connection status |
| `/users/{user_id}/strava/disconnect` | DELETE | Disconnect Strava |

### Webhooks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/strava/webhook` | GET | Verification endpoint |
| `/strava/webhook` | POST | Event handler |

## Data Mapping

### Activity Type Detection

The integration automatically maps Strava activities to workout types:

| Strava Activity Name Contains | Mapped Run Type |
|-------------------------------|-----------------|
| "tempo" | Tempo |
| "interval", "speed", "track" | Intervals |
| "hill" | Hill Repeats |
| "long" | Long |
| "recovery" | Recovery |
| "race" | Race |
| Default | Easy |

### Metrics Synced

All Strava metrics are synced:
- Distance (meters)
- Duration (moving time, elapsed time)
- Speed (average, max)
- Heart rate (average, max)
- Cadence (average)
- Power (average, max) - if available
- Elevation gain
- Calories

### GPS Streams (Optional)

When `include_streams=true`, detailed time-series data is synced:
- GPS coordinates (lat/lng)
- Elevation profile
- Heart rate per second
- Cadence per second
- Velocity per second
- Temperature
- Gradient

## Troubleshooting

### "No Strava connection found"

- User hasn't connected their Strava account yet
- Use `/strava/connect` to get authorization URL

### "Token expired" errors

- Tokens are automatically refreshed
- Check database `expires_at` field is being updated

### Webhook verification fails

- Ensure `STRAVA_WEBHOOK_VERIFY_TOKEN` matches what you sent when creating subscription
- Check URL is publicly accessible
- Verify endpoint returns `{"hub.challenge": "..."}` correctly

### Activities not syncing

1. Check connection status: `/users/{user_id}/strava/status`
2. Verify `sync_enabled` is `true`
3. Check last sync time
4. Manually trigger sync: `/users/{user_id}/strava/sync`
5. Check application logs for errors

### Duplicate activities

- Activities are deduplicated by `strava_activity_id`
- Duplicate syncs will update existing activities, not create duplicates

## Security Best Practices

1. **Never commit** `.env` file with real credentials
2. **Use HTTPS** in production
3. **Rotate tokens** if compromised
4. **Validate webhook** events (check verify token)
5. **Rate limiting**: Strava has API rate limits (100 requests/15min, 1000/day)

## Example: Complete Integration Flow

```bash
# 1. Create user
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{"email":"runner@example.com","name":"Jane Doe"}'

# Response: {"id": "user_abc123", ...}

# 2. Get Strava auth URL
curl "http://localhost:8000/strava/connect?user_id=user_abc123"

# 3. User visits URL and authorizes (browser)

# 4. After callback, check status
curl "http://localhost:8000/users/user_abc123/strava/status"

# 5. Sync activities
curl -X POST "http://localhost:8000/users/user_abc123/strava/sync?days_back=60"

# 6. View workouts
curl "http://localhost:8000/users/user_abc123/workouts"

# 7. Generate training program based on Strava data
curl -X POST "http://localhost:8000/users/user_abc123/training-programs/generate"
```

## Rate Limits

Strava API rate limits:
- **15-minute limit**: 100 requests
- **Daily limit**: 1,000 requests

The integration handles this by:
- Paginating activity fetches
- Using bulk endpoints where possible
- Caching tokens until expiry

## Additional Resources

- [Strava API Documentation](https://developers.strava.com/docs/reference/)
- [OAuth 2.0 Flow](https://developers.strava.com/docs/authentication/)
- [Webhook Events Guide](https://developers.strava.com/docs/webhooks/)

## Support

If you encounter issues:
1. Check the application logs
2. Verify Strava API credentials
3. Test with Strava's API playground
4. Open an issue on GitHub
