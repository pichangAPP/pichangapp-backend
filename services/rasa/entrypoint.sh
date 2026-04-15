#!/bin/bash
set -e
set -u

echo "==============================="
echo "   STARTING CHATO-BOT"
echo "==============================="

# 1) Start action server
echo "Starting Action Server (5055)..."
rasa run actions \
  --cors "*" \
  --port 5055 &

ACTION_PID=$!
echo "Action Server PID: $ACTION_PID"

# 2) Start Rasa server (NLU/Core)
MODEL_DIR="${RASA_MODEL_DIR:-/app/artifacts/models}"
if [ -n "${RASA_MODEL_PATH:-}" ] && [ -f "${RASA_MODEL_PATH}" ]; then
  MODEL_ARG="${RASA_MODEL_PATH}"
elif ls "${MODEL_DIR}"/*.tar.gz >/dev/null 2>&1; then
  MODEL_ARG="${MODEL_DIR}"
else
  echo "WARNING: no model found in ${MODEL_DIR} (*.tar.gz). Train with: rasa train --out artifacts/models"
  MODEL_ARG="${MODEL_DIR}"
fi

echo "Starting Rasa Server (5005) with --model ${MODEL_ARG}..."
rasa run \
  --enable-api \
  --cors "*" \
  --port 5005 \
  --model "${MODEL_ARG}" &

RASA_PID=$!
echo "Rasa Server PID: $RASA_PID"

# 3) Wait until /status responds with a loaded model
echo "Waiting for Rasa /status..."
if python - <<'PY'
import json
import time
import urllib.request

url = "http://localhost:5005/status"
timeout_seconds = 180
start = time.monotonic()

while True:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8") or "{}")
                if data.get("model_file"):
                    print("Rasa ready.")
                    raise SystemExit(0)
    except Exception:
        pass

    if time.monotonic() - start > timeout_seconds:
        print("WARNING: Rasa /status timeout. Continuing...")
        raise SystemExit(1)

    time.sleep(2)
PY
then
  :
fi

# 4) Start FastAPI gateway
echo "Starting FastAPI (8006)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8006
