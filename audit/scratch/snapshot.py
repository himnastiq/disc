"""Usage: python audit/scratch/snapshot.py before|after   -> writes audit/scratch/snapshot_<name>.json"""
import hashlib
import json
import pathlib
import subprocess
import sys

name = sys.argv[1] if len(sys.argv) > 1 else "before"
roots = ["artifacts", "data/processed"]
out = {}

def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

tracked = subprocess.run(
    ["git", "ls-files"],
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout.splitlines()
for f in tracked:
    p = pathlib.Path(f)
    if p.is_file():
        out[f] = sha(p)
for r in roots:
    for p in pathlib.Path(r).rglob("*") if pathlib.Path(r).exists() else []:
        if p.is_file():
            out[p.as_posix()] = sha(p)

pathlib.Path("audit/scratch").mkdir(parents=True, exist_ok=True)
pathlib.Path(f"audit/scratch/snapshot_{name}.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
print(f"{len(out)} files hashed -> audit/scratch/snapshot_{name}.json")
if name == "after" and pathlib.Path("audit/scratch/snapshot_before.json").exists():
    before = json.loads(pathlib.Path("audit/scratch/snapshot_before.json").read_text(encoding="utf-8"))
    changed = sorted(k for k in set(before) | set(out) if before.get(k) != out.get(k))
    print("CHANGED FILES:", changed if changed else "none")
