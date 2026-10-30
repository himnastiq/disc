#!/usr/bin/env bash
# ==============================================================================
# Discovery Engine - Development & Demo Launcher
# Launches the FastAPI Backend (port 8000) and Next.js Frontend (port 3000)
# in two separate terminal windows.
#
# Supports:
#  - Windows (Git Bash, MSYS2, MinGW, Cygwin)
#  - Windows Subsystem for Linux (WSL)
#  - macOS (Terminal.app)
#  - Linux (gnome-terminal, konsole, xfce4-terminal, xterm, or tmux)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="dev"
ACTION="start"

# ------------------------------------------------------------------------------
# Parse Arguments
# ------------------------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --prod|-p)
      MODE="prod"
      ;;
    --stop|-k|--kill)
      ACTION="stop"
      ;;
    --help|-h)
      echo "Discovery Engine - Terminal Launcher"
      echo ""
      echo "Usage: ./run.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  (no args)    Start Backend & Frontend in separate terminals (dev mode with hot-reload)"
      echo "  --prod, -p   Start in production mode (requires 'npm run build')"
      echo "  --stop, -k   Stop running servers on ports 8000 and 3000"
      echo "  --help, -h   Show this help message"
      echo ""
      echo "Endpoints:"
      echo "  Backend API:      http://127.0.0.1:8000"
      echo "  Interactive Docs: http://127.0.0.1:8000/docs"
      echo "  Frontend UI:      http://localhost:3000"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Run './run.sh --help' for usage."
      exit 1
      ;;
  esac
done

# ------------------------------------------------------------------------------
# Helper: Detect OS Environment
# ------------------------------------------------------------------------------
IS_WINDOWS=false
IS_WSL=false
IS_MACOS=false
IS_LINUX=false

if [ -f /proc/version ] && grep -qi microsoft /proc/version; then
  IS_WSL=true
fi

case "$OSTYPE" in
  msys*|cygwin*|win32*)
    IS_WINDOWS=true
    ;;
  darwin*)
    IS_MACOS=true
    ;;
  linux*)
    if [ "$IS_WSL" = false ]; then
      IS_LINUX=true
    fi
    ;;
  *)
    # Fallback heuristic
    if command -v cmd.exe >/dev/null 2>&1; then
      IS_WINDOWS=true
    else
      IS_LINUX=true
    fi
    ;;
esac

# ------------------------------------------------------------------------------
# Helper: Stop processes listening on ports 8000 and 3000
# ------------------------------------------------------------------------------
kill_port() {
  local port="$1"
  local name="$2"

  if [ "$IS_WINDOWS" = true ] || [ "$IS_WSL" = true ]; then
    # On Windows / WSL, use netstat & taskkill / PowerShell
    local pids
    pids=$(netstat -ano 2>/dev/null | grep ":$port " | grep "LISTENING" | awk '{print $NF}' | sort -u || true)
    if [ -n "$pids" ]; then
      echo "Stopping $name on port $port (PID: $pids)..."
      for pid in $pids; do
        taskkill //F //PID "$pid" 2>/dev/null || taskkill /F /PID "$pid" 2>/dev/null || true
      done
    fi
  else
    # Unix / Linux / macOS
    if command -v lsof >/dev/null 2>&1; then
      local pids
      pids=$(lsof -ti :"$port" 2>/dev/null || true)
      if [ -n "$pids" ]; then
        echo "Stopping $name on port $port (PID: $pids)..."
        kill -9 $pids 2>/dev/null || true
      fi
    elif command -v fuser >/dev/null 2>&1; then
      fuser -k -9 "$port/tcp" 2>/dev/null || true
    fi
  fi
}

stop_all() {
  echo "Terminating any existing servers on ports 8000 and 3000..."
  kill_port 8000 "Backend"
  kill_port 3000 "Frontend"
  echo "Ports cleared."
}

if [ "$ACTION" = "stop" ]; then
  stop_all
  exit 0
fi

# Always clean up prior stale servers before launching to prevent address collisions
stop_all

# ------------------------------------------------------------------------------
# Locate Python Virtual Environment
# ------------------------------------------------------------------------------
PYTHON_EXEC=""
WIN_PYTHON=""

