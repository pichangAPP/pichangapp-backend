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
MODEL_DIR="${RASA_MODEL_DIR:-/app/models}"
FALLBACK_MODEL_DIR="${RASA_FALLBACK_MODEL_DIR:-/app/artifacts/models}"
EXCLUDED_MODELS_REGEX="${RASA_EXCLUDED_MODELS_REGEX:-^$}"
RASA_STARTUP_TIMEOUT_SECONDS="${RASA_STARTUP_TIMEOUT_SECONDS:-180}"

mkdir -p "${MODEL_DIR}"

latest_model_from_dir() {
  local search_dir="$1"
  ls -1t "${search_dir}"/*.tar.gz 2>/dev/null | grep -Ev "/(${EXCLUDED_MODELS_REGEX})$" | head -n1 || true
}

echo "Model resolution order:"
echo "  1) ${MODEL_DIR} (*.tar.gz)"
echo "  2) ${FALLBACK_MODEL_DIR} (*.tar.gz) -> used directly as fallback"
echo "  3) If no model is found, startup fails (no auto-train)."
echo "Excluded models regex: ${EXCLUDED_MODELS_REGEX}"

MODEL_ARG="$(latest_model_from_dir "${MODEL_DIR}")"
if [ -n "${MODEL_ARG}" ]; then
  echo "Model package(s) found in ${MODEL_DIR}."
elif [ -n "$(latest_model_from_dir "${FALLBACK_MODEL_DIR}")" ]; then
  echo "No model found in ${MODEL_DIR}. Using latest model from ${FALLBACK_MODEL_DIR}..."
  MODEL_ARG="$(latest_model_from_dir "${FALLBACK_MODEL_DIR}")"
else
  echo "ERROR: no eligible model found. Expected a .tar.gz in ${MODEL_DIR}."
  echo "Fallback checked: ${FALLBACK_MODEL_DIR}"
  echo "Excluded by regex: ${EXCLUDED_MODELS_REGEX}"
  echo "How to fix:"
  echo "  - Train manually: rasa train --out artifacts/models"
  echo "  - Or copy one: cp models/*.tar.gz artifacts/models/"
  exit 1
fi

echo "Selected model package: ${MODEL_ARG}"

echo "Starting Rasa Server (5005) with --model ${MODEL_ARG}..."
rasa run \
  --enable-api \
  --cors "*" \
  --port 5005 \
  --model "${MODEL_ARG}" \
  --endpoints /app/endpoints.yml \
  --credentials /app/credentials.yml &

RASA_PID=$!
echo "Rasa Server PID: $RASA_PID"

# 3) Wait until /status responds with a loaded model
echo "Waiting for Rasa /status..."
if RASA_STARTUP_TIMEOUT_SECONDS="${RASA_STARTUP_TIMEOUT_SECONDS}" python - <<'PY'
import json
import os
import time
import urllib.request

url = "http://localhost:5005/status"
timeout_seconds = int(os.environ.get("RASA_STARTUP_TIMEOUT_SECONDS", "180"))
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
else
  echo "ERROR: Rasa did not load a model before timeout (${RASA_STARTUP_TIMEOUT_SECONDS}s)."
  kill "${RASA_PID}" "${ACTION_PID}" >/dev/null 2>&1 || true
  exit 1
fi

# 4) Start FastAPI gateway
echo "Starting FastAPI (8006)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8006
