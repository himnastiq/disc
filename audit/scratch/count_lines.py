"""Count files and lines per area in the repository."""

import collections
import subprocess

files = subprocess.run(
    ["git", "ls-files"],
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout.splitlines()

areas = collections.defaultdict(lambda: {"count": 0, "lines": 0})
for f in files:
    parts = f.split("/")
    area = parts[0] if len(parts) > 1 else "(root)"
    if area == "backend" and len(parts) > 1:
        area = "backend/" + parts[1]
    areas[area]["count"] += 1
    try:
        with open(f, encoding="utf-8") as fh:
            areas[area]["lines"] += sum(1 for _ in fh)
    except (OSError, UnicodeDecodeError):
        continue

for a in sorted(areas):
    d = areas[a]
    print(f"{a}: {d['count']} files, {d['lines']} lines")
print(f"TOTAL: {len(files)} files")
