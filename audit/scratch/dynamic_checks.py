import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
MINI = ROOT / "backend/tests/fixtures/artifacts_mini"
TMP = Path(tempfile.mkdtemp(prefix="discovery_audit_", dir=os.environ.get("TEMP")))
out = {}
# 1. artifact corruption
from engine.artifacts import verify_artifacts
from engine.errors import ArtifactCorruptError, ArtifactError


def cp():
    d = TMP / "art"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(MINI / "movies", d)
    return d

d = cp()
verify_artifacts(d)
out["verify_ok"] = True
(d / "items.parquet").unlink()
try:
    verify_artifacts(d)
    out["delete_detected"] = False
except ArtifactError as e:
    out["delete_detected"] = type(e).__name__
d = cp()
b = bytearray((d / "items.parquet").read_bytes())
b[10] ^= 1
(d / "items.parquet").write_bytes(bytes(b))
try:
    verify_artifacts(d)
    out["flip_detected"] = False
except ArtifactCorruptError:
    out["flip_detected"] = True
d = cp()
m = json.loads((d / "manifest.json").read_text())
m["artifact_schema_version"] = "9.9.9"
(d / "manifest.json").write_text(json.dumps(m))
try:
    verify_artifacts(d)
    out["version_detected"] = False
except ArtifactCorruptError:
    out["version_detected"] = True
# 2. API probes
os.environ["ARTIFACT_DIR"] = str(MINI)
os.environ.pop("RECOMMENDER_API_KEY", None)
from api.main import create_app
from fastapi.testclient import TestClient

with TestClient(create_app()) as c:
    probes={
      'health':c.get('/v1/health').status_code,
      'types':c.get('/v1/types').status_code,
      'about':c.get('/v1/about').status_code,
      'k0':c.get('/v1/recommend',params={'type':'movies','user_id':'1','k':0}).status_code,
      'k51':c.get('/v1/recommend',params={'type':'movies','user_id':'1','k':51}).status_code,
      'badtype':c.get('/v1/recommend',params={'type':'../movies','user_id':'1'}).status_code,
      'baduser':c.get('/v1/recommend',params={'type':'movies','user_id':'nope'}).status_code,
      'baditem':c.get('/v1/similar',params={'type':'movies','item_id':'nope','k':5}).status_code,
      'emptyq':c.get('/v1/items/search',params={'type':'movies','q':''}).status_code,
      'longq':c.get('/v1/items/search',params={'type':'movies','q':'x'*101}).status_code,
      'cold_empty':c.post('/v1/recommend/cold-start',json={'type':'movies','history':[],'k':5}).status_code,
      'cold_201':c.post('/v1/recommend/cold-start',json={'type':'movies','history':[{'item_id':str(i)} for i in range(201)],'k':5}).status_code,
      'cold_dupe':c.post('/v1/recommend/cold-start',json={'type':'movies','history':[{'item_id':'1'},{'item_id':'1'}],'k':5}).status_code,
      'cold_unknown':c.post('/v1/recommend/cold-start',json={'type':'movies','history':[{'item_id':'ZZZ'}],'k':5}).status_code,
    }
    r=c.get('/v1/recommend',params={'type':'movies','user_id':'1','k':10})
    j=r.json(); probes['recommend_k']=len(j['results']); probes['source']=j['meta']['source']
    # exclude a returned item
    iid=j['results'][0]['item_id']
    r2=c.get('/v1/recommend',params={'type':'movies','user_id':'1','k':10,'exclude':iid})
    probes['exclude_removed']=all(x['item_id']!=iid for x in r2.json()['results'])
    # prefix invariance k=5 vs 10
    r5=c.get('/v1/recommend',params={'type':'movies','user_id':'1','k':5}).json()['results']
    probes['prefix_stable']=[x['item_id'] for x in r5]==[x['item_id'] for x in j['results'][:5]]
    # search total_matches vs returned
    sr=c.get('/v1/items/search',params={'type':'movies','q':'a','limit':1}).json()
    probes['search_total_matches']=sr['total_matches']; probes['search_returned']=len(sr['results'])
    # metrics passthrough
    mp=c.get('/v1/metrics',params={'type':'movies'}).json()
    am=json.loads((MINI/'movies'/'metrics.json').read_text())
    probes['metrics_equal']=mp==am
    # API key non-ascii
    os.environ['RECOMMENDER_API_KEY']='këy'
    probes['key_missing']=c.get('/v1/health').status_code
    probes['key_wrong']=c.get('/v1/health',headers={'X-API-Key':'wrong'}).status_code
    probes['key_nonascii']=c.get('/v1/health',headers=[(b'X-API-Key','këy'.encode())]).status_code
    os.environ.pop('RECOMMENDER_API_KEY',None)
out['api_probes']=probes
print(json.dumps(out,indent=1))
print('TMP',TMP)
