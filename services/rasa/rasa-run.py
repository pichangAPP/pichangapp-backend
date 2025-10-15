from dotenv import load_dotenv
import os
import subprocess

# Cargar variables del .env
load_dotenv()

# Ejecutar Rasa
subprocess.run(["rasa", "run", "--enable-api", "-p", "5005"])
