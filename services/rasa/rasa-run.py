import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    service_root = Path(__file__).resolve().parent
    cmd = [
        "rasa",
        "run",
        "--enable-api",
        "--cors", "*",
        "--port", "5005",
        "--model", str(service_root / "models"),
        "--endpoints", str(service_root / "endpoints.yml"),
        "--credentials", str(service_root / "credentials.yml"),
    ]

    print("Ejecutando:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
