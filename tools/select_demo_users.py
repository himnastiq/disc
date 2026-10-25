#!/usr/bin/env python3
"""Discovery Engine - Select diverse demo users for showcase tabs (P3.11).

CLI wrapper over engine.demo_users.select_demo_users.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from engine.demo_users import select_demo_users


def main() -> None:
    """CLI entry point for tools/select_demo_users.py."""
    parser = argparse.ArgumentParser(
        description="Select diverse demo users for a content type."
    )
    parser.add_argument(
        "--type", default="movies", help="Content type identifier (default: movies)"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for selection (default: 42)"
    )
    parser.add_argument(
        "--count", type=int, default=8, help="Target demo user count (default: 8)"
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Custom artifacts directory path",
    )

    args = parser.parse_args()
    try:
        users = select_demo_users(
            content_type=args.type,
            artifacts_dir=args.artifacts_dir,
            seed=args.seed,
            target_count=args.count,
        )
        print(f"Successfully selected {len(users)} demo users for '{args.type}':")
        for u in users:
            print(
                f"  User {u['user_id']:<6} | Persona: {u['persona']:<12} | Interactions: {u['interaction_count']}"
            )
    except Exception as e:  # noqa: BLE001
        print(f"Error selecting demo users: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
