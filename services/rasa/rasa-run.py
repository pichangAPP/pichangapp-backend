import subprocess
import sys

if __name__ == "__main__":
    cmd = [
        "rasa",
        "run",
        "--enable-api",
        "--cors", "*",
        "--port", "5005",
        # NO pasar endpoints ni credentials
    ]

    print("Ejecutando:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
