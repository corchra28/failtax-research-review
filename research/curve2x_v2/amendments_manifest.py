"""CURVE2X V2 — manifest machine-readable al amendamentelor (COMPLIANCE_ONLY). sealed=false, preregistered=false. Hash-urile finale ale fisierelor publicate."""
import os,json,hashlib,time
HERE=os.path.dirname(os.path.abspath(__file__))
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
spec=json.load(open(os.path.join(HERE,"frozen_spec_V1_REJECTED.json"))); ch=json.load(open(os.path.join(HERE,".compliance_hashes.json"))) if os.path.exists(os.path.join(HERE,".compliance_hashes.json")) else {}
files=[l.strip() for l in open(os.path.join(HERE,"published_files.txt")) if l.strip()]
A=[dict(id=1,file="curve2x_lib.py",when="post-freeze, pre-outcome",reason="garda de gap (regula 31) folosita identic in batch si replay",outcome_driven=False),
   dict(id=2,file="model_stage.py",when="post-freeze, pre-outcome",reason="gap_known calculat cu aceeasi functie in batch",outcome_driven=False),
   dict(id=3,file="tape_pass.py",when="post-freeze, dupa prima constructie (fara selectie de model)",reason="constanta programului pentru PDA-ul pool-authority (PumpSwap in loc de pump.fun); splice_ok era 0/2739; trecerea si constructia rerulate",outcome_driven=False),
   dict(id=4,file="label_check.py",when="post-freeze",reason="bug al verificatorului independent (UNAVAILABLE pentru pozitii rezolvate pe curba inainte de migrare); LABEL_AGREEMENT 77,8 % -> 100 %",outcome_driven=False),
   dict(id=5,file="leakage_mutation.py",when="post-model",reason="testul muta 300 mint-uri simultan si detecta diferente de context de regim ale altor randuri; refacut cu ferestre disjuncte (235 randuri, 100 % identice)",outcome_driven=False),
   dict(id=6,file="curve2x_paper_watcher.py",when="post-model",reason="self-check-ul se declansa pe propria lista de token-uri; token-uri compuse",outcome_driven=False),
   dict(id=7,file="model_artifact.json",when="COMPLIANCE_ONLY",reason="policy_enabled=false, final_verdict=NO_VERIFIED_EDGE (garda; parametrii modelului neschimbati)",sha256_before=ch.get("model_artifact_sha256_before"),sha256_after=ch.get("model_artifact_sha256_after"),outcome_driven=False),
   dict(id=8,file="results.json",when="COMPLIANCE_ONLY",reason="poarta beats_state_headroom_baseline marcata N/A (baseline si politica cu 0 semnale); nicio cifra recalculata",sha256_before=ch.get("results_json_sha256_before"),outcome_driven=False),
   dict(id=9,file="curve2x_paper_watcher.py, curve2x_replay.py",when="COMPLIANCE_ONLY",reason="PAPER_CANDIDATE numai daca policy_enabled AND final_verdict==PAPER_CANDIDATE AND grid_feasible>0; altfel WATCH (ELIGIBLE_POLICY_DISABLED); replay repetat cu 0 candidati asteptati",outcome_driven=False),
   dict(id=10,file="toate scripturile, publish.sh",when="COMPLIANCE_ONLY",reason="cai efemere eliminate (CURVE2X_DERIVED_DIR), frozen_spec.json redenumit frozen_spec_V1_REJECTED.json (continut neschimbat), token exclusiv din GITHUB_TOKEN/gh auth, SHA256SUMS doar pentru fisierele publicate, validator public",outcome_driven=False)]
man=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",sealed=False,preregistered=False,generated=time.strftime("%Y-%m-%d %H:%M:%S %Z"),original_frozen_spec=dict(file="frozen_spec_V1_REJECTED.json",sha256=sha(os.path.join(HERE,"frozen_spec_V1_REJECTED.json")),frozen_at=spec.get("frozen_at"),code_sha256_at_freeze=spec.get("code_sha256"),status="V1_REJECTED (grila de politica infezabila; NO_VERIFIED_EDGE)"),
    amendments=A,final_file_sha256={f:sha(os.path.join(HERE,f)) for f in files if os.path.exists(os.path.join(HERE,f)) and f not in ("amendments_manifest.json","reproducibility_manifest.json","SHA256SUMS.txt")},model_hash_final=sha(os.path.join(HERE,"model_artifact.json")))
json.dump(man,open(os.path.join(HERE,"amendments_manifest.json"),"w"),indent=1); print("amendments_manifest written; model_hash_final",man["model_hash_final"])
