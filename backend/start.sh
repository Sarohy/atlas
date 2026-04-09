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

python -m src/atlas/seed
python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port 8080