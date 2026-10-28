"""Discovery Engine - Generic Type Extensibility & Literal Purity Tests (FIX-49).

Verifies that engine/ and api/ contain zero hardcoded string literals for specific
content type domains ("movies", "products", "articles") outside configs, proving
that the engine and API are strictly generic and schema-driven.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from engine.config import load_config
from engine.schema import ContentTypeSpec


def test_no_hardcoded_content_type_literals_in_engine_and_api() -> None:
    """Assert that engine/ and api/ contain zero literals 'movies', 'products', 'articles' outside configs."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    backend_dir = repo_root / "backend"
    engine_dir = backend_dir / "engine"
    api_dir = backend_dir / "api"

    forbidden_literals = {"movies", "products", "articles"}
    regex_pattern = re.compile(r"[\"'](movies|products|articles)[\"']")

    ast_violations: list[str] = []
    regex_violations: list[str] = []

    for search_root in (engine_dir, api_dir):
        for py_path in search_root.rglob("*.py"):
            # Exclude configs directory
            if "configs" in py_path.parts:
                continue

            content = py_path.read_text(encoding="utf-8")
            rel_file = py_path.relative_to(repo_root).as_posix()

            # 1. AST check for string constants
            try:
                tree = ast.parse(content, filename=str(py_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        cleaned = node.value.strip().lower()
                        if cleaned in forbidden_literals:
                            ast_violations.append(
                                f"{rel_file}:{node.lineno} -> AST literal {node.value!r}"
                            )
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {rel_file}: {e}")

            # 2. Regex check for quoted literals in lines
            for lineno, line in enumerate(content.splitlines(), start=1):
                if regex_pattern.search(line):
                    regex_violations.append(f"{rel_file}:{lineno} -> {line.strip()}")

    assert not ast_violations, (
        f"Found hardcoded domain literals in AST ({len(ast_violations)} violations):\n"
        + "\n".join(ast_violations)
    )
    assert not regex_violations, (
        f"Found hardcoded domain literals via regex ({len(regex_violations)} violations):\n"
        + "\n".join(regex_violations)
    )


def test_config_fields_loaded_and_applied_correctly() -> None:
    """Verify that dataset.display_name, evaluation.max_test_users, and evaluation.protocol are validated."""
    for ctype in ("movies", "products", "articles"):
        spec = load_config(ctype)
        assert isinstance(spec, ContentTypeSpec)
        assert spec.dataset.display_name is not None
        assert len(spec.dataset.display_name) > 0
        assert spec.evaluation.max_test_users > 0
        assert spec.evaluation.protocol in ("standard", "dual_protocol")

        # Fast override check
        fast_spec = load_config(ctype, fast=True)
        assert fast_spec.evaluation.max_test_users == 50
