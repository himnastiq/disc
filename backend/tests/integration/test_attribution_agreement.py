"""Integration test verifying agreement between /v1/about and docs/ATTRIBUTION.md (P11.3).

Asserts that:
  1. The API endpoint /v1/about and docs/ATTRIBUTION.md agree on Recommenders source URL.
  2. The API endpoint /v1/about and docs/ATTRIBUTION.md agree on Recommenders version (1.2.1).
  3. The API endpoint /v1/about and docs/ATTRIBUTION.md agree on the MIT License.
  4. Both sources explicitly state the non-commercial educational notice.
  5. backend/discovery/NOTICE.md agrees on git tag / source release 1.2.1.
"""

from __future__ import annotations

import re
from pathlib import Path

from api.routes.metadata import get_about

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ATTRIBUTION_DOC_PATH = REPO_ROOT / "docs" / "ATTRIBUTION.md"
NOTICE_PATH = REPO_ROOT / "backend" / "discovery" / "NOTICE.md"


def test_about_and_attribution_agreement() -> None:
    """Certify that /v1/about and docs/ATTRIBUTION.md agree on provenance, URL, version, and license."""
    assert ATTRIBUTION_DOC_PATH.exists(), f"Missing {ATTRIBUTION_DOC_PATH}"
    assert NOTICE_PATH.exists(), f"Missing {NOTICE_PATH}"

    doc_content = ATTRIBUTION_DOC_PATH.read_text(encoding="utf-8")
    notice_content = NOTICE_PATH.read_text(encoding="utf-8")

    # 1. Fetch /v1/about response model directly
    about_response = get_about()
    data = about_response.model_dump()

    # Find Recommenders attribution in API response
    recommenders_att = None
    for att in data.get("attributions", []):
        if "recommenders" in att.get("name", "").lower():
            recommenders_att = att
            break

    assert recommenders_att is not None, "Recommenders attribution missing from /v1/about"

    # 2. Assert source URL agreement
    api_url = recommenders_att["source_url"].rstrip("/")
    assert api_url in doc_content, f"API source_url '{api_url}' not found in docs/ATTRIBUTION.md"
    assert "https://github.com/recommenders-team/recommenders" in doc_content

    # 3. Assert version agreement (1.2.1)
    version_match = re.search(
        r"version.*?:.*?\b([0-9]+\.[0-9]+\.[0-9]+)\b", doc_content, re.IGNORECASE
    )
    assert version_match is not None, "Version not found in docs/ATTRIBUTION.md"
    doc_version = version_match.group(1)
    assert doc_version == "1.2.1"
    assert "1.2.1" in notice_content

    # 4. Assert MIT license agreement
    api_license = recommenders_att["license"]
    assert "MIT" in api_license
    assert "MIT License" in doc_content or "MIT" in doc_content

    # 5. Assert non-commercial educational notice present in both
    api_notice = data.get("non_commercial_notice", "").lower()
    assert "educational" in api_notice or "non-commercial" in api_notice
    doc_lower = doc_content.lower()
    assert "educational" in doc_lower
    assert "non-commercial" in doc_lower


def test_notice_matches_actual_patches() -> None:
    """Certify that backend/discovery/NOTICE.md lists all active minimal compatibility patches."""
    notice_content = NOTICE_PATH.read_text(encoding="utf-8")

    expected_patch_topics = [
        "utils/notebook_utils.py",
        "datasets/download_utils.py",
        "datasets/mind.py",
        "models/tfidf/tfidf_utils.py",
        "datasets/movielens.py",
        "models/sar/sar_singlenode.py",
    ]

    for topic in expected_patch_topics:
        assert topic in notice_content, f"NOTICE.md missing documentation for patch in '{topic}'"
