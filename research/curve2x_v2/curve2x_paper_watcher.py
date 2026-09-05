#!/usr/bin/env python3
"""CURVE2X V2 paper watcher — HISTORICAL_REMEDIATION_NOT_SEALED. PAPER-ONLY. Emite exclusiv REJECT / WATCH / PAPER_CANDIDATE.
Mod suportat: --mode replay pe o banda EXISTENTA (fisiere events_*.jsonl.gz). Nu exista mod live: nu deschide niciun endpoint RPC/WSS, nu semneaza, nu trimite tranzactii.
Garzi: model hash obligatoriu (procesul moare la nepotrivire), stale-data, unknown-schema, gap, maximum un semnal per mint, jurnal append-only, SQLite fara duplicate la restart,
stop file, limite de resurse (RLIMIT_AS, nice). Toate mesajele sunt linii simple in terminal."""
import argparse,os,sys,json,gzip,glob,time,sqlite3,hashlib,resource,zlib,datetime,collections
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import curve2x_lib as L
import numpy as np
FORBIDDEN=tuple(a+b for a,b in (("send","Transaction"),("sign","Transaction"),("PRIVATE","_KEY"),("SECRET","_KEY"),("wss",":"+"//"),("rpc","-api"),("heli","us")))   # compuse, ca sa nu apara literal in propriul cod
ENV_BAD=tuple(a+b for a,b in (("PRIVATE","_KEY"),("WALLET","_SECRET"),("KEY","PAIR")))
def die(msg,code=2): print(f"FATAL | {msg}",flush=True); sys.exit(code)
def self_check():
    src=open(__file__).read()+open(os.path.join(HERE,"curve2x_lib.py")).read()
    for tok in FORBIDDEN:
        if tok in src: die(f"SELF_CHECK_FAILED token interzis in cod: {tok}")
    for k in os.environ:
        if any(x in k.upper() for x in ENV_BAD): die(f"ENV_GUARD variabila de mediu interzisa prezenta: {k}")
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
def mint_id(m): return hashlib.sha256(("external-review-v1:"+m).encode()).hexdigest()[:16]
class Scorer:
    def __init__(self,art):
        self.art=art; self.fl=art["features"]; self.fill=np.array(art["fill"]); self.pct=art["pct"]; self.pol=art["policy"]; self.N=art["N_primary"]; m=art["models"][str(self.N)]; self.clf=m["clf"]; self.cal=m["cal"]; self.reg=m["reg"]; self.rs=m["regstats"]
    def score(self,row):
        f=row["f"]; Lm=str(row["landmark"])
        def P(k,v):
            q=self.pct[Lm][k]; return float(np.searchsorted(q,v,side="right")/len(q)) if v is not None else 0.5
        f["organic_acceleration"]=P("vel_last10",f["vel_last10"])*P("uniq_buyers",f["uniq_buyers"])*(1-P("hhi",f["hhi"]))*(1-P("top3_share",f["top3_share"]))
        X,_=L.X_of([row],self.fl,self.fill); Pm=L.apply_cal(self.cal,L.predict(self.clf,X)); ev=float(L.pred_gbm_reg(self.reg,X)[0])
        dec=int(np.searchsorted(self.rs["edges"],ev,side="right")); dec=min(max(dec,0),len(self.rs["sd"])-1); n=max(1,self.rs["n"][dec]); sd=self.rs["sd"][dec]
        p=float(Pm[0,0]); return dict(p_tp=p,p_sl=float(Pm[0,1]),p_to=float(Pm[0,2]),p_tp_lcb=max(0.0,p-1.2816*(p*(1-p)/n)**0.5),ev=ev,ev_lcb=ev-1.2816*sd/n**0.5,n_similar=int(n))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",required=True); ap.add_argument("--source",required=True); ap.add_argument("--paper-only",action="store_true"); ap.add_argument("--model-hash",required=True); ap.add_argument("--stop-file",required=True)
    ap.add_argument("--config",default=os.path.join(HERE,"config.example.json")); ap.add_argument("--state",default=None); ap.add_argument("--signal-log",default=None); ap.add_argument("--max-events",type=int,default=0); ap.add_argument("--quiet",action="store_true")
    a=ap.parse_args(); cfg=json.load(open(a.config))
    if not a.paper_only: die("PAPER_ONLY_REQUIRED: flag-ul --paper-only este obligatoriu")
    if a.mode!="replay": die(f"MODE_NOT_SUPPORTED: '{a.mode}' (singurul mod implementat este replay pe banda existenta; nu exista mod live)")
    self_check(); resource.setrlimit(resource.RLIMIT_AS,(cfg.get("max_rss_bytes",3*2**30),)*2); os.nice(cfg.get("nice",10))
    art_path=os.path.join(HERE,cfg.get("model_artifact","model_artifact.json")); s=open(art_path,"rb").read(); mh=hashlib.sha256(s).hexdigest()
    if mh!=a.model_hash: die(f"MODEL_HASH_MISMATCH: artefact {mh[:16]}.. != cerut {a.model_hash[:16]}..")
    art=json.loads(s); S=Scorer(art); pol=S.pol; N=S.N; watch_thr=cfg.get("watch_p_tp_min",0.20)
    files=sorted(glob.glob(os.path.join(a.source,"events_*.jsonl.gz"))) if os.path.isdir(a.source) else sorted(glob.glob(a.source))
    if not files: die("NO_SOURCE_FILES")
    state=a.state or os.path.join(HERE,"state.sqlite"); db=sqlite3.connect(state); db.executescript(open(os.path.join(HERE,"schema.sql")).read())
    decided={r[0] for r in db.execute("select mint from signals where action='PAPER_CANDIDATE'")}; ck=db.execute("select file,seq from checkpoint where id=1").fetchone()
    log=open(a.signal_log or os.path.join(HERE,"signals.jsonl"),"a")
    print(f"START | mode={a.mode} paper_only=True model_hash={mh[:16]}.. policy={json.dumps(pol)} files={len(files)} resume={ck} decided_before={len(decided)} stop_file={a.stop_file}",flush=True)
    OUT_W=[]; clog=os.path.join(os.path.dirname(files[0]),"collector.log")
    if os.path.exists(clog):
        o=None
        for line in open(clog):
            if len(line)<20: continue
            try: t=datetime.datetime.strptime(line[:19],"%Y-%m-%d %H:%M:%S").timestamp()
            except Exception: continue
            if "DECONECTARE" in line and o is None: o=t
            if "conectat:" in line and o is not None: OUT_W.append((o,t)); o=None
    windows=list(OUT_W); E=L.Engine(); seq=0; last_create_t=None; counts=collections.Counter(); n_ev=0; last_t=None; t0=time.time(); unknown=collections.Counter()
    def emit(row,sc,action,why):
        rec=dict(ts=row["ts"],mint_id=mint_id(row["mint"]),landmark=row["landmark"],action=action,reason=why,notional_sol=N,**{k:round(v,6) if isinstance(v,float) else v for k,v in sc.items()},headroom_025=round(row["f"]["headroom_025"],4),headroom_050=round(row["f"]["headroom_050"],4),headroom_100=round(row["f"]["headroom_100"],4),gap_known=row.get("gap_known",False),model_hash=mh[:16],paper_only=True)
        log.write(json.dumps(rec)+"\n"); log.flush()
        db.execute("insert or ignore into signals(mint,landmark,ts,action,reason,p_tp,p_sl,p_to,ev,ev_lcb,model_hash) values(?,?,?,?,?,?,?,?,?,?,?)",(row["mint"],row["landmark"],row["ts"],action,why,sc["p_tp"],sc["p_sl"],sc["p_to"],sc["ev"],sc["ev_lcb"],mh))
        if not a.quiet or action=="PAPER_CANDIDATE": print(f"SIGNAL | MINT={rec['mint_id']} | LANDMARK={row['landmark']}% | ACTION={action} | REASON={why} | P_TP_FIRST={sc['p_tp']:.3f} | P_SL_FIRST={sc['p_sl']:.3f} | P_TIMEOUT={sc['p_to']:.3f} | P_TP_FIRST_LCB90={sc['p_tp_lcb']:.3f} | EXPECTED_NET={sc['ev']:+.4f} SOL | EXPECTED_NET_LCB90={sc['ev_lcb']:+.4f} | N_SIMILAR_OOS={sc['n_similar']} | NOTIONAL={N} SOL | PAPER_ONLY",flush=True)
    for fp in files:
        fn=os.path.basename(fp)
        if ck and fn<ck[0]: continue
        for line in readlines(fp):
            if '"src":"pump"' not in line: seq+=1; continue
            if ck and fn==ck[0] and seq<=ck[1]: seq+=1; continue
            try: r=json.loads(line); t=int(r["t"]); slot=r["slot"]
            except Exception: unknown["BAD_RECORD"]+=1; seq+=1; continue
            if last_t is not None and t<last_t-300: unknown["TIME_REGRESSION"]+=1
            last_t=t
            for k,e in enumerate(r["events"]):
                ev=e.get("ev")
                if ev=="CreateEvent":
                    if not all(x in e for x in ("mint","user")): unknown["CreateEvent_schema"]+=1; continue
                    if last_create_t is not None and t-last_create_t>L.GAP_JUMP_S: windows.append((last_create_t,t)); print(f"GAP | discontinuitate {t-last_create_t:.0f}s intre {last_create_t} si {t}",flush=True)
                    last_create_t=t; E.on_event(["C",t,slot,seq,e["mint"],e["user"]])
                elif ev=="TradeEvent":
                    if not all(x in e for x in ("mint","user","sol","tok","is_buy","rsol","rtok","vsol","vtok")): unknown["TradeEvent_schema"]+=1; continue
                    E.on_event(["T",e.get("ts") or t,slot,seq,k,e["mint"],e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"]])
                elif ev=="CompleteEvent":
                    if "mint" not in e: unknown["CompleteEvent_schema"]+=1; continue
                    cts=int(next((x.get("ts") for x in r["events"] if x.get("ev")=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),t)); E.on_event(["X",cts,slot,seq,e["mint"]])
                else: unknown[ev or "NONE"]+=1
                n_ev+=1
            while E.rows:
                row=E.rows.pop(0); row["gap_known"]=L.known_gap(row["ts"],windows); counts["rows"]+=1
                if row["mint"] in decided: counts["ALREADY_DECIDED"]+=1; continue
                sc=S.score(row); sr=dict(landmark=row["landmark"],f=row["f"],gap_known=row["gap_known"],**sc); ok,why=L.eligible(sr,pol,N)
                if ok: decided.add(row["mint"]); emit(row,sc,"PAPER_CANDIDATE",why); counts["PAPER_CANDIDATE"]+=1
                elif sc["p_tp"]>=watch_thr and L.ENTRY_MIN<=row["landmark"]<=L.ENTRY_MAX: emit(row,sc,"WATCH",why); counts["WATCH"]+=1
                else: counts["REJECT"]+=1; counts["REJECT_"+why]+=1
            seq+=1
            if seq%200000==0:
                db.execute("insert or replace into checkpoint(id,file,seq) values(1,?,?)",(fn,seq)); db.commit()
                print(f"HB | file={fn} seq={seq} events={n_ev} rows={counts['rows']} candidates={counts['PAPER_CANDIDATE']} watch={counts['WATCH']} reject={counts['REJECT']} unknown={dict(unknown)} elapsed={time.time()-t0:.0f}s",flush=True)
                if os.path.exists(a.stop_file): print("STOP | stop file detectat; oprire curata",flush=True); db.commit(); return
                if sum(unknown.values())>cfg.get("max_unknown_events",1000): die("UNKNOWN_SCHEMA_GUARD: prea multe evenimente cu schema necunoscuta")
            if a.max_events and n_ev>=a.max_events: break
        db.execute("insert or replace into checkpoint(id,file,seq) values(1,?,?)",(fn,seq)); db.commit()
        if a.max_events and n_ev>=a.max_events: break
    db.commit(); print(f"DONE | events={n_ev} rows={counts['rows']} PAPER_CANDIDATE={counts['PAPER_CANDIDATE']} WATCH={counts['WATCH']} REJECT={counts['REJECT']} reasons={ {k:v for k,v in counts.items() if k.startswith('REJECT_')} } unknown={dict(unknown)} elapsed={time.time()-t0:.0f}s | LIVE_TRADING_ENABLED=NO",flush=True)
if __name__=="__main__": main()
