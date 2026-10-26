import re
import sys
from pathlib import Path

cur_path = Path("IMPLEMENTATION_PLAN.md")
res_path = Path("IMPLEMENTATION_PLAN.restored.md")

cur = cur_path.read_text(encoding="utf-8").replace("\r\n", "\n")
if "## 4. Architecture" in cur:
    sys.exit("sections already present; nothing to do")

res = res_path.read_text(encoding="utf-8").replace("\r\n", "\n")


def clean(s: str) -> str:
    return re.sub(r"\n---\s*$", "", s.rstrip()).rstrip() + "\n\n---\n\n"


A = clean(res[res.index("## 4. Architecture") : res.index("# PHASES")])
B = clean(res[res.index("## 12. Known risks") : res.index("## 14. Session Log")])
i = cur.index("# PHASES")
cur = cur[:i] + A + cur[i:]
j = cur.index("## 14. Session Log")
cur = cur[:j] + B + cur[j:]
cur_path.write_text(cur, encoding="utf-8", newline="\n")
print("restored sections 4-13")
