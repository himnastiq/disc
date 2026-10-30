#!/usr/bin/env python3
"""Export FastAPI OpenAPI 3.1 specification to frontend/openapi.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
OUTPUT_FILE = REPO_ROOT / "frontend" / "openapi.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    from api.main import app

    schema = app.openapi()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"[SUCCESS] Exported OpenAPI schema to {OUTPUT_FILE} ({len(json.dumps(schema))} bytes)")


if __name__ == "__main__":
    main()

