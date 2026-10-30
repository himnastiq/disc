"""Unit tests for consolidated cross-platform demo supervisor (P10.1)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.demo as demo  # noqa: E402


def test_preflight_success():
    """Verify preflight check passes against verified fixtures."""
    fixtures_dir = REPO_ROOT / "backend" / "tests" / "fixtures" / "artifacts_mini"
    assert fixtures_dir.exists(), "artifacts_mini fixture must exist"

    ok = demo.preflight_check(fixtures_dir, build_missing=False)
    assert ok is True


def test_preflight_missing_manifest(tmp_path: Path):
    """Missing manifest without build_missing must fail preflight."""
    # Create empty structure for movies, products, articles
    for t in ["movies", "products", "articles"]:
        (tmp_path / t).mkdir()

    ok = demo.preflight_check(tmp_path, build_missing=False)
    assert ok is False


def test_preflight_corrupted_checksum(tmp_path: Path):
    """Altered file checksum must be flagged as corrupted and fail preflight."""
    fixtures_dir = REPO_ROOT / "backend" / "tests" / "fixtures" / "artifacts_mini"
    for t in ["movies", "products", "articles"]:
        shutil.copytree(fixtures_dir / t, tmp_path / t)

    # Corrupt one file in movies
    corrupt_target = tmp_path / "movies" / "items.parquet"
    corrupt_target.write_bytes(b"corrupted_content_for_testing")

    ok = demo.preflight_check(tmp_path, build_missing=False)
    assert ok is False


def test_preflight_stale_code_hash(tmp_path: Path, capsys):
    """Manifest with stale code hash still passes validation but prints warning."""
    fixtures_dir = REPO_ROOT / "backend" / "tests" / "fixtures" / "artifacts_mini"
    for t in ["movies", "products", "articles"]:
        shutil.copytree(fixtures_dir / t, tmp_path / t)

    manifest_path = tmp_path / "movies" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["code_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    ok = demo.preflight_check(tmp_path, build_missing=False)
    assert ok is True
    captured = capsys.readouterr()
    assert "STALE" in captured.out


def test_handle_port_free():
    """Unoccupied port returns True immediately."""
    with patch("tools.demo.is_port_in_use", return_value=False):
        assert demo.handle_port(8999, our_pids=[]) is True


def test_handle_port_our_pid():
    """Port held by our prior PID is safely stopped."""
    with (
        patch("tools.demo.is_port_in_use", side_effect=[True, False]),
        patch("tools.demo.get_pid_holding_port", return_value=1234),
        patch("tools.demo.terminate_pid_tree") as mock_term,
    ):
        result = demo.handle_port(8000, our_pids=[1234], force=False)
        assert result is True
        mock_term.assert_called_once_with(1234, force=False)


def test_handle_port_foreign_pid_refused_without_force():
    """Foreign process holding port is not terminated without --force."""
    with (
        patch("tools.demo.is_port_in_use", return_value=True),
        patch("tools.demo.get_pid_holding_port", return_value=9999),
        patch("tools.demo.terminate_pid_tree") as mock_term,
    ):
        result = demo.handle_port(8000, our_pids=[1234], force=False)
        assert result is False
        mock_term.assert_not_called()


def test_handle_port_foreign_pid_with_force():
    """Foreign process is terminated when --force is specified."""
    with (
        patch("tools.demo.is_port_in_use", side_effect=[True, False]),
        patch("tools.demo.get_pid_holding_port", return_value=9999),
        patch("tools.demo.terminate_pid_tree") as mock_term,
    ):
        result = demo.handle_port(8000, our_pids=[1234], force=True)
        assert result is True
        mock_term.assert_called_once_with(9999, force=True)


def test_poll_backend_health_healthy():
    """Healthy 200 /v1/health response returns True."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {
            "status": "ok",
            "types": {
                "movies": {"available": True},
                "products": {"available": True},
                "articles": {"available": True},
            },
        }
    ).encode("utf-8")

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        assert demo.poll_backend_health(8000, timeout=2) is True


def test_poll_backend_health_degraded_allowed():
    """Degraded 200 /v1/health response still returns True (degraded allowed)."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {
            "status": "ok",
            "types": {
                "movies": {"available": True},
                "products": {"available": False, "error": "not found"},
            },
        }
    ).encode("utf-8")

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        assert demo.poll_backend_health(8000, timeout=2) is True


def test_poll_backend_health_timeout():
    """Connection failure until timeout returns False."""
    with patch("http.client.HTTPConnection", side_effect=OSError("connection refused")):
        assert demo.poll_backend_health(8000, timeout=1) is False


def test_smoke_demo_backend_start_and_stop():
    """Smoke test: starts API on alternate port using artifacts_mini, checks health, stops."""
    fixtures_dir = REPO_ROOT / "backend" / "tests" / "fixtures" / "artifacts_mini"
    python_bin = demo.get_python_executable()
    test_port = 8899

    backend_env = {
        **dict(subprocess.os.environ),
        "PYTHONPATH": str(REPO_ROOT / "backend"),
        "ARTIFACT_DIR": str(fixtures_dir.resolve()),
    }

    proc = subprocess.Popen(
        [
            python_bin,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(test_port),
        ],
        cwd=str(REPO_ROOT / "backend"),
        env=backend_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Poll health
        healthy = demo.poll_backend_health(test_port, timeout=10)
        assert healthy is True, f"API failed to become healthy on port {test_port}"
    finally:
        demo.terminate_pid_tree(proc.pid, force=True)
        time.sleep(1.0)
        assert not demo.is_port_in_use(test_port), f"Port {test_port} was not released"