if [ "$IS_WINDOWS" = true ]; then
  if [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/Scripts/python.exe"
  elif [ -f "$SCRIPT_DIR/backend/.venv/Scripts/python.exe" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/backend/.venv/Scripts/python.exe"
  else
    PYTHON_EXEC="python"
  fi
  WIN_PYTHON="$(cygpath -w "$PYTHON_EXEC" 2>/dev/null || echo "$PYTHON_EXEC")"
  WIN_ROOT="$(cygpath -w "$SCRIPT_DIR" 2>/dev/null || echo "$SCRIPT_DIR")"
elif [ "$IS_WSL" = true ]; then
  if [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    WIN_PYTHON="$(wslpath -w "$SCRIPT_DIR/.venv/Scripts/python.exe")"
    PYTHON_EXEC="$SCRIPT_DIR/.venv/Scripts/python.exe"
  elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
  else
    PYTHON_EXEC="python3"
  fi
  WIN_ROOT="$(wslpath -w "$SCRIPT_DIR" 2>/dev/null || echo "$SCRIPT_DIR")"
else
  if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
  elif [ -f "$SCRIPT_DIR/backend/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/backend/.venv/bin/python"
  else
    PYTHON_EXEC="python3"
  fi
fi

# Verify frontend dependencies
if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
  echo "Installing frontend dependencies (first-time setup)..."
  npm --prefix "$SCRIPT_DIR/frontend" install
fi

# ------------------------------------------------------------------------------
# Launch Separate Terminals
# ------------------------------------------------------------------------------
echo "========================================================================"
echo " Starting Discovery Engine"
echo " Mode: $([ "$MODE" = "prod" ] && echo "Production" || echo "Development (Hot-Reload)")"
echo "========================================================================"

if [ "$IS_WINDOWS" = true ]; then
  # ----------------------------------------------------------------------------
  # Windows Native (Git Bash / MSYS2 / Cygwin)
  # ----------------------------------------------------------------------------
  if [ "$MODE" = "prod" ]; then
    BACKEND_CMD="cd /d \"$WIN_ROOT\" && title Discovery Engine - Backend (FastAPI) && set PYTHONPATH=backend && \"$WIN_PYTHON\" -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
    FRONTEND_CMD="cd /d \"$WIN_ROOT\\frontend\" && title Discovery Engine - Frontend (Next.js) && npm run start"
  else
    BACKEND_CMD="cd /d \"$WIN_ROOT\" && title Discovery Engine - Backend (FastAPI) && set PYTHONPATH=backend && \"$WIN_PYTHON\" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload"
    FRONTEND_CMD="cd /d \"$WIN_ROOT\\frontend\" && title Discovery Engine - Frontend (Next.js) && npm run dev"
  fi

  echo "Launching FastAPI Backend window..."
  MSYS_NO_PATHCONV=1 cmd.exe /c start "Discovery Engine - Backend" cmd.exe /k "$BACKEND_CMD"

  echo "Launching Next.js Frontend window..."
  MSYS_NO_PATHCONV=1 cmd.exe /c start "Discovery Engine - Frontend" cmd.exe /k "$FRONTEND_CMD"

elif [ "$IS_WSL" = true ]; then
  # ----------------------------------------------------------------------------
  # Windows Subsystem for Linux (WSL) -> Launch via cmd.exe
  # ----------------------------------------------------------------------------
  if [ "$MODE" = "prod" ]; then
    BACKEND_CMD="cd /d \"$WIN_ROOT\" && title Discovery Engine - Backend (FastAPI) && set PYTHONPATH=backend && \"$WIN_PYTHON\" -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
    FRONTEND_CMD="cd /d \"$WIN_ROOT\\frontend\" && title Discovery Engine - Frontend (Next.js) && npm run start"
  else
    BACKEND_CMD="cd /d \"$WIN_ROOT\" && title Discovery Engine - Backend (FastAPI) && set PYTHONPATH=backend && \"$WIN_PYTHON\" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload"
    FRONTEND_CMD="cd /d \"$WIN_ROOT\\frontend\" && title Discovery Engine - Frontend (Next.js) && npm run dev"
  fi

  echo "Launching FastAPI Backend window via Windows host..."
  cmd.exe /c start "Discovery Engine - Backend" cmd.exe /k "$BACKEND_CMD"

  echo "Launching Next.js Frontend window via Windows host..."
  cmd.exe /c start "Discovery Engine - Frontend" cmd.exe /k "$FRONTEND_CMD"

elif [ "$IS_MACOS" = true ]; then
  # ----------------------------------------------------------------------------
  # macOS -> Terminal.app via osascript
  # ----------------------------------------------------------------------------
  if [ "$MODE" = "prod" ]; then
    BACKEND_SHELL_CMD="cd '$SCRIPT_DIR' && export PYTHONPATH=backend && '$PYTHON_EXEC' -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
    FRONTEND_SHELL_CMD="cd '$SCRIPT_DIR/frontend' && npm run start"
  else
    BACKEND_SHELL_CMD="cd '$SCRIPT_DIR' && export PYTHONPATH=backend && '$PYTHON_EXEC' -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload"
    FRONTEND_SHELL_CMD="cd '$SCRIPT_DIR/frontend' && npm run dev"
  fi

  echo "Launching FastAPI Backend in Terminal.app..."
  osascript -e "tell application \"Terminal\" to do script \"$BACKEND_SHELL_CMD\""

  echo "Launching Next.js Frontend in Terminal.app..."
  osascript -e "tell application \"Terminal\" to do script \"$FRONTEND_SHELL_CMD\""

elif [ "$IS_LINUX" = true ]; then
  # ----------------------------------------------------------------------------
  # Linux Desktop GUI
  # ----------------------------------------------------------------------------
  if [ "$MODE" = "prod" ]; then
    BACKEND_SHELL_CMD="cd '$SCRIPT_DIR' && export PYTHONPATH=backend && '$PYTHON_EXEC' -m uvicorn api.main:app --host 127.0.0.1 --port 8000; exec bash"
    FRONTEND_SHELL_CMD="cd '$SCRIPT_DIR/frontend' && npm run start; exec bash"
  else
    BACKEND_SHELL_CMD="cd '$SCRIPT_DIR' && export PYTHONPATH=backend && '$PYTHON_EXEC' -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload; exec bash"
    FRONTEND_SHELL_CMD="cd '$SCRIPT_DIR/frontend' && npm run dev; exec bash"
  fi

  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --title="Discovery Engine - Backend" -- bash -c "$BACKEND_SHELL_CMD"
    gnome-terminal --title="Discovery Engine - Frontend" -- bash -c "$FRONTEND_SHELL_CMD"
  elif command -v konsole >/dev/null 2>&1; then
    konsole --new-tab -p tabtitle="Discovery Engine - Backend" -e bash -c "$BACKEND_SHELL_CMD" &
    konsole --new-tab -p tabtitle="Discovery Engine - Frontend" -e bash -c "$FRONTEND_SHELL_CMD" &
  elif command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --title="Discovery Engine - Backend" -e "bash -c \"$BACKEND_SHELL_CMD\"" &
    xfce4-terminal --title="Discovery Engine - Frontend" -e "bash -c \"$FRONTEND_SHELL_CMD\"" &
  elif command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -T "Discovery Engine - Backend" -e "bash -c \"$BACKEND_SHELL_CMD\"" &
    x-terminal-emulator -T "Discovery Engine - Frontend" -e "bash -c \"$FRONTEND_SHELL_CMD\"" &
  elif command -v xterm >/dev/null 2>&1; then
    xterm -title "Discovery Engine - Backend" -e "bash -c \"$BACKEND_SHELL_CMD\"" &
    xterm -title "Discovery Engine - Frontend" -e "bash -c \"$FRONTEND_SHELL_CMD\"" &
  elif command -v tmux >/dev/null 2>&1; then
    echo "No desktop terminal emulator detected. Launching in tmux session 'discovery'..."
    tmux new-session -d -s discovery -n backend "bash -c \"$BACKEND_SHELL_CMD\""
    tmux new-window -t discovery: -n frontend "bash -c \"$FRONTEND_SHELL_CMD\""
    echo "Attach to tmux anytime using: tmux attach -t discovery"
  else
    echo "No supported graphical terminal emulator found."
    echo "Starting both as background processes in this shell:"
    (cd "$SCRIPT_DIR" && export PYTHONPATH=backend && "$PYTHON_EXEC" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload) &
    (cd "$SCRIPT_DIR/frontend" && npm run dev) &
    echo "Servers started in background. Press Ctrl+C or run './run.sh --stop' to terminate."
    wait
  fi
fi

echo ""
echo "========================================================================"
echo " Discovery Engine is starting up!"
echo "------------------------------------------------------------------------"
echo "  Backend API:      http://127.0.0.1:8000"
echo "  API Health:       http://127.0.0.1:8000/v1/health"
echo "  Swagger Docs:     http://127.0.0.1:8000/docs"
echo "  Frontend UI:      http://localhost:3000"
echo "------------------------------------------------------------------------"
echo " Both servers are running in separate terminal windows."
echo " To stop both servers at any time, run: ./run.sh --stop"
echo "========================================================================"
