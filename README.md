# AI Fitness Coach

An AI-powered fitness coaching system that generates personalized running training programs, evaluates workout performance, and tracks training load using TrainingPeaks methodology (CTL/ATL/TSB).

## Features

### Core Functionality
- **AI Training Program Generation**: Claude-powered personalized training plans based on goals and fitness history
- **Workout Evaluation**: Automated evaluation comparing planned vs actual workouts with adherence scoring
- **Training Load Management**: TSS, CTL, ATL, and TSB calculations following TrainingPeaks methodology
- **Multi-User Support**: Full user management with individual training programs
- **Strava Integration**: Full OAuth, automatic sync, and real-time webhooks ✨
- **Fitness Device Support**: Data models compatible with Garmin, Suunto, Apple HealthKit, Android Health

### Training Programs
- **Race Preparation**: 5K, 10K, Half Marathon, Marathon, Ultra distances
- **Periodized Training**: Base → Build → Peak → Taper phases
- **Adaptive Programs**: 8-20 week programs based on time until race
- **Smart Workouts**: Easy runs, tempo, intervals, long runs, recovery days
- **Intensity Zones**: 5-zone training intensity system

### Training Load Metrics
- **TSS (Training Stress Score)**: Pace-based with elevation adjustment
- **CTL (Chronic Training Load)**: 42-day fitness indicator
- **ATL (Acute Training Load)**: 7-day fatigue indicator
- **TSB (Training Stress Balance)**: Readiness/form indicator
- **Threshold Pace Estimation**: Automatic FTP estimation from workout history

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **AI**: Anthropic Claude Sonnet 4
- **Data Validation**: Pydantic 2.0
- **Migrations**: Alembic

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Anthropic API key

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai_fitness_coach
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings:
# - DATABASE_URL: PostgreSQL connection string
# - ANTHROPIC_API_KEY: Your Claude API key
```

5. **Initialize database**
```bash
# Create database
createdb fitness_coach

# Run migrations
alembic upgrade head
```

6. **Start the server**
```bash
python app.py
# Or with uvicorn:
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Strava Integration

See [STRAVA_SETUP.md](STRAVA_SETUP.md) for detailed setup instructions.

**Quick Setup:**

1. Create a Strava API application at https://www.strava.com/settings/api
2. Add credentials to `.env`:
```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```
3. Connect user account:
```bash
# Get auth URL
curl "http://localhost:8000/strava/connect?user_id={user_id}"
# User visits URL and authorizes

# Sync activities
curl -X POST "http://localhost:8000/users/{user_id}/strava/sync"
```

Features:
- ✅ OAuth 2.0 authentication
- ✅ Automatic activity syncing
- ✅ Real-time webhook updates
- ✅ GPS streams support
- ✅ Duplicate detection
- ✅ Token refresh handling

## Quick Start

### 1. Create a User
```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "runner@example.com",
    "name": "Jane Runner",
    "unit_preference": "imperial"
  }'
```

### 2. Add Workout History
```bash
curl -X POST "http://localhost:8000/users/{user_id}/workouts" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-10-20T06:30:00",
    "run_type": "easy",
    "metrics": {
      "distance": 8000.0,
      "moving_time": 2880.0,
      "elapsed_time": 2880.0,
      "average_speed": 2.78,
      "average_heartrate": 145
    },
    "perceived_effort": 4,
    "notes": "Morning run, felt good"
  }'
```

### 3. Set a Goal
```bash
curl -X POST "http://localhost:8000/users/{user_id}/goals" \
  -H "Content-Type: application/json" \
  -d '{
    "race_distance": "marathon",
    "race_date": "2026-04-20",
    "target_time_seconds": 10800
  }'
```

### 4. Generate Training Program
```bash
curl -X POST "http://localhost:8000/users/{user_id}/training-programs/generate"
```

### 5. View Training Program
```bash
# Get active program overview
curl "http://localhost:8000/users/{user_id}/training-programs/active"

# Get specific week details
curl "http://localhost:8000/training-programs/{program_id}/weeks/1"
```

### 6. Check Training Load
```bash
curl "http://localhost:8000/users/{user_id}/training-load"
```

## API Endpoints

