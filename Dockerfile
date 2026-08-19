FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Keep dependency installation cacheable independently from application source.
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-editable

COPY config.example.yaml ./config.yaml
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["flowcam", "run", "--config", "/app/config.yaml"]
