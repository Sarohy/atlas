#!/bin/bash
set -e

echo "🚀 Starting ATLAS Backend Deployment..."

# Set Python path to include src directory
export PYTHONPATH=/app/src:$PYTHONPATH

# Step 1: Upgrade pip and install dependencies from pyproject.toml
echo "📦 Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install .

# Step 2: Verify Alembic installation
echo "🔍 Verifying Alembic installation..."
python -m pip show alembic

# Step 3: Run database migrations
echo "🗄️  Running database migrations..."
python -m alembic upgrade head

# Step 4: Seed the database
echo "🌱 Seeding database..."
python -m atlas.seed || echo "⚠️  Seeding completed with warnings (data may already exist)"

# Step 5: Start the server
echo "✅ Starting server on port ${PORT:-8080}..."
exec python -m uvicorn atlas.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}
