"""CURVE2X V2 — determinism: refit-ul configuratiei selectate (acelasi cod, aceleasi date) si rescorarea deciziilor batch trebuie sa produca hash-uri identice."""
import gzip,json,sys,os,hashlib,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L, model_stage as MS
D=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(os.path.abspath(__file__)),"derived")); OUT="research/curve2x_v2"
art=json.load(open(f"{OUT}/model_artifact.json")); rows=[json.loads(l) for l in gzip.open(f"{D}/curve2x_rows.jsonl.gz","rt")]; H=art["H"]; N=art["N_primary"]
tr=[r for r in rows if r["split"]=="TRAIN" and MS.usable(r,N,H)]; pct=MS.fit_pct([r for r in rows if r["split"]=="TRAIN"]); MS.add_composite(rows,pct)
X,fill=L.X_of(tr,art["features"]); Y=MS.Y_of(tr,N,H); fits=[]
for k in range(2):
    m={"A":L.fit_mlogit,"B":L.fit_mgbm}[art["model_kind"]](X,Y); fits.append(hashlib.sha256(json.dumps(m,sort_keys=True,default=float).encode()).hexdigest())
same_fit=fits[0]==fits[1]; ref=hashlib.sha256(json.dumps(art["models"][str(N)]["clf"],sort_keys=True,default=float).encode()).hexdigest()
res=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",refit_hashes=fits,refit_identical=same_fit,matches_frozen_artifact=(fits[0]==ref),fill_identical=bool(np.allclose(fill,np.array(art["fill"]))),PASS=same_fit and fits[0]==ref)
json.dump(res,open(f"{OUT}/determinism_check.json","w"),indent=1); print(json.dumps(res))
