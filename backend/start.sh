#!/bin/bash
set -e

export PATH="/mise/shims:$PATH"

python -c "from alembic.config import main; main()" upgrade head
python -m atlas.seed
python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080