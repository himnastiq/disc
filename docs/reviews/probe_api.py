import random
import statistics
import time

import fastapi
import starlette
from api.main import app
from fastapi.testclient import TestClient


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


with TestClient(app) as c:
    print("HEALTH", c.get("/v1/health").json().get("status"))
    types = c.get("/v1/types").json()["types"]
    print("P7 card types", [(t["id"], t["card_type"]) for t in types])
    ms = app.state.artifacts["movies"]
    ids = ms.items["item_id"].astype(str).tolist()[:5]
    r1 = c.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "k": 10, "history": [{"item_id": i} for i in ids]},
    )
    print("P1 no-signal", r1.status_code, r1.json().get("mode"))
    r2 = c.post(
        "/v1/recommend/cold-start",
        json={
            "type": "movies",
            "k": 10,
            "history": [{"item_id": i, "signal": 5.0} for i in ids],
        },
    )
    print("P2 signal5", r2.status_code, r2.json().get("mode"))
    users = ms.users["user_id"].astype(str).tolist()
    u = users[0]
    for k in (50, 51, 100, 101):
        print(
            "P3 k=",
            k,
            c.get(
                "/v1/recommend", params={"type": "movies", "user_id": u, "k": k}
            ).status_code,
        )
    body = c.get(
        "/v1/recommend", params={"type": "movies", "user_id": u, "k": 5}
    ).json()
    print("P4 meta keys", sorted(body.get("meta", {}).keys()))
    inter = ms.interactions
    pos = (
        inter[inter["positive"].astype(bool)]
        .groupby(inter["user_id"].astype(str))
        .size()
    )
    low = [x for x in pos[pos < 3].index.tolist()]
    if low:
        lu = low[0]
        rr = c.get(
            "/v1/recommend", params={"type": "movies", "user_id": lu, "k": 10}
        ).json()
        pp = c.get("/v1/popular", params={"type": "movies", "k": 10}).json()
        a = [x["item_id"] for x in rr.get("results", [])]
        b = [x["item_id"] for x in pp.get("results", [])]
        print(
            "P5 low-positive user", lu, "mode", rr.get("mode"), "equals_popular", a == b
        )
    else:
        print("P5 no user with 1-2 positives found")
    random.seed(0)
    sample = random.sample(users, min(100, len(users)))
    t = []
    for x in sample:
        s = time.perf_counter()
        c.get("/v1/recommend", params={"type": "movies", "user_id": x, "k": 10})
        t.append((time.perf_counter() - s) * 1000)
    med_t = statistics.median(t)
    p95_t = pct(t, 0.95)
    max_t = max(t)
    print(f"P6 ms p50 {med_t:.1f} p95 {p95_t:.1f} max {max_t:.1f}")
    prof = c.get(f"/v1/users/{u}/profile", params={"type": "movies"}).json()
    print("P8 top_categories", len(prof.get("top_categories", [])))
print("P9 starlette", starlette.__version__, "fastapi", fastapi.__version__)
