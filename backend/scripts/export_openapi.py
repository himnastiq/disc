"""Discovery Engine - Export OpenAPI schema (Phase 7, P7.9).

Generates OpenAPI 3.1.0 schema JSON from the FastAPI application. Supports
deterministic export and CI check mode (--check) to ensure committed schemas
never drift from implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure backend root is on path when invoked as script
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.main import create_app  # noqa: E402

DEFAULT_OUTPUT_PATH = BACKEND_ROOT / "api" / "openapi.json"


def get_openapi_schema() -> dict:
    """Generate OpenAPI specification dictionary from FastAPI app."""
    app = create_app()
    return app.openapi()


def export_openapi(output_path: Path = DEFAULT_OUTPUT_PATH, check_only: bool = False) -> int:
    """Export or verify committed openapi.json schema."""
    generated_schema = get_openapi_schema()
    formatted_json = json.dumps(generated_schema, indent=2, sort_keys=True) + "\n"

    if check_only:
        if not output_path.exists():
            print(f"[ERROR] OpenAPI schema file does not exist at: {output_path}", file=sys.stderr)
            return 1

        committed_content = output_path.read_text(encoding="utf-8")
        try:
            committed_schema = json.loads(committed_content)
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Failed to parse committed schema JSON: {exc}", file=sys.stderr)
            return 1

        if committed_schema == generated_schema:
            print(f"[SUCCESS] OpenAPI schema at {output_path} is strictly up to date.")
            return 0

        print(
            f"[ERROR] Committed OpenAPI schema at {output_path} drifts from current API implementation.",
            file=sys.stderr,
        )
        print("Run 'python backend/scripts/export_openapi.py' to regenerate it.", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(formatted_json.replace("\r\n", "\n").encode("utf-8"))
    print(
        f"[SUCCESS] Exported OpenAPI schema ({len(formatted_json.encode('utf-8'))} bytes) to {output_path}"
    )
    return 0


def main() -> None:
    """CLI entrypoint for export_openapi.py."""
    parser = argparse.ArgumentParser(
        description="Export or verify Discovery Engine OpenAPI specification schema."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Target path for openapi.json (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether committed schema matches generated schema without modifying file.",
    )

    args = parser.parse_args()
    exit_code = export_openapi(output_path=args.output, check_only=args.check)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
