# ===========================================
# 🧠 BASE: Imagen oficial de Rasa Pro
# ===========================================
FROM rasa/rasa-pro:3.12.3

# Trabajaremos como root para poder instalar dependencias
USER root
WORKDIR /app

# ===========================================
# 📦 Instalar dependencias adicionales
# (FastAPI, psycopg2, SQLAlchemy, etc.)
# ===========================================
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# ===========================================
# 📁 Copiar TODO tu proyecto dentro del contenedor
# Incluye domain, actions, config, endpoints, FastAPI, etc.
# ===========================================
COPY . /app

# Asegurar permisos del entrypoint
RUN chmod +x /app/entrypoint.sh

# ===========================================
# 🌐 Exponer puertos
# -------------------------------------------
# 5005 → Rasa NLU/Core API
# 5055 → Action Server
# 8006 → FastAPI
# ===========================================
EXPOSE 5005 5055 8006

# ===========================================
# 🚀 ENTRYPOINT
# ===========================================
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
