FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first so this layer caches until pyproject/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

EXPOSE 8000
# Single-instance setup: migrate, then serve. With several replicas, run migrations as a separate one-off step.
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && exec uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
