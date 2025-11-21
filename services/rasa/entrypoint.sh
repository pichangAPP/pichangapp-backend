#!/bin/bash
set -euo pipefail

# Start Rasa action server in the background
/venv/bin/rasa run actions --cors "*" --port 5055 &

# Run custom Rasa pipeline bootstrapper if required
/venv/bin/python rasa-run.py &

# Launch FastAPI wrapper
exec /venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8006
