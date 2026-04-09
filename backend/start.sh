#!/bin/bash
set -e

python -m pip install alembic sqlalchemy asyncpg

python -c "
import sys
import subprocess
subprocess.run([sys.executable, '-m', 'pip', 'show', 'alembic'], check=True)

import alembic.config
alembic.config.main(argv=['upgrade', 'head'])
"

export PYTHONPATH=/app/src && python -m pip install --upgrade pip && python -m pip install fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy[asyncio] asyncpg alembic structlog httpx && python -m alembic upgrade head && python -m atlas.seed && python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080