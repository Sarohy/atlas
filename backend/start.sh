#!/bin/bash
set -e

pip install alembic sqlalchemy asyncpg
alembic upgrade head
python -m atlas.seed
python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080