#!/usr/bin/env bash
# dev.sh — start the ATLAS backend and frontend in parallel.
# Usage: ./dev.sh
# Stop both with Ctrl-C.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Colours ────────────────────────────────────────────────────────────────
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

log()  { echo -e "${CYAN}[atlas]${RESET} $*"; }
ok()   { echo -e "${GREEN}[atlas]${RESET} $*"; }
warn() { echo -e "${YELLOW}[atlas]${RESET} $*"; }
err()  { echo -e "${RED}[atlas]${RESET} $*" >&2; }

# ─── Node version check ──────────────────────────────────────────────────────
load_nvm() {
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "$NVM_DIR/nvm.sh"
    return 0
  fi
  return 1
}

ensure_node() {
  local required_major=20
  local current_major
  current_major=$(node --version 2>/dev/null | sed 's/v\([0-9]*\).*/\1/' || echo "0")

  if (( current_major < required_major )); then
    warn "Node $(node --version 2>/dev/null || echo 'not found') is too old — need >=20."
    if load_nvm; then
      log "Switching to Node 22 via nvm…"
      nvm use 22 2>/dev/null || nvm install 22
      ok "Now on $(node --version)"
    else
      err "nvm not found. Install Node >=20 and retry."
      exit 1
    fi
  else
    ok "Node $(node --version) ✓"
  fi
}

# ─── Cleanup: kill child processes on exit ───────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  warn "Shutting down…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  ok "All processes stopped."
}
trap cleanup EXIT INT TERM

# ─── Backend ──────────────────────────────────────────────────────────────────
apply_backend_migrations() {
  log "Applying pending backend migrations…"
  cd "$ROOT_DIR/backend"
  uv run alembic upgrade head
  ok "Backend migrations are up to date."
}

start_backend() {
  log "Starting backend on :8000…"
  cd "$ROOT_DIR/backend"
  uv run uvicorn atlas.main:create_app \
    --factory \
    --reload \
    --port 8000 \
    --log-level info \
    2>&1 | sed "s/^/${CYAN}[backend]${RESET} /" &
  PIDS+=($!)
}

# ─── Frontend ─────────────────────────────────────────────────────────────────
start_frontend() {
  log "Starting frontend on :3000…"
  cd "$ROOT_DIR/frontend"
  pnpm dev 2>&1 | sed "s/^/${GREEN}[frontend]${RESET} /" &
  PIDS+=($!)
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
  log "ATLAS dev server starting…"
  ensure_node
  apply_backend_migrations
  start_backend
  # Brief pause so the backend boots before the frontend makes auth calls.
  sleep 1
  start_frontend

  ok "Both servers running. Press Ctrl-C to stop."
  # Wait for any child to exit (error) and propagate.
  wait -n 2>/dev/null || wait
}

main
