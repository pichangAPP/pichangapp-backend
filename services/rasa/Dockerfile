# syntax=docker/dockerfile:1.4

FROM python:3.11-slim AS builder

ARG PIP_VERSION=24.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off \
    VENV_PATH=/venv

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN python -m venv ${VENV_PATH} \
    && ${VENV_PATH}/bin/pip install --no-cache-dir --upgrade "pip==${PIP_VERSION}" \
    && PIP_USE_DEPRECATED=legacy-resolver ${VENV_PATH}/bin/pip wheel --no-cache-dir --prefer-binary --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim

ARG PIP_VERSION=24.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=on \
    VENV_PATH=/venv \
    PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN python -m venv ${VENV_PATH} \
    && ${VENV_PATH}/bin/pip install --no-cache-dir --upgrade "pip==${PIP_VERSION}" \
    && PIP_USE_DEPRECATED=legacy-resolver ${VENV_PATH}/bin/pip install --no-cache-dir --prefer-binary /wheels/* \
    && rm -rf /wheels

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8006 5055

ENTRYPOINT ["/app/entrypoint.sh"]
