from dotenv import load_dotenv
import os
import subprocess

# Cargar variables del .env
load_dotenv()

# Nivel de log: por defecto WARNING para reducir ruido
log_level = os.getenv("LOG_LEVEL", "ERROR").upper()

# Ejecutar Rasa
subprocess.run(["rasa", "run", "--enable-api", "-p", "5005", "--log-level", log_level])
