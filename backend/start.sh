#!/bin/bash
set -e

echo "=== Finding alembic ==="
find / -name "alembic" -type f 2>/dev/null

echo "=== Python location ==="
which python

echo "=== PATH ==="
echo $PATH