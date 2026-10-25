"""Runtime purity integration test for FastAPI backend (Phase 7, P7.12).

Spawns the Discovery Engine API in a fresh subprocess, exercises all 12 API endpoints
across all three content types (movies, products, articles), and strictly asserts that
no deep learning or heavy distributed frameworks (TensorFlow, PySpark, PyTorch, Cornac)
are imported into sys.modules during startup or live serving.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"


def test_runtime_purity_across_all_endpoints() -> None:
    """Verify in subprocess that hitting all endpoints never imports forbidden frameworks."""
    subproc_code = """
import sys
from pathlib import Path

# Set up paths
backend_root = Path.cwd()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient
from api.main import create_app

app = create_app()

with TestClient(app) as client:
    # 1. System metadata endpoints
    r = client.get("/v1/health")
    assert r.status_code == 200, f"/v1/health failed: {r.status_code}"

    r = client.get("/v1/types")
    assert r.status_code == 200, f"/v1/types failed: {r.status_code}"

    r = client.get("/v1/about")
    assert r.status_code == 200, f"/v1/about failed: {r.status_code}"

    for ctype in ["movies", "products", "articles"]:
        # 2. Metrics & users endpoints
        r = client.get(f"/v1/metrics?type={ctype}")
        assert r.status_code == 200, f"/v1/metrics failed for {ctype}: {r.status_code}"

        r = client.get(f"/v1/types/{ctype}/users")
        assert r.status_code == 200, f"/v1/types/{ctype}/users failed: {r.status_code}"

        # Dynamically retrieve valid user and item for this content type
        user_id = str(app.state.artifacts[ctype].users["user_id"].iloc[0])
        item_id = str(app.state.artifacts[ctype].items["item_id"].iloc[0])

        # 3. Item detail and search endpoints
        r = client.get(f"/v1/items/{item_id}?type={ctype}")
        assert r.status_code == 200, f"/v1/items/{item_id} failed for {ctype}: {r.status_code}"

        r = client.get(f"/v1/items/search?type={ctype}&q=a&limit=5")
        assert r.status_code == 200, f"/v1/items/search failed for {ctype}: {r.status_code}"

        # 4. User profile endpoint
        r = client.get(f"/v1/users/{user_id}/profile?type={ctype}")
        assert r.status_code == 200, f"/v1/users/profile failed for {ctype}: {r.status_code}"

        # 5. Recommendation endpoint
        r = client.get(f"/v1/recommend?type={ctype}&user_id={user_id}&k=5")
        assert r.status_code == 200, f"/v1/recommend failed for {ctype}: {r.status_code}"

        # 6. Cold-start endpoint
        cold_payload = {
            "type": ctype,
            "k": 5,
            "history": [{"item_id": item_id, "signal": 5.0}],
            "exclude": [],
        }
        r = client.post("/v1/recommend/cold-start", json=cold_payload)
        assert r.status_code == 200, f"/v1/recommend/cold-start failed for {ctype}: {r.status_code}"

        # 7. Popular endpoint
        r = client.get(f"/v1/popular?type={ctype}&k=5")
        assert r.status_code == 200, f"/v1/popular failed for {ctype}: {r.status_code}"

        # 8. Similar endpoint
        r = client.get(f"/v1/similar?type={ctype}&item_id={item_id}&k=5")
        assert r.status_code == 200, f"/v1/similar failed for {ctype}: {r.status_code}"

# 9. Strict Purity Assertion on sys.modules
forbidden = ["tensorflow", "pyspark", "torch", "cornac"]
imported_forbidden = [pkg for pkg in forbidden if pkg in sys.modules]

if imported_forbidden:
    print(f"FORBIDDEN_FRAMEWORKS_IMPORTED: {imported_forbidden}")
    sys.exit(1)

print("PURITY_VERIFIED")
sys.exit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", subproc_code],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"Purity subprocess test failed with code {result.returncode}:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert "PURITY_VERIFIED" in result.stdout
