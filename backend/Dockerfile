FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /uvx /bin/

WORKDIR /app

ENV UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_DOWNLOADS=0 PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock .python-version ./
COPY src ./src

RUN --mount=type=cache,target=/tmp/uv-cache uv sync --locked --no-dev

EXPOSE 8000

CMD ["taste-match-api"]
