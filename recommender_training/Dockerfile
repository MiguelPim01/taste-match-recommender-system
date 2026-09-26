FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /uvx /bin/

WORKDIR /app

ENV UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_DOWNLOADS=0 PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
COPY config ./config

RUN --mount=type=cache,target=/tmp/uv-cache uv sync --locked --no-dev

CMD ["taste-match-training", "worker"]
