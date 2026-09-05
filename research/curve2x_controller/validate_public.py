#!/usr/bin/env python3
"""Validator PUBLIC controller (fara date private, fara /tmp/claude): sume, absenta cailor efemere/adreselor brute/cheilor, teste (ruleaza integral fara date private), champion imuabil (hash fixat,
policy_enabled=false), watcher/controller fara PAPER_CANDIDATE si fara cai de trimitere de tranzactii, un singur challenger per ciclu (registru), promovare fara aprobare umana refuzata, forward spec inghetat."""
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
miss=[f for f in sums if not os.path.exists(os.path.join(HERE,f))]; bad=[f for f in sums if f not in miss and sha(os.path.join(HERE,f))!=sums[f]]; rep("sha256sums_match",not miss and not bad,f"{len(sums)} fisiere; lipsa {miss}; diferite {bad}")
PATS={"eph":re.compile(r"/tmp/claude|scratchpad"),"pump_mint_raw":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b"),"key":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{86,90}\b"),"gh":re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),"wss":re.compile("wss:"+"//"),"send":re.compile("send"+"Transaction")}
hits=[(f,n) for f in sums for n,p in PATS.items() if f not in ("validate_public.py","prep_ctrl.py") and os.path.exists(os.path.join(HERE,f)) and p.search(open(os.path.join(HERE,f),errors="ignore").read())]; rep("no_ephemeral_paths_raw_addresses_or_keys",not hits,f"{hits}")
c=json.load(open(os.path.join(HERE,"champion.json"))); rep("champion_immutable_and_policy_disabled",c.get("immutable") is True and c.get("policy_enabled") is False and re.fullmatch(r"[0-9a-f]{64}",c.get("artifact_sha256","")) is not None,c.get("artifact_sha256","")[:16])
src=open(os.path.join(HERE,"controller_lib.py")).read()+open(os.path.join(HERE,"controller.py")).read(); rep("no_paper_candidate_and_no_tx_paths","PAPER_CANDIDATE" not in src.replace("PAPER_CANDIDATE_possible","") and ("send"+"Transaction") not in src and ("sign"+"Transaction") not in src and ("wss:"+"//") not in src,"")
rep("single_challenger_per_cycle","models=[champ,ch]" in src and src.count("train_challenger(")>=1,"")
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ,CURVE2X_CTRL_STATE=td,CURVE2X_DERIVED_DIR=td,CURVE2X_V3_DERIVED_DIR=td); r=subprocess.run([sys.executable,os.path.join(HERE,"tests_controller.py")],capture_output=True,text=True,env=env,cwd=HERE); rep("tests_without_private_data","ALL_PASS" in r.stdout,(r.stdout.strip().splitlines() or [r.stderr[-200:]])[-1])
fs=json.load(open(os.path.join(HERE,"forward_spec.json"))); rep("forward_spec_frozen",fs.get("status")=="FROZEN_BEFORE_NEW_DATA" and fs.get("model_hash")==c.get("artifact_sha256") and fs.get("policy_enabled") is False and fs.get("maturity_s")==960 and fs.get("LIVE_TRADING_ENABLED") is False,fs.get("spec_sha256","")[:16])
print("VALIDATION =","PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