### Users
- `POST /users` - Create user
- `GET /users/{user_id}` - Get user details

### Workouts
- `POST /users/{user_id}/workouts` - Add workout
- `GET /users/{user_id}/workouts` - List workouts (with date filters)

### Goals
- `POST /users/{user_id}/goals` - Create goal
- `GET /users/{user_id}/goals/active` - Get active goal

### Training Programs
- `POST /users/{user_id}/training-programs/generate` - Generate new program
- `GET /users/{user_id}/training-programs/active` - Get active program
- `GET /training-programs/{program_id}/weeks/{week_number}` - Get week details

### Training Load
- `GET /users/{user_id}/training-load` - Get CTL/ATL/TSB metrics

### Evaluation
- `POST /workouts/{planned_workout_id}/evaluate` - Evaluate workout performance

## Data Models

All data follows Strava API format:
- **Distance**: meters
- **Duration**: seconds
- **Speed/Pace**: meters per second
- **Elevation**: meters
- **Heart Rate**: bpm
- **Power**: watts

Use utility functions in `utils.py` for display formatting (imperial/metric).

## Training Load Explained

### TSS (Training Stress Score)
Quantifies the training stress of a single workout based on intensity and duration.

```
TSS = duration_hours × (intensity_factor²) × 100
```

### CTL (Chronic Training Load) - Fitness
42-day exponentially weighted moving average of daily TSS. Represents long-term fitness.

```
CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) × (1/42)
```

### ATL (Acute Training Load) - Fatigue
7-day exponentially weighted moving average of daily TSS. Represents recent fatigue.

```
ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) × (1/7)
```

### TSB (Training Stress Balance) - Form
```
TSB = CTL - ATL
```

**Interpretation:**
- **+15 to +25**: Optimal race readiness
- **+5 to +15**: Well rested, good for racing
- **-10 to -30**: Productive training zone
- **< -30**: Risk of overtraining

## Project Structure

```
ai_fitness_coach/
├── models.py              # Pydantic data models
├── db_models.py           # SQLAlchemy database models
├── database.py            # Database configuration
├── ai_coach.py            # AI training program generator
├── training_load.py       # TSS/CTL/ATL/TSB calculations
├── utils.py               # Unit conversion utilities
├── app.py                 # FastAPI application
├── requirements.txt       # Python dependencies
├── alembic/               # Database migrations
├── .env.example           # Environment configuration template
└── README.md              # This file
```

## Deployment

### Single EC2 Instance

1. **Launch EC2 instance** (Ubuntu 22.04 recommended)
2. **Install dependencies**
```bash
sudo apt update
sudo apt install -y python3.11 python3-pip postgresql
```

3. **Clone and setup application**
```bash
git clone <repo>
cd ai_fitness_coach
pip install -r requirements.txt
```

4. **Configure PostgreSQL**
```bash
sudo -u postgres createuser fitness_coach
sudo -u postgres createdb fitness_coach
# Set password and update DATABASE_URL in .env
```

5. **Run with systemd** (create service file)
```ini
[Unit]
Description=AI Fitness Coach API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/ai_fitness_coach
Environment="PATH=/home/ubuntu/ai_fitness_coach/venv/bin"
ExecStart=/home/ubuntu/ai_fitness_coach/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

6. **Setup nginx reverse proxy** (optional, recommended for production)

### AWS RDS (Optional)

To use AWS RDS instead of local PostgreSQL:

1. Create RDS PostgreSQL instance
2. Update `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://user:pass@your-rds-endpoint.rds.amazonaws.com:5432/fitness_coach
```

No code changes needed!

## Future Enhancements

- [ ] Fitness device integrations (Strava OAuth, Garmin Connect)
- [ ] Real-time workout syncing
- [ ] Web dashboard UI
- [ ] Mobile app
- [ ] Custom model training (replace Claude)
- [ ] Injury prevention monitoring
- [ ] Nutrition recommendations
- [ ] Multi-sport support (cycling, swimming, triathlon)
- [ ] Social features (coach-athlete relationships)

## Contributing

Contributions welcome! Please open an issue or PR.

## License

MIT License

## Support

For issues or questions, please open a GitHub issue.
