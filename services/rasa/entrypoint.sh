#!/bin/bash
set -euo pipefail

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
echo "👉 Iniciando Rasa Server (5005)..."
rasa run \
  --enable-api \
  --cors "*" \
  --port 5005 &

RASA_PID=$!
echo "✔ Rasa Server PID: $RASA_PID"

###############################################
# 3) Pequeña espera para que termine de cargar
###############################################
sleep 10

###############################################
# 4) Levantar FastAPI (8006)
###############################################
echo "👉 Iniciando FastAPI (8006)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8006
