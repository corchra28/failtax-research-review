"""CURVE2X V3 RECLAIM — verificarea acordului batch vs streaming: (mint, dec_i, probabilitati (1e-9), action, reason) trebuie sa coincida 100 %."""
import os,sys,gzip,json,subprocess,hashlib,time,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L; import model_v3 as M3
D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(HERE,"derived_v3")); TAPE=os.environ.get("CURVE2X_TAPE_DIR",os.path.join(os.path.dirname(os.path.dirname(HERE)),"strategy_m","data","tape"))
def main():
    t0=time.time(); art=json.load(open(os.path.join(HERE,"model_artifact.json"))); mh=hashlib.sha256(open(os.path.join(HERE,"model_artifact.json"),"rb").read()).hexdigest(); fl=art["features"]; fill=np.array(art["fill"]); pol=art["policy"]
    rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt")]; X,_=L.X_of(rows,fl,fill); sc=M3.score(rows,X,art["models"],fl); batch={}
    for r,s in zip(rows,sc): a,w=M3.decide(s,pol); batch[r["mint"]]=dict(dec_i=r["dec_i"],p_tp=s["p_tp"],p_sl=s["p_sl"],p_to=s["p_to"],action=a,reason=w)
    out=os.path.join(HERE,"replay_signals.jsonl"); rc=subprocess.call([sys.executable,os.path.join(HERE,"watcher_v3.py"),"--mode","replay","--source",TAPE,"--paper-only","--model-hash",mh,"--stop-file",os.path.join(HERE,"STOP_replay"),"--out",out,"--quiet"])
    rep={}
    for l in open(out): x=json.loads(l); rep[x["mint"]]=dict(dec_i=x["dec_i"],p_tp=x["p_tp"],p_sl=x["p_sl"],p_to=x["p_to"],action=x["action"],reason=x["reason"])
    keys=set(batch)|set(rep); same=0; mism=[]
    for m in keys:
        b=batch.get(m); r=rep.get(m)
        ok=b is not None and r is not None and b["dec_i"]==r["dec_i"] and b["action"]==r["action"] and b["reason"]==r["reason"] and all(abs(b[k]-r[k])<1e-9 for k in ("p_tp","p_sl","p_to"))
        same+=ok
        if not ok and len(mism)<10: mism.append(dict(mint_id=V.mint_id(m),batch=b,replay=r))
    res=dict(label="HISTORICAL_DEV_NOT_SEALED",watcher_rc=rc,batch_decisions=len(batch),replay_decisions=len(rep),matching=same,AUTOMATION_REPLAY_AGREEMENT=(same/len(keys)) if keys else 1.0,paper_candidates_emitted=0,fields_compared=["mint","dec_i","p_tp","p_sl","p_to","action","reason"],mismatches=mism,model_hash=mh,runtime_s=round(time.time()-t0,1))
    json.dump(res,open(os.path.join(HERE,"replay_check.json"),"w"),indent=1,default=float); print(json.dumps({k:v for k,v in res.items() if k!="mismatches"})); print("mismatches",mism[:3]); print("REPLAY_DONE")
if __name__=="__main__": main()
