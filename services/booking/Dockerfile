# syntax=docker/dockerfile:1.4

ARG SHARED_VENV_IMAGE=pichangapp-shared-venv:latest
FROM ${SHARED_VENV_IMAGE} AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=on \
    VENV_PATH=/opt/venv \
    PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN ${VENV_PATH}/bin/pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN groupadd --system appuser \
    && useradd --system --gid appuser appuser

USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
