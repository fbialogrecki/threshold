# syntax=docker/dockerfile:1

# Readable tag retained for Python 3.13/bookworm-slim; digest pins the multi-arch index.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY libs/py/pyproject.toml libs/py/pyproject.toml
COPY services/auth-gateway/pyproject.toml services/auth-gateway/pyproject.toml
COPY services/events/pyproject.toml services/events/pyproject.toml
COPY services/media/pyproject.toml services/media/pyproject.toml
COPY services/social/pyproject.toml services/social/pyproject.toml
COPY services/users/pyproject.toml services/users/pyproject.toml
COPY libs/py/threshold_common libs/py/threshold_common
COPY services/users/src services/users/src
COPY services/users/alembic.ini services/users/alembic.ini
COPY services/users/migrations services/users/migrations
RUN uv sync --locked --no-dev --no-editable --package threshold-users

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca AS runtime
WORKDIR /app/services/users
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/services/users/alembic.ini ./alembic.ini
COPY --from=builder --chown=app:app /app/services/users/migrations ./migrations

USER app
EXPOSE 8000
CMD ["uvicorn", "users.main:app", "--host", "0.0.0.0", "--port", "8000"]
