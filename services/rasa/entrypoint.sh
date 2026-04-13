#!/usr/bin/env sh
set -eu

echo "==============================="
echo "   🚀 INICIANDO CHATO-BOT"
echo "==============================="

###############################################
# 1) Levantar Action Server
###############################################
echo "👉 Iniciando Action Server (5055)..."
rasa run actions \
  --cors "*" \
  --port 5055 &

ACTION_PID=$!
echo "✔ Action Server PID: $ACTION_PID"

###############################################
# 2) Levantar Rasa Server (NLU/Core)
###############################################
MODEL_DIR="${RASA_MODEL_DIR:-/app/artifacts/models}"
if [ -n "${RASA_MODEL_PATH:-}" ] && [ -f "${RASA_MODEL_PATH}" ]; then
  MODEL_ARG="${RASA_MODEL_PATH}"
elif ls "${MODEL_DIR}"/*.tar.gz >/dev/null 2>&1; then
  MODEL_ARG="${MODEL_DIR}"
else
  echo "⚠️ No hay modelo en ${MODEL_DIR} (*.tar.gz). Monta el volumen o entrena con: rasa train --out artifacts/models"
  MODEL_ARG="${MODEL_DIR}"
fi
echo "👉 Iniciando Rasa Server (5005) con --model ${MODEL_ARG}..."
rasa run \
  --enable-api \
  --cors "*" \
  --port 5005 \
  --model "${MODEL_ARG}" &

RASA_PID=$!
echo "✔ Rasa Server PID: $RASA_PID"

###############################################
# 3) Pequeña espera para que termine de cargar
###############################################
echo "⏳ Esperando a que Rasa Server responda en /status..."
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
                    print("✔ Rasa Server listo.")
                    raise SystemExit(0)
    except Exception:
        pass

    if time.monotonic() - start > timeout_seconds:
        print("⚠️ Rasa Server no respondió a tiempo. Continuando...")
        raise SystemExit(1)

    time.sleep(2)
PY
then
  :
fi

###############################################
# 4) Levantar FastAPI (8006)
###############################################
echo "👉 Iniciando FastAPI (8006)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8006
