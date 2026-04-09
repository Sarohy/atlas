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

python -m pip install . && PYTHONPATH=/app/src python -m alembic upgrade head && PYTHONPATH=/app/src python -m atlas.seed && PYTHONPATH=/app/src python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080
