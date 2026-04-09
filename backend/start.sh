#!/bin/bash
set -e

# Install uv if not present
if ! command -v uv &> /dev/null; then
    pip install uv
fi

uv sync
uv run alembic upgrade head
uv run python -m atlas.seed
uv run uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080