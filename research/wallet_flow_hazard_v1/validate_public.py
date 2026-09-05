#!/usr/bin/env python3
"""Validator PUBLIC WALLET_FLOW_HAZARD_V1 (nemutant; fara date private): sume inainte/dupa teste, teste in director temporar, git status curat, fara cai efemere/adrese brute/chei, spec inghetat, artefact cu policy_enabled=false."""
import os,sys,re,json,hashlib,subprocess,tempfile
HERE=os.path.dirname(os.path.abspath(__file__)); ok=True
def rep(n,c,d=""):
    global ok; ok=ok and bool(c); print("PASS" if c else "FAIL",n,d)
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
sums={l.strip().split("  ",1)[1]:l.strip().split("  ",1)[0] for l in open(os.path.join(HERE,"SHA256SUMS.txt")) if l.strip()}
miss=[f for f in sums if not os.path.exists(os.path.join(HERE,f))]; bad=[f for f in sums if f not in miss and sha(os.path.join(HERE,f))!=sums[f]]; rep("sha256sums_match",not miss and not bad,f"{len(sums)}; lipsa {miss}; diferite {bad}")
PATS={"eph":re.compile(r"/tmp/claude|scratchpad"),"pump_mint_raw":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b"),"key":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{86,90}\b"),"gh":re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),"wss":re.compile("wss:"+"//")}
hits=[(f,n) for f in sums for n,p in PATS.items() if f not in ("validate_public.py","publish_prep_wfh.py") and os.path.exists(os.path.join(HERE,f)) and p.search(open(os.path.join(HERE,f),errors="ignore").read())]; rep("no_ephemeral_or_raw_addresses",not hits,f"{hits}")
before={f:sha(os.path.join(HERE,f)) for f in sums if os.path.exists(os.path.join(HERE,f))}
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ,WFH_DERIVED_DIR=td,CURVE2X_DERIVED_DIR=td,WFH_TEST_OUT=td); r=subprocess.run([sys.executable,os.path.join(HERE,"tests_wfh.py")],capture_output=True,text=True,env=env,cwd=HERE); rep("tests_without_private_data","ALL_PASS" in r.stdout,(r.stdout.strip().splitlines() or [r.stderr[-200:]])[-1])
after={f:sha(os.path.join(HERE,f)) for f in sums if os.path.exists(os.path.join(HERE,f))}; rep("tests_did_not_mutate_published_files",before==after,[f for f in before if before[f]!=after.get(f)])
gs=subprocess.run(["git","status","--porcelain","--",HERE],capture_output=True,text=True,cwd=HERE); rep("git_status_clean",gs.returncode!=0 or not gs.stdout.strip(),gs.stdout.strip()[:200])
art=json.load(open(os.path.join(HERE,"model_artifact.json"))); rep("policy_enabled_false",art.get("policy_enabled") is False,""); sp=json.load(open(os.path.join(HERE,"frozen_spec.json"))); rep("spec_label",sp.get("label")=="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED" and sp.get("sealed") is False,"")
print("VALIDATION =","PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
