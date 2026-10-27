import collections
import random

from api.main import app
from fastapi.testclient import TestClient

random.seed(0)
stats = collections.Counter()
fails = []
def chk(name, r, ok=(200,)):
    stats[(name, r.status_code)] += 1
    if r.status_code not in ok and len(fails) < 15:
        fails.append((name, r.status_code, r.text[:200]))
with TestClient(app) as c:
    types = [t["id"] for t in c.get("/v1/types").json()["types"]]
    print("TYPES", types)
    for t in types:
        art = app.state.artifacts.get(t)
        if art is None:
            print("SKIP unavailable", t)
            continue
        users = art.users["user_id"].astype(str).tolist()
        items = art.items["item_id"].astype(str).tolist()
        title_of = dict(zip(art.items["item_id"].astype(str), art.items["title"].astype(str)))
        for u in random.sample(users, min(20, len(users))):
            r = c.get("/v1/recommend", params={"type": t, "user_id": u, "k": 10})
            chk(t + "/recommend", r)
            if r.status_code == 200:
                res = r.json()["results"]
                ids = [x["item_id"] for x in res]
                if len(ids) != len(set(ids)):
                    fails.append((t, "duplicate ids", u))
                if t != "articles" and res and not any(x["categories"] for x in res):
                    fails.append((t, "all categories empty", u))
            chk(t + "/profile", c.get("/v1/users/" + u + "/profile", params={"type": t}))
        for i in random.sample(items, min(30, len(items))):
            chk(t + "/item", c.get("/v1/items/" + i, params={"type": t}))
            chk(t + "/similar", c.get("/v1/similar", params={"type": t, "item_id": i, "k": 5}))
            words = title_of[i].split()
            chk(t + "/search", c.get("/v1/items/search", params={"type": t, "q": words[0] if words else "a", "limit": 5}))
        hist = random.sample(items, min(5, len(items)))
        chk(t + "/cold", c.post("/v1/recommend/cold-start", json={"type": t, "k": 10, "history": [{"item_id": i} for i in hist]}))
        chk(t + "/popular", c.get("/v1/popular", params={"type": t, "k": 10}))
for k, v in sorted(stats.items()):
    print(k, v)
print("FAILS", len(fails))
for f in fails:
    print(f)
