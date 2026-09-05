#!/usr/bin/env python3
"""CURVE2X V3 — validator PUBLIC (fara date private, fara cai /tmp/claude): sume, manifest, cai efemere, teste sintetice, garda de politica (policy_enabled=false, watcher fara PAPER_CANDIDATE), replay."""
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
man=json.load(open(os.path.join(HERE,"reproducibility_manifest.json"))); rep("manifest_consistent",man.get("files_sha256")==sums,"")
EPH=re.compile(r"/tmp/claude|scratchpad"); eph=[f for f in sums if os.path.exists(os.path.join(HERE,f)) and f not in ("publish_prep_v3.py",) and EPH.search(open(os.path.join(HERE,f),errors="ignore").read())]; rep("no_ephemeral_paths",not eph,f"{eph}")
before={f:sha(os.path.join(HERE,f)) for f in sums if os.path.exists(os.path.join(HERE,f))}
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ,CURVE2X_DERIVED_DIR=td,CURVE2X_V3_DERIVED_DIR=td,CURVE2X_TEST_OUT=os.environ.get("CURVE2X_TEST_OUT",td)); r=subprocess.run([sys.executable,os.path.join(HERE,"tests_v3.py")],capture_output=True,text=True,env=env,cwd=HERE); rep("synthetic_tests_without_private_data","ALL_PASS" in r.stdout,(r.stdout.strip().splitlines() or [r.stderr[-200:]])[-1])
after={f:sha(os.path.join(HERE,f)) for f in sums if os.path.exists(os.path.join(HERE,f))}; rep("tests_did_not_mutate_published_files",before==after,[f for f in before if before[f]!=after.get(f)])
gs=subprocess.run(["git","status","--porcelain","--",HERE],capture_output=True,text=True,cwd=HERE); rep("git_status_clean_after_validation",gs.returncode!=0 or not gs.stdout.strip(),gs.stdout.strip()[:200] if gs.returncode==0 else "nu este repo git (ok)")
art=json.load(open(os.path.join(HERE,"model_artifact.json"))); rep("policy_enabled_false",art.get("policy_enabled") is False,f"final_verdict={art.get('final_verdict')}")
src=open(os.path.join(HERE,"watcher_v3.py")).read(); rep("watcher_never_emits_paper_candidate","\"PAPER_CANDIDATE\"" not in src.replace("PAPER_CANDIDATE=0","").replace("PAPER_CANDIDATE_POSSIBLE=False","") and "action,why=\"WATCH\"" in src,"")
rc=json.load(open(os.path.join(HERE,"replay_check.json"))); rep("replay_agreement_100",rc.get("AUTOMATION_REPLAY_AGREEMENT")==1.0 and rc.get("paper_candidates_emitted")==0,f"{rc.get('matching')}/{rc.get('batch_decisions')}")
lk=json.load(open(os.path.join(HERE,"leakage_report.json"))); rep("leakage_report_pass",lk.get("PASS") is True,""); dt=json.load(open(os.path.join(HERE,"determinism_check.json"))); rep("determinism_pass",dt.get("PASS") is True,"")
print("VALIDATION =","PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
