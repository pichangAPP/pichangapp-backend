import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    service_root = Path(__file__).resolve().parent
    preferred_models_dir = service_root / "models"
    fallback_models_dir = service_root / "artifacts" / "models"

    selected_model: str
    if preferred_models_dir.exists():
        model_files = sorted(
            preferred_models_dir.glob("*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if model_files:
            selected_model = str(model_files[0])
        else:
            selected_model = str(preferred_models_dir)
    else:
        selected_model = str(fallback_models_dir)

    cmd = [
        "rasa",
        "run",
        "--enable-api",
        "--cors", "*",
        "--port", "5005",
        "--model", selected_model,
        "--endpoints", str(service_root / "endpoints.yml"),
        "--credentials", str(service_root / "credentials.yml"),
    ]

    print("Ejecutando:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
