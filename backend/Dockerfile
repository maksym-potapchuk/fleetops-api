# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install poetry (latest 2.x — matches lock-version 2.1 from poetry 2.3+)
# Cache pip downloads across rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "poetry>=2.3.0,<3.0.0"

# Dependency layer — cached unless pyproject.toml / poetry.lock change
# poetry's default cache on Linux (root) = /root/.cache/pypoetry
COPY pyproject.toml poetry.lock ./
# If this fails with "pyproject.toml changed", run `poetry lock` locally and rebuild
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --no-root

COPY . .

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]
