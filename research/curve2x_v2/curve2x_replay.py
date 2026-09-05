#!/usr/bin/env python3
"""CURVE2X V2 replay check: (1) deciziile batch din randurile etichetate cu artefactul inghetat (aceleasi functii ca watcher-ul), (2) watcher-ul in --mode replay pe banda existenta,
(3) comparatie exacta (mint, landmark) => AUTOMATION_REPLAY_AGREEMENT. Paper-only; zero RPC."""
import subprocess,sys,os,json,gzip,hashlib,collections,sqlite3,time
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0,HERE); import curve2x_lib as L
D=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(os.path.abspath(__file__)),"derived")); TAPE=os.path.join(ROOT,"strategy_m/data/tape")
def batch_decisions(mh):
    from curve2x_paper_watcher import Scorer
    art=json.load(open(os.path.join(HERE,"model_artifact.json"))); S=Scorer(art); man=json.load(open(f"{D}/curve2x_pass_manifest.json")); W=[tuple(w) for w in man["outage_windows"]]
    ct=[json.loads(l)[1] for l in gzip.open(f"{D}/curve2x_stream.jsonl.gz","rt") if l.startswith('["C"')]; W+=L.gap_windows_from_create_times(ct)
    by=collections.defaultdict(list)
    for l in gzip.open(f"{D}/curve2x_rows.jsonl.gz","rt"):
        r=json.loads(l); r["gap_known"]=L.known_gap(r["ts"],W); by[r["mint"]].append(r)
    dec={}
    for m,rows in by.items():
        scored=[dict(landmark=r["landmark"],f=r["f"],gap_known=r["gap_known"],**S.score(r)) for r in rows]; d=L.decide_mint(scored,S.pol,S.N)
        if d: dec[m]=d["landmark"]
    return dec
def main():
    mh=hashlib.sha256(open(os.path.join(HERE,"model_artifact.json"),"rb").read()).hexdigest(); t0=time.time(); bd=batch_decisions(mh); print("batch decisions",len(bd),round(time.time()-t0),"s",flush=True)
    st=os.path.join(HERE,"replay_state.sqlite"); lg=os.path.join(HERE,"replay_signals.jsonl")
    for p in (st,lg):
        if os.path.exists(p): os.remove(p)
    rc=subprocess.call([sys.executable,os.path.join(HERE,"curve2x_paper_watcher.py"),"--mode","replay","--source",TAPE,"--paper-only","--model-hash",mh,"--stop-file",os.path.join(HERE,"STOP_replay"),"--state",st,"--signal-log",lg,"--quiet"],cwd=ROOT)
    db=sqlite3.connect(st); rd={m:lm for m,lm in db.execute("select mint,landmark from signals where action='PAPER_CANDIDATE' or reason='ELIGIBLE_POLICY_DISABLED'")}; npc=db.execute("select count(*) from signals where action='PAPER_CANDIDATE'").fetchone()[0]
    same=sum(1 for m,lm in bd.items() if rd.get(m)==lm); union=len(set(bd)|set(rd)); agree=(same/union) if union else 1.0
    art=json.load(open(os.path.join(HERE,"model_artifact.json"))); armed=bool(art.get("policy_enabled") is True and art.get("final_verdict")=="PAPER_CANDIDATE" and (art.get("grid_feasible") or 0)>0)
    res=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",watcher_rc=rc,batch_eligible=len(bd),replay_eligible=len(rd),matching=same,AUTOMATION_REPLAY_AGREEMENT=agree,only_batch=len(set(bd)-set(rd)),only_replay=len(set(rd)-set(bd)),policy_armed=armed,replay_paper_candidates=npc,expected_paper_candidates=(len(bd) if armed else 0),paper_candidate_check=(npc==(len(bd) if armed else 0)),model_hash=mh,runtime_s=round(time.time()-t0,1))
    json.dump(res,open(os.path.join(HERE,"replay_check.json"),"w"),indent=1); print(json.dumps(res)); print("REPLAY_DONE")
if __name__=="__main__": main()
