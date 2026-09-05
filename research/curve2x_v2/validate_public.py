#!/usr/bin/env python3
"""CURVE2X V2 — validator PUBLIC (ruleaza din pachetul publicat, fara date private): (1) SHA256SUMS.txt vs fisierele prezente, (2) reproducibility_manifest.json consistent
cu sumele, (3) absenta cailor efemere (/tmp/claude, scratchpad) in fisierele publicate, (4) testele sintetice ruleaza integral fara date private, (5) garda de politica din artefact.
Iesire: linii PASS/FAIL si cod de iesire 0/1."""
import os,sys,re,json,hashlib,subprocess,tempfile
HERE=os.path.dirname(os.path.abspath(__file__)); ok=True
def report(name,cond,detail=""):
    global ok; ok=ok and bool(cond); print(("PASS" if cond else "FAIL"),name,detail)
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
sums={}
for l in open(os.path.join(HERE,"SHA256SUMS.txt")):
    h,f=l.strip().split("  ",1); sums[f]=h
missing=[f for f in sums if not os.path.exists(os.path.join(HERE,f))]; bad=[f for f in sums if f not in missing and sha(os.path.join(HERE,f))!=sums[f]]
report("sha256sums_match",not bad and not missing,f"{len(sums)} fisiere; lipsa {missing}; diferite {bad}")
man=json.load(open(os.path.join(HERE,"reproducibility_manifest.json"))); mm=man.get("files_sha256",{}); inc=[f for f in sums if f in mm and mm[f]!=sums[f]]
report("manifest_consistent_with_sums",not inc and set(mm)==set(sums),f"nepotriviri {inc}; doar in manifest {sorted(set(mm)-set(sums))[:5]}; doar in sums {sorted(set(sums)-set(mm))[:5]}")
EPH=re.compile(r"/tmp/claude|scratchpad"); eph=[]
for f in sums:
    p=os.path.join(HERE,f)
    if not os.path.exists(p) or f.endswith((".gz",".sqlite")) or f in ("publish_prep.py","amendments.md","amendments_manifest.json"): continue
    if EPH.search(open(p,errors="ignore").read()): eph.append(f)
report("no_ephemeral_paths",not eph,f"{eph}")
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ,CURVE2X_DERIVED_DIR=td); r=subprocess.run([sys.executable,os.path.join(HERE,"test_curve2x.py")],capture_output=True,text=True,env=env,cwd=os.path.dirname(os.path.dirname(HERE)) if os.path.basename(os.path.dirname(HERE))=="research" else HERE)
    report("synthetic_tests_without_private_data","ALL_PASS" in r.stdout,r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
art=json.load(open(os.path.join(HERE,"model_artifact.json"))); armed=bool(art.get("policy_enabled") is True and art.get("final_verdict")=="PAPER_CANDIDATE" and (art.get("grid_feasible") or 0)>0)
report("policy_guard_disarmed",not armed,f"policy_enabled={art.get('policy_enabled')} final_verdict={art.get('final_verdict')} grid_feasible={art.get('grid_feasible')}")
am=json.load(open(os.path.join(HERE,"amendments_manifest.json"))); report("amendments_manifest_present",am.get("sealed") is False and am.get("preregistered") is False,f"amendamente {len(am.get('amendments',[]))}")
rc=json.load(open(os.path.join(HERE,"replay_check.json"))); report("replay_paper_candidates_zero",rc.get("replay_paper_candidates")==0 and rc.get("paper_candidate_check") is True,f"{rc.get('replay_paper_candidates')} candidati, agreement {rc.get('AUTOMATION_REPLAY_AGREEMENT')}")
print("VALIDATION =","PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
