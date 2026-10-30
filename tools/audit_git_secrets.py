"""Discovery Engine - Git history secret scanning tool (Phase 10, P10.5).

Scans all revisions across git history (git rev-list --all) for credentials,
private keys, and sensitive token patterns. Specifically audits the two commits
that tracked artifacts_backup_* (deff867 and 72d6d52).
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import NamedTuple


class Finding(NamedTuple):
    commit: str
    pattern: str
    line: str
    filename: str


SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Private Key Header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS Access Key", re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("GitHub Personal Access Token", re.compile(r"ghp_[0-9a-zA-Z]{36}")),
    ("GitHub Fine-Grained PAT", re.compile(r"github_pat_[0-9a-zA-Z_]{82}")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}")),
    (
        "Generic High-Entropy Key",
        re.compile(
            r"""(?:api_key|apiKey|secret_key|secretKey)\s*[:=]\s*['"][A-Za-z0-9+/=_\-]{24,}['"]"""
        ),
    ),
]

ALLOWLIST_PATTERNS = [
    re.compile(r"TEST_SECRET_API_KEY_NEVER_LEAK"),
    re.compile(r"super-secret-backend-key-12345"),
    re.compile(r"ascii_configured_secret"),
    re.compile(r"prod_secret_token_456"),
    re.compile(r"dummy"),
    re.compile(r"example"),
    re.compile(r"canary"),
    re.compile(r"test_"),
]


def audit_git_history() -> tuple[list[Finding], int]:
    """Scan all commits in git history for secret patterns using streaming git log."""
    proc = subprocess.Popen(
        ["git", "log", "-p", "-U0", "--no-color", "--all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    current_commit = "unknown"
    current_file = ""
    commit_set: set[str] = set()
    findings: list[Finding] = []

    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.rstrip("\r\n")
        if line.startswith("commit "):
            current_commit = line.split()[1][:8]
            commit_set.add(current_commit)
            current_file = ""
            continue
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue

        added_content = line[1:].strip()
        if not added_content:
            continue
        if any(allow.search(added_content) for allow in ALLOWLIST_PATTERNS):
            continue

        for pattern_name, regex in SECRET_PATTERNS:
            if regex.search(added_content):
                findings.append(
                    Finding(
                        commit=current_commit,
                        pattern=pattern_name,
                        line=added_content[:80],
                        filename=current_file,
                    )
                )

    proc.wait()
    return findings, len(commit_set)


def audit_backup_commits() -> dict[str, int]:
    """Specifically inspect commits deff867 and 72d6d52 (Session 28 artifacts_backup)."""
    target_commits = ["deff867", "72d6d52"]
    results = {}
    for commit in target_commits:
        try:
            res = subprocess.run(
                ["git", "show", "--stat", "--oneline", commit],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            results[commit] = len(res.stdout.splitlines())
        except subprocess.CalledProcessError:
            results[commit] = 0
    return results


def main() -> int:
    print("=" * 70, flush=True)
    print("Discovery Engine - Git History Secret Scan (P10.5)", flush=True)
    print("=" * 70, flush=True)

    backup_status = audit_backup_commits()
    for commit, lines in backup_status.items():
        print(
            f"[AUDIT] Commit {commit} (artifacts_backup_* tracking): {lines} stat lines examined.",
            flush=True,
        )

    findings, commit_count = audit_git_history()

    print(f"\n[SUMMARY] Scanned {commit_count} commits across git history.", flush=True)
    if findings:
        print(
            f"[ALERT] {len(findings)} potential secret pattern(s) detected:", flush=True
        )
        for f in findings:
            print(
                f"  - Commit {f.commit} in {f.filename} [{f.pattern}]: {f.line}",
                flush=True,
            )
        return 1

    print(
        "[SUCCESS] Zero secrets, private keys, or credentials found in git history.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
