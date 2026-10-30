#!/usr/bin/env bash
# Discovery Engine - Cross-Platform Bash Forwarder (P10.1)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/backend/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/backend/.venv/bin/python"
else
    PYTHON="python3"
fi
exec "$PYTHON" "$SCRIPT_DIR/tools/demo.py" "$@"
