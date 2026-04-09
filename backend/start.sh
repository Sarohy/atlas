#!/bin/bash
set -e

export PATH="/mise/installs/python/3.14.4/bin:$PATH"

alembic upgrade head
python -m atlas.seed
python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080