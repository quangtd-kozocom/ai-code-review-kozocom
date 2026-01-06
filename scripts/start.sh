#!/bin/bash

# =============================================================================
# AI Code Reviewer - Startup Script
# =============================================================================
# Usage:
#   ./scripts/start.sh          # Start API + Worker
#   ./scripts/start.sh --ngrok  # Start API + Worker + ngrok tunnel
#   ./scripts/start.sh --tmux   # Start in tmux with API+Worker and ngrok in separate panes
#   ./scripts/start.sh --dev    # Start API only (dev mode with reload)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGROK_DOMAIN="national-kit-poorly.ngrok-free.app"
API_PORT=9000
TMUX_SESSION="ai-reviewer"

# PID files
PIDS_DIR="$PROJECT_DIR/.pids"
mkdir -p "$PIDS_DIR"

# =============================================================================
# Functions
# =============================================================================

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════╗"
    echo "║       🤖 AI Code Reviewer                ║"
    echo "║       Starting services...               ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Python (try python3 first, then python)
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python not found. Please install Python 3.13+"
        exit 1
    fi
    log_info "Using $PYTHON_CMD: $($PYTHON_CMD --version)"
    
    # Check uv
    if ! command -v uv &> /dev/null; then
        log_error "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    # Check .env file
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_error ".env file not found. Copy from .env.example and configure."
        exit 1
    fi
    
    log_info "All dependencies OK ✓"
}

start_api() {
    local reload_flag=""
    if [ "$1" == "--reload" ]; then
        reload_flag="--reload"
    fi
    
    log_info "Starting API server on port $API_PORT..."
    cd "$PROJECT_DIR"
    
    # Activate virtual environment if exists
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
    
    uvicorn src.app.main:app --host 0.0.0.0 --port $API_PORT $reload_flag &
    echo $! > "$PIDS_DIR/api.pid"
    log_info "API server started (PID: $!)"
}

start_worker() {
    log_info "Starting Celery worker..."
    cd "$PROJECT_DIR"
    
    # Activate virtual environment if exists
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
    
    celery -A src.workers.celery_app worker --loglevel=info &
    echo $! > "$PIDS_DIR/worker.pid"
    log_info "Celery worker started (PID: $!)"
}

start_ngrok() {
    log_info "Starting ngrok tunnel..."
    
    if ! command -v ngrok &> /dev/null; then
        log_warn "ngrok not found. Skipping tunnel."
        log_warn "Install with: brew install ngrok"
        return
    fi
    
    ngrok http $API_PORT --domain=$NGROK_DOMAIN &
    echo $! > "$PIDS_DIR/ngrok.pid"
    log_info "ngrok tunnel started"
    echo ""
    echo -e "${GREEN}🌐 Public URL: https://$NGROK_DOMAIN${NC}"
    echo -e "${GREEN}📌 Webhook URL: https://$NGROK_DOMAIN/api/v1/webhooks/github${NC}"
    echo ""
}

start_tmux() {
    log_info "Starting services in tmux session: $TMUX_SESSION"
    
    # Check if tmux is installed
    if ! command -v tmux &> /dev/null; then
        log_error "tmux not found. Install with: brew install tmux"
        exit 1
    fi
    
    # Check if ngrok is installed
    if ! command -v ngrok &> /dev/null; then
        log_error "ngrok not found. Install with: brew install ngrok"
        exit 1
    fi
    
    # Kill existing session if exists
    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    
    # Create new tmux session and run API + Worker
    tmux new-session -d -s "$TMUX_SESSION" -c "$PROJECT_DIR" "./scripts/start.sh"
    
    # Split window horizontally and run ngrok in right pane
    tmux split-window -h -t "$TMUX_SESSION" -c "$PROJECT_DIR" "sleep 3 && ngrok http $API_PORT --domain=$NGROK_DOMAIN"
    
    # Focus on the first pane (left - API + Worker)
    tmux select-pane -t "$TMUX_SESSION" -L
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ tmux session '$TMUX_SESSION' created!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "   API Server:  http://localhost:$API_PORT"
    echo -e "  🌐 Public URL:  https://$NGROK_DOMAIN"
    echo -e "  📌 Webhook:     https://$NGROK_DOMAIN/api/v1/webhooks/github"
    echo ""
    echo -e "  ${YELLOW}tmux shortcuts:${NC}"
    echo -e "    Ctrl+B, D     - Detach from session"
    echo -e "    Ctrl+B, ←/→   - Switch between panes"
    echo -e "    Ctrl+B, X     - Kill current pane"
    echo ""
    
    # Attach or switch to the session
    if [ -n "$TMUX" ]; then
        # Already inside tmux, switch to the new session
        echo -e "  ${YELLOW}Switching to session...${NC}"
        tmux switch-client -t "$TMUX_SESSION"
    else
        # Not inside tmux, attach normally
        echo -e "  ${YELLOW}Attaching to session...${NC}"
        tmux attach -t "$TMUX_SESSION"
    fi
}

show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Services started successfully!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "  📡 API Server:    http://localhost:$API_PORT"
    echo -e "  🏥 Health Check:  http://localhost:$API_PORT/health"
    echo -e "  📚 API Docs:      http://localhost:$API_PORT/docs"
    
    if [ -f "$PIDS_DIR/ngrok.pid" ]; then
        echo -e "  🌐 Public URL:    https://$NGROK_DOMAIN"
        echo -e "  📌 Webhook:       https://$NGROK_DOMAIN/api/v1/webhooks/github"
    fi
    
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
    echo ""
}

cleanup() {
    echo ""
    log_info "Stopping services..."
    
    # Kill API
    if [ -f "$PIDS_DIR/api.pid" ]; then
        kill $(cat "$PIDS_DIR/api.pid") 2>/dev/null || true
        rm "$PIDS_DIR/api.pid"
    fi
    
    # Kill Worker
    if [ -f "$PIDS_DIR/worker.pid" ]; then
        kill $(cat "$PIDS_DIR/worker.pid") 2>/dev/null || true
        rm "$PIDS_DIR/worker.pid"
    fi
    
    # Kill ngrok
    if [ -f "$PIDS_DIR/ngrok.pid" ]; then
        kill $(cat "$PIDS_DIR/ngrok.pid") 2>/dev/null || true
        rm "$PIDS_DIR/ngrok.pid"
    fi
    
    # Kill any remaining child processes
    pkill -P $$ 2>/dev/null || true
    
    log_info "All services stopped ✓"
    exit 0
}

# =============================================================================
# Main
# =============================================================================

# Handle Ctrl+C
trap cleanup SIGINT SIGTERM

# Parse arguments
USE_NGROK=false
USE_TMUX=false
DEV_MODE=false

for arg in "$@"; do
    case $arg in
        --ngrok)
            USE_NGROK=true
            ;;
        --tmux)
            USE_TMUX=true
            ;;
        --dev)
            DEV_MODE=true
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ngrok    Start ngrok tunnel for public access"
            echo "  --tmux     Start in tmux with API+Worker and ngrok in separate panes"
            echo "  --dev      Development mode (API only with auto-reload)"
            echo "  --help     Show this help message"
            exit 0
            ;;
    esac
done

# Handle tmux mode first (it will call start.sh internally without --tmux)
if [ "$USE_TMUX" == true ]; then
    start_tmux
    exit 0
fi

# Run
print_banner
check_dependencies

if [ "$DEV_MODE" == true ]; then
    start_api --reload
else
    start_api
    sleep 2
    start_worker
fi

if [ "$USE_NGROK" == true ]; then
    sleep 1
    start_ngrok
fi

show_status

# Keep script running and wait for all background processes
wait
