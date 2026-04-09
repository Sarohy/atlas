#!/bin/bash
set -e

# Find alembic wherever it's installed
ALEMBIC=$(python -c "import shutil; print(shutil.which('alembic'))")
$ALEMBIC upgrade head

python -m atlas.seed
python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080