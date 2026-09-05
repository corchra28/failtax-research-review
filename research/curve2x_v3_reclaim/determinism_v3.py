"""CURVE2X V3 — determinism: refit-ul modelului selectat de doua ori (aceleasi date) => hash identic si egal cu artefactul inghetat."""
import os,sys,gzip,json,hashlib,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L; import model_v3 as M3
D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(HERE,"derived_v3")); art=json.load(open(os.path.join(HERE,"model_artifact.json")))
rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt")]; tr=[r for r in rows if r["split"]=="TRAIN" and M3.usable(r)]; X,fill=L.X_of(tr,art["features"]); Y=M3.Y_of(tr); hs=[]
for _ in range(2): m={"A":L.fit_mlogit,"B":L.fit_mgbm}[art["model_kind"]](X,Y); hs.append(hashlib.sha256(json.dumps(m,sort_keys=True,default=float).encode()).hexdigest())
ref=hashlib.sha256(json.dumps(art["models"]["clf"],sort_keys=True,default=float).encode()).hexdigest()
res=dict(label="HISTORICAL_DEV_NOT_SEALED",refit_identical=hs[0]==hs[1],matches_artifact=hs[0]==ref,fill_identical=bool(np.allclose(fill,np.array(art["fill"]))),PASS=bool(hs[0]==hs[1]==ref)); json.dump(res,open(os.path.join(HERE,"determinism_check.json"),"w"),indent=1); print(json.dumps(res))
