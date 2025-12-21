#!/bin/bash

# =============================================================================
# AI Code Reviewer - Stop Script
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS_DIR="$PROJECT_DIR/.pids"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_info "Stopping AI Code Reviewer services..."

# Stop from PID files
for pid_file in "$PIDS_DIR"/*.pid; do
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        service=$(basename "$pid_file" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log_info "Stopped $service (PID: $pid)"
        fi
        rm "$pid_file"
    fi
done

# Also try to kill by process name (fallback)
pkill -f "uvicorn src.app.main:app" 2>/dev/null || true
pkill -f "celery -A src.workers.celery_app" 2>/dev/null || true

log_info "All services stopped ✓"
