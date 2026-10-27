"""Read-only scanner for hardcoded values. Prints candidates; a human/agent judges them."""
import re
import subprocess
import sys

# Only scan tracked, text-like source files.
files = subprocess.run(
    ["git", "ls-files"],
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout.splitlines()
files = [f for f in files if f.endswith((".py", ".yaml", ".yml", ".toml", ".cfg", ".ini", "Makefile", ".json", ".md"))]
skip = ("backend/discovery/", "uv.lock", "package-lock.json", "openapi.json", ".md")  # .md only listed for URL scan below

CATEGORIES = {
    "ABSOLUTE_PATH": r"(?:[A-Za-z]:[\\\/]|/home/|/Users/|/tmp/|\\\\)[^\s'\"]*",
    "URL_OR_HOST": r"https?://[^\s'\"]+|localhost|127\.0\.0\.1|0\.0\.0\.0",
    "PORT": r"\bport\s*[=:]\s*\d{2,5}\b|:\d{4,5}\b",
    "SECRET_LIKE": r"(?i)(api[_-]?key|secret|token|passw(or)?d)\s*[:=]\s*['\"][^'\"]+['\"]",
    "TYPE_SPECIFIC": r"(?i)\b(movielens|movies?|products?|articles?|amazon|mind|rating|genre)\b",
    "MAGIC_NUMBER": r"(?<![\w.\"'])(?:[2-9]|\d{2,})(?:\.\d+)?(?![\w.\"'])",
    "SEED_LITERAL": r"(?i)seed\s*[=:(]\s*\d+|random_state\s*=\s*\d+",
    "BROAD_EXCEPT": r"except\s*:|except\s+Exception\b|except\s+BaseException\b",
    "PRINT_CALL": r"^\s*print\(",
    "TODO_MARKER": r"(?i)\b(TODO|FIXME|HACK|XXX)\b",
    "SUPPRESSION": r"#\s*(type:\s*ignore|noqa|pragma:\s*no cover)",
    "ASSERT_RUNTIME": r"^\s*assert\s",
    "UNSAFE_CALL": r"\b(eval|exec|pickle|cPickle|dill|joblib\.load|yaml\.load|os\.system|allow_pickle)\b|shell\s*=\s*True",
    "NAIVE_TIME": r"datetime\.(now|utcnow)\(\s*\)|time\.time\(\)",
}
SCOPE = {  # restrict noisy categories to code areas where they matter
    "TYPE_SPECIFIC": ("backend/engine/", "backend/api/", "tools/"),
    "MAGIC_NUMBER": ("backend/engine/", "backend/api/", "tools/", "backend/scripts/"),
    "ASSERT_RUNTIME": ("backend/engine/", "backend/api/"),
    "PRINT_CALL": ("backend/engine/", "backend/api/"),
}
EXCLUDE_TYPE_SPECIFIC = ("backend/engine/adapters/", "backend/engine/configs/", "backend/tests/")

for cat, pat in CATEGORIES.items():
    rx = re.compile(pat)
    print(f"\n===== {cat} =====")
    for f in files:
        if any(s in f for s in skip) and not (cat == "URL_OR_HOST" and f.endswith(".md")):
            continue
        if cat in SCOPE and not f.startswith(SCOPE[cat]):
            continue
        if cat == "TYPE_SPECIFIC" and f.startswith(EXCLUDE_TYPE_SPECIFIC):
            continue
        if cat in ("MAGIC_NUMBER", "ASSERT_RUNTIME", "PRINT_CALL") and "/tests/" in f:
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"!! cannot read {f}: {exc}", file=sys.stderr)
            continue
        for n, line in enumerate(lines, 1):
            if rx.search(line) and not line.lstrip().startswith(("#", "//")) or (cat in ("TODO_MARKER", "SUPPRESSION") and rx.search(line)):
                print(f"{f}:{n}: {line.strip()[:160]}")
