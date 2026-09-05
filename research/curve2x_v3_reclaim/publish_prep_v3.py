"""CURVE2X V3 — pregatirea publicarii: results_public.json (fara randuri per semnal), scan secrete/termeni/cai efemere, SHA256SUMS (doar fisierele publicate), reproducibility_manifest.json."""
import os,re,json,hashlib,subprocess,time,sys
HERE=os.path.dirname(os.path.abspath(__file__))
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
R=json.load(open(os.path.join(HERE,"results.json"))); json.dump(R,open(os.path.join(HERE,"results_public.json"),"w"),indent=1,default=float)   # results.json nu contine randuri per semnal (acestea sunt in signals_val_conf.json, nepublicat)
files=[l.strip() for l in open(os.path.join(HERE,"published_files.txt")) if l.strip()]
PATS={"key_b58":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{86,90}\b"),"api_key":re.compile(r"api[-_]?key=",re.I),"heli":re.compile("heli"+"us-rpc"),"wss":re.compile("wss:"+"//"),"send_tx":re.compile("send"+"Transaction|sign"+"Transaction"),"gh_token":re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),"env_key":re.compile("PRIVATE"+"_KEY|SECRET"+"_KEY")}
FORB=re.compile(r"\b(BUY|SAFE|GUARANTEED|MINIM_2X)\b"); EPH=re.compile(r"/tmp/claude|scratchpad"); hits=[]; forb=[]; eph=[]
for f in files:
    p=os.path.join(HERE,f)
    if not os.path.exists(p) or f in ("SHA256SUMS.txt","reproducibility_manifest.json"): continue
    txt=open(p,errors="ignore").read()
    for n,pat in PATS.items():
        if pat.search(txt) and f not in ("publish_prep_v3.py","validate_public.py","watcher_v3.py"): hits.append((f,n))
    for m in FORB.finditer(txt):
        if f not in ("publish_prep_v3.py","validate_public.py"): forb.append((f,m.group(0)))
    if EPH.search(txt) and f not in ("publish_prep_v3.py","validate_public.py"): eph.append(f)
sums={f:sha(os.path.join(HERE,f)) for f in sorted(files) if os.path.exists(os.path.join(HERE,f)) and f not in ("SHA256SUMS.txt","reproducibility_manifest.json","validate_public.py")}
open(os.path.join(HERE,"SHA256SUMS.txt"),"w").write("".join(f"{h}  {f}\n" for f,h in sums.items()))
commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=HERE).stdout.strip()
man=dict(label="HISTORICAL_DEV_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),source_commit_at_build=commit,files_sha256=sums,frozen_spec_sha256=sums.get("frozen_spec.json"),model_hash=sha(os.path.join(HERE,"model_artifact.json")),secret_scan_hits=hits,forbidden_term_hits=forb,ephemeral_path_hits=eph,rpc_calls=0,new_data=False,live=False,policy_enabled=False,python=sys.version.split()[0])
json.dump(man,open(os.path.join(HERE,"reproducibility_manifest.json"),"w"),indent=1); print(json.dumps(dict(files=len(sums),secret_hits=hits,forbidden=forb,ephemeral=eph)))
