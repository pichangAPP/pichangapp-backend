#!/bin/bash
set -euo pipefail

# 1) Levantar el action server
/venv/bin/rasa run actions --cors "*" --port 5055 &
ACTIONS_PID=$!

# 2) Levantar Rasa (API principal) y esperar a que esté listo en el 5005
/venv/bin/python rasa-run.py &
RASA_PID=$!

/venv/bin/python - <<'PY'
import socket, sys, time

host, port, timeout = "127.0.0.1", 5005, 60
deadline = time.time() + timeout

while time.time() < deadline:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) == 0:
            sys.exit(0)
    time.sleep(1)

print(f"Rasa HTTP API ({host}:{port}) no respondió en {timeout}s", file=sys.stderr)
sys.exit(1)
PY

# 3) Iniciar la API FastAPI (puerto 8006) cuando Rasa ya está arriba
exec /venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8006
