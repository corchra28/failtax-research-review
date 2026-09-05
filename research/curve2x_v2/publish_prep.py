"""CURVE2X V2 — pregatirea publicarii: scan secrete / termeni interzisi / RPC-WSS-sendTransaction-chei, SHA256SUMS, reproducibility_manifest.json. Nu publica nimic singur."""
import os,sys,re,json,hashlib,subprocess,time,glob
sys.path.insert(0,"research/curve2x_v2"); import curve2x_lib as L
OUT="research/curve2x_v2"; files=[l.strip() for l in open(f"{OUT}/published_files.txt") if l.strip() and l.strip() not in ("validate_public.py","reproducibility_manifest.json","SHA256SUMS.txt")]
PATS={"private_key_b58_64":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{86,90}\b"),"api_key_param":re.compile(r"api[-_]?key=",re.I),"helius_url":re.compile(r"helius-rpc\.com",re.I),"wss":re.compile(r"wss://"),"send_tx":re.compile(r"sendTransaction|signTransaction"),"github_token":re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),"aws":re.compile(r"AKIA[0-9A-Z]{16}"),"env_key":re.compile(r"PRIVATE_KEY|SECRET_KEY|KEYPAIR")}
ALLOW={"curve2x_paper_watcher.py":{"send_tx","env_key","wss"},"publish_prep.py":{"send_tx","env_key","wss","helius_url","api_key_param"},"README_AUTOMATION.md":{"send_tx","env_key"},"frozen_spec_V1_REJECTED.json":{"send_tx"},"amendments.md":set(),"model_card.md":{"send_tx"},"curve2x-paper.service.example":set()}
FORBID=re.compile(r"\b(BUY|SAFE|GUARANTEED|MINIM_2X)\b")
hits=[]; forb=[]
EPHEMERAL=re.compile(r"/tmp/claude|scratchpad"); eph=[]
for f in files:
    if f.endswith((".gz",".sqlite")) or not os.path.exists(os.path.join(OUT,f)): continue
    if EPHEMERAL.search(open(os.path.join(OUT,f),errors="ignore").read()) and f not in ("publish_prep.py","validate_public.py","amendments.md","amendments_manifest.json"): eph.append(f)
    try: txt=open(os.path.join(OUT,f),errors="ignore").read()
    except Exception: continue
    for name,p in PATS.items():
        if p.search(txt) and name not in ALLOW.get(f,set()): hits.append((f,name))
    for m in FORBID.finditer(txt): forb.append((f,m.group(0)))
if os.path.exists(f"{OUT}/results.json"):
    R=json.load(open(f"{OUT}/results.json"))
    for seg in R.get("evaluation",{}).values():
        for nn in seg.values(): nn.pop("signals_detail",None)
    json.dump(R,open(f"{OUT}/results_public.json","w"),indent=1,default=float)
sums={f:L.sha256_file(os.path.join(OUT,f)) for f in sorted(files) if os.path.exists(os.path.join(OUT,f))}
open(f"{OUT}/SHA256SUMS.txt","w").write("".join(f"{h}  {f}\n" for f,h in sums.items()))
commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True).stdout.strip()
man=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),source_commit_at_build=commit,files_sha256=sums,frozen_spec_sha256=sums.get("frozen_spec_V1_REJECTED.json"),model_hash=hashlib.sha256(open(f"{OUT}/model_artifact.json","rb").read()).hexdigest() if os.path.exists(f"{OUT}/model_artifact.json") else None,
    secret_scan_hits=hits,forbidden_term_hits=forb,ephemeral_path_hits=eph,published_files=sorted(files),rpc_calls=0,new_data=False,raw_tape_modified=False,live=False,python=sys.version.split()[0])
json.dump(man,open(f"{OUT}/reproducibility_manifest.json","w"),indent=1); print(json.dumps(dict(files=len(files),secret_hits=hits,forbidden=forb[:10],n_forbidden=len(forb),ephemeral=eph)))
