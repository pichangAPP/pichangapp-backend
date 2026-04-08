import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    service_root = Path(__file__).resolve().parent
    models_dir = service_root / "artifacts" / "models"
    cmd = [
        "rasa",
        "run",
        "--enable-api",
        "--cors", "*",
        "--port", "5005",
        "--model", str(models_dir),
        "--endpoints", str(service_root / "endpoints.yml"),
        "--credentials", str(service_root / "credentials.yml"),
    ]

    print("Ejecutando:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
