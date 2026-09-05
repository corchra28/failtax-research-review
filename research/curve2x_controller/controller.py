#!/usr/bin/env python3
"""PROSPECTIVE_SELF_LEARNING_CONTROLLER — CLI paper/shadow. Subcomenzi: init | run-cycle --mode replay --source <tape> --cutoff <UTC> | evaluate | gates | status | verify-journal.
run-cycle: Champion imuabil prezice in flux (jurnal append-only); la cutoff: labeler-ul separat eticheteaza predictiile maturizate (decizie + orizont + marja <= cutoff), un singur Challenger
este antrenat doar pe outcome-uri maturizate cu embargo, apoi Champion si Challenger prezic simultan (shadow) pana la sfarsit; labeler la final; evaluare prequentiala; porti; drift.
Nicio promovare automata; nicio schimbare de target/praguri; LIVE_TRADING_ENABLED=NO. Zero RPC."""
import os,sys,json,gzip,glob,time,argparse,collections,datetime,zlib,uuid,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import controller_lib as C; V=C.V; L=C.L; import numpy as np
ST=C.STATE; J=os.path.join(ST,"prediction_journal.jsonl"); O=os.path.join(ST,"outcomes.jsonl"); REF=os.path.join(ST,"reference_stats.json"); CH=os.path.join(ST,"challenger_artifact.json"); D2=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(C.ROOT,"research","curve2x_v2","derived")); D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(C.V3,"derived_v3"))
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
def utcts(s): return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc).timestamp()
def cmd_init(a):
    os.makedirs(ST,exist_ok=True); champ=C.Champion(); rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt") if '"split":"TRAIN"' in l]
    ref=C.reference_stats(rows,champ.art["features"]); json.dump(ref,open(REF,"w")); print(f"INIT | champion={champ.model_hash[:16]}.. feature_schema={champ.feature_schema_hash[:16]}.. reference TRAIN rows={len(rows)} policy_enabled=False")
def cmd_run_cycle(a):
    if not a.paper_only: raise SystemExit("PAPER_ONLY_REQUIRED")
    if a.mode!="replay": raise SystemExit("MODE_NOT_SUPPORTED (doar replay; nu exista mod live)")
    champ=C.Champion(); ref=json.load(open(REF)); cutoff=utcts(a.cutoff); models=[champ]; jr=C.Journal(J); E=C.Stream(); creates=collections.deque(); seq=0; n=0; t0=time.time(); drift_severe=False; policy_enabled=False; cycle_id=f"cycle-{a.cutoff.replace(' ','T')}"; challenger_info=None; clock=0; passed_cutoff=False
    files=sorted(glob.glob(os.path.join(a.source,"events_*.jsonl.gz"))); mints_seen=set(); last_eval_n=0
    print(f"RUN | mode=replay paper_only=True champion={champ.model_hash[:16]}.. cutoff={a.cutoff}Z cycle={cycle_id} LIVE_TRADING_ENABLED=NO",flush=True)
    def flush():
        nonlocal drift_severe
        while E.decisions:
            d=E.decisions.pop(0); row=dict(f=d["f"],ts=d["ts"]); ctx=dict(launches_10m=sum(1 for t in creates if t>=d["ts"]-600)); reg=C.regime_of(row,ctx); mints_seen.add(d["mint"])
            for m in models:
                sc=C.score_with(m,row,ref); act,why=C.decide(sc,m.policy or champ.policy,policy_enabled,drift_severe)
                rec=dict(prediction_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{m.model_hash}:{d['mint']}:{d['seq']}:{d['k']}")),mint_hash=V.mint_id(d["mint"]),mint=d["mint"],dec_i=d["dec_i"],decision_slot=d["slot"],decision_time=d["ts"],decision_time_utc=C.utc(d["ts"]),model_role=m.role,model_hash=m.model_hash,feature_schema_hash=m.feature_schema_hash,regime=reg,**sc,action=act,reason=why,policy_enabled=policy_enabled,features=d["f"],gap_known=False,cycle_id=cycle_id)
                jr.append(rec)
                if act=="WATCH" and not a.quiet: print(f"PRED | {m.role} | MINT={rec['mint_hash']} | {rec['decision_time_utc']} | P_TP_FIRST={sc['P_TP_FIRST']:.3f} | P_SL_FIRST={sc['P_SL_FIRST']:.3f} | P_TIMEOUT={sc['P_TIMEOUT']:.3f} | P_2X_LCB90={sc['P_2X_LCB90']:.3f} | EV_NET={sc['EV_NET']:+.4f} | EV_NET_LCB90={sc['EV_NET_LCB90']:+.4f} | support={sc['local_support']} | OOD={sc['OOD_score']:.2f} | ACTION={act} | REASON={why}",flush=True)
    def at_cutoff():
        nonlocal models,challenger_info
        jr.f.flush(); n_lab=C.label_matured(J,O,C.load_curves_index(f"{D2}/curve2x_curves.jsonl.gz",mints_seen),cutoff); rows=C.join(J,O); art,info=C.train_challenger(rows,cutoff,champ.art["features"],champ.art["fill"],cycle_id); challenger_info=info
        print(f"CUTOFF | {a.cutoff}Z labeled_matured={n_lab} challenger={'TRAINED' if art else 'NOT_TRAINED'} {info}",flush=True)
        if art:
            json.dump(art,open(CH,"w"),sort_keys=True,separators=(",",":"),default=float); ch=C.Challenger(art,info["sha256"]); ch.policy=champ.policy; models=[champ,ch]
            C.register_attempt("CHALLENGER_TRAINED",dict(cycle_id=cycle_id,challenger_sha256=info["sha256"],trained_on=art["trained_on"],window_start_ts=cutoff,window_end_ts=None,note="fereastra de evaluare shadow incepe la cutoff; un singur challenger per ciclu"))
        ev=C.prequential(rows,champ.policy,ref); 
        if ev.get("drift",{}).get("SEVERE"): print("DRIFT | SEVERE la cutoff => POLICY_ENABLED=false ACTION=WATCH REASON=MODEL_DRIFT",flush=True); return True
        return False
    for fp in files:
        for line in readlines(fp):
            if '"src":"pump"' not in line: seq+=1; continue
            try: r=json.loads(line); t=int(r["t"]); slot=r["slot"]
            except Exception: seq+=1; continue
            clock=t
            if not passed_cutoff and t>=cutoff: passed_cutoff=True; drift_severe=at_cutoff()
            for k,e in enumerate(r["events"]):
                ev=e.get("ev")
                if ev=="CreateEvent" and "mint" in e and "user" in e: E.create(t,slot,seq,e["mint"],e["user"]); creates.append(t); 
                elif ev=="TradeEvent" and all(x in e for x in ("mint","user","sol","tok","is_buy","rsol","rtok","vsol","vtok")): E.trade(e.get("ts") or t,slot,seq,k,e["mint"],e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"])
                elif ev=="CompleteEvent" and "mint" in e: E.complete(e["mint"])
                n+=1
            while creates and creates[0]<t-700: creates.popleft()
            flush(); seq+=1
            if seq%400000==0:
                print(f"HB | {os.path.basename(fp)} events={n} journal={jr.n} models={[m.role for m in models]} elapsed={time.time()-t0:.0f}s",flush=True)
                if os.path.exists(a.stop_file): print("STOP | stop file",flush=True); return
    jr.f.flush(); n_lab=C.label_matured(J,O,C.load_curves_index(f"{D2}/curve2x_curves.jsonl.gz",mints_seen),clock); print(f"END | labeled_matured_at_end={n_lab} journal={jr.n} clock={C.utc(clock)}",flush=True)
    cmd_evaluate(a)
def cmd_evaluate(a):
    champ=C.Champion(); ref=json.load(open(REF)); rows=C.join(J,O); by={r:[x for x in rows if x["model_role"]==r] for r in ("CHAMPION","CHALLENGER")}; ev={r:C.prequential(v,champ.policy,ref) for r,v in by.items() if v}
    # comparatie pereche pe aceleasi decizii (dupa cutoff)
    ch={x["mint_hash"]:x for x in by["CHALLENGER"]}; pair=[(x,ch[x["mint_hash"]]) for x in by["CHAMPION"] if x["mint_hash"] in ch and x.get("label_quality")=="OK"]
    def ll(xs): 
        P=np.array([[x["P_TP_FIRST"],x["P_SL_FIRST"],x["P_TIMEOUT"]] for x in xs]); Y=np.array([[x["state"]=="TP_FIRST",x["state"]=="SL_FIRST",x["state"]=="TIMEOUT_OTHER"] for x in xs],float); return L.log_loss(P,Y)
    cmp_=dict(n_paired=len(pair),champion_log_loss=ll([p[0] for p in pair]) if pair else None,challenger_log_loss=ll([p[1] for p in pair]) if pair else None,agreement_action=float(np.mean([p[0]["action"]==p[1]["action"] for p in pair])) if pair else None)
    stress={}
    if by["CHALLENGER"]:
        sel=[x for x in by["CHALLENGER"] if x.get("label_quality")=="OK" and x["action"]=="WATCH"]; stress=dict(land5=float(np.mean([x["realized_net_pnl_land5"] for x in sel if x.get("realized_net_pnl_land5") is not None])) if sel else None,cost125=float(np.mean([x["realized_net_pnl_cost125"] for x in sel if x.get("realized_net_pnl_cost125") is not None])) if sel else None)
    g,allstat=C.promotion_gates(ev.get("CHALLENGER",{}),stress) if by["CHALLENGER"] else ({"CHALLENGER":"ABSENT"},False)
    drift_any=any((v.get("drift") or {}).get("SEVERE") for v in ev.values())
    n_tried=C.n_challengers_tried(); rb=C.rollback_check(ev.get("CHAMPION"))
    if rb and a.__dict__.get("allow_rollback"): C.do_rollback("LCB95<0 sau drift sever pe fereastra prospectiva")
    C.register_attempt("PROMOTION_EVAL",dict(n_challengers_tried=n_tried,bonferroni_alpha=C.bonferroni_alpha(),all_statistical_gates_pass=allstat,window_end_ts=max((r["decision_time"] for r in rows),default=None),untouched_window_required=True))
    rep=dict(label="PROSPECTIVE_SELF_LEARNING_CONTROLLER / REPLAY_DEMONSTRATION_ON_HISTORICAL_TAPE (nu forward real)",attempts_registry=dict(n_challengers_tried=n_tried,bonferroni_alpha=C.bonferroni_alpha(),rollback_condition_met=rb,rollback_policy="automat la ultimul champion arhivat (daca exista); promovarea ramane manuala"),generated=time.strftime("%Y-%m-%d %H:%M:%S %Z"),champion=dict(model_hash=champ.model_hash,policy=champ.policy,policy_enabled=False),journal=C.Journal.verify(J),prequential=ev,champion_vs_challenger=cmp_,challenger_stress=stress,promotion_gates=g,all_statistical_gates_pass=allstat,
      POLICY_ENABLED=False,DRIFT_SEVERE=drift_any,ACTION_ON_DRIFT="WATCH / MODEL_DRIFT" if drift_any else None,PROMOTION="NONE (aprobare umana obligatorie; niciodata automata)",READY_FOR_TINY_CAPITAL_REVIEW=("YES" if allstat else "NO"),LIVE_TRADING_ENABLED="NO")
    json.dump(rep,open(os.path.join(ST,"evaluation_report.json"),"w"),indent=1,default=float); print(json.dumps(dict(journal=rep["journal"],gates=g,all_statistical_gates_pass=allstat,ready_for_tiny_capital_review=rep["READY_FOR_TINY_CAPITAL_REVIEW"],champion=ev.get("CHAMPION",{}).get("selected_region"),challenger=ev.get("CHALLENGER",{}).get("selected_region"),cmp=cmp_,drift={k:(v.get("drift") or {}).get("SEVERE") for k,v in ev.items()}),default=float)[:2500]); print("EVALUATE_DONE")
def cmd_run_forward(a):
    """FORWARD PAPER autentic: citeste doar fisiere NOI dintr-un director de colectare (scris de un colector extern aprobat separat), in ordinea sosirii; nu re-citeste banda istorica;
    spec-ul inghetat (forward_spec.json) fixeaza model/prag/schema/porti; predictiile se scriu append-only inainte de orice outcome; labeler la maturitate 960 s; NICIO reantrenare in confirmare."""
    if not a.paper_only: raise SystemExit("PAPER_ONLY_REQUIRED")
    spec=json.load(open(os.path.join(HERE,"forward_spec.json"))); champ=C.Champion()
    if champ.model_hash!=spec["model_hash"] or champ.feature_schema_hash!=spec["feature_schema_hash"] or champ.policy!=spec["policy"]: raise SystemExit("FORWARD_SPEC_MISMATCH (model/schema/prag diferit de spec-ul inghetat)")
    ref=json.load(open(REF)); FJ=os.path.join(ST,"forward_prediction_journal.jsonl"); FO=os.path.join(ST,"forward_outcomes.jsonl"); jr=C.Journal(FJ); E=C.Stream(); creates=collections.deque(); seen=set(json.load(open(os.path.join(ST,"forward_files_done.json")))) if os.path.exists(os.path.join(ST,"forward_files_done.json")) else set(); seq=0; n=0; decided=set()
    if os.path.exists(FJ):
        for l in open(FJ): decided.add(json.loads(l)["mint"])
    print(f"FORWARD | paper_only=True champion={champ.model_hash[:16]}.. spec_frozen_at={spec['frozen_at']} maturity_s={spec['maturity_s']} files_done={len(seen)} LIVE_TRADING_ENABLED=NO",flush=True)
    files=[f for f in sorted(glob.glob(os.path.join(a.source,"events_*.jsonl.gz"))) if os.path.basename(f) not in seen and os.path.getmtime(f)<time.time()-a.settle_s]
    if not files: print("FORWARD | niciun fisier nou de procesat (colectorul extern nu a fost pornit sau nu a produs fisiere inchise)",flush=True); return
    for fp in files:
        for line in readlines(fp):
            if '"src":"pump"' not in line: seq+=1; continue
            try: r=json.loads(line); t=int(r["t"]); slot=r["slot"]
            except Exception: seq+=1; continue
            for k,e in enumerate(r["events"]):
                ev=e.get("ev")
                if ev=="CreateEvent" and "mint" in e and "user" in e: E.create(t,slot,seq,e["mint"],e["user"]); creates.append(t)
                elif ev=="TradeEvent" and all(x in e for x in ("mint","user","sol","tok","is_buy","rsol","rtok","vsol","vtok")): E.trade(e.get("ts") or t,slot,seq,k,e["mint"],e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"])
                elif ev=="CompleteEvent" and "mint" in e: E.complete(e["mint"])
                n+=1
            while creates and creates[0]<t-700: creates.popleft()
            while E.decisions:
                d=E.decisions.pop(0)
                if d["mint"] in decided: continue
                decided.add(d["mint"]); row=dict(f=d["f"],ts=d["ts"]); sc=C.score_with(champ,row,ref); act,why=C.decide(sc,champ.policy,False,False)
                jr.append(dict(prediction_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{champ.model_hash}:{d['mint']}:{d['seq']}:{d['k']}")),mint_hash=V.mint_id(d["mint"]),mint=d["mint"],dec_i=d["dec_i"],decision_slot=d["slot"],decision_time=d["ts"],decision_time_utc=C.utc(d["ts"]),model_role="CHAMPION",model_hash=champ.model_hash,feature_schema_hash=champ.feature_schema_hash,regime=C.regime_of(row,dict(launches_10m=sum(1 for x in creates if x>=d["ts"]-600))),**sc,action=act,reason=why,policy_enabled=False,features=d["f"],forward=True,spec_sha256=spec["spec_sha256"]))
            seq+=1
        seen.add(os.path.basename(fp)); json.dump(sorted(seen),open(os.path.join(ST,"forward_files_done.json"),"w"))
    print(f"FORWARD | files={len(files)} events={n} journal={jr.n} (outcome-urile se eticheteaza separat, dupa {spec['maturity_s']} s, cu `label-forward`)",flush=True)
def cmd_status(a):
    print("MODE = replay/shadow paper-only | LIVE_TRADING_ENABLED = NO | POLICY_ENABLED = False"); c=json.load(open(os.path.join(HERE,"champion.json"))); print("CHAMPION =",c["artifact_sha256"][:16],"immutable =",c["immutable"])
    if os.path.exists(J): print("JOURNAL =",C.Journal.verify(J)); 
    if os.path.exists(O): print("OUTCOMES =",sum(1 for _ in open(O)))
    if os.path.exists(os.path.join(ST,"evaluation_report.json")): r=json.load(open(os.path.join(ST,"evaluation_report.json"))); print("GATES =",r["promotion_gates"]); print("READY_FOR_TINY_CAPITAL_REVIEW =",r["READY_FOR_TINY_CAPITAL_REVIEW"])
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True); sub.add_parser("init"); r=sub.add_parser("run-cycle"); r.add_argument("--mode",required=True); r.add_argument("--source",required=True); r.add_argument("--cutoff",required=True); r.add_argument("--paper-only",action="store_true"); r.add_argument("--stop-file",default=os.path.join(ST,"STOP")); r.add_argument("--quiet",action="store_true")
    e=sub.add_parser("evaluate"); e.add_argument("--allow-rollback",action="store_true"); sub.add_parser("status"); sub.add_parser("verify-journal"); f=sub.add_parser("run-forward"); f.add_argument("--source",required=True); f.add_argument("--paper-only",action="store_true"); f.add_argument("--settle-s",type=int,default=120); a=ap.parse_args()
    if a.cmd=="init": cmd_init(a)
    elif a.cmd=="run-cycle": cmd_run_cycle(a)
    elif a.cmd=="evaluate": cmd_evaluate(a)
    elif a.cmd=="status": cmd_status(a)
    elif a.cmd=="verify-journal": print(C.Journal.verify(J))
    elif a.cmd=="run-forward": cmd_run_forward(a)
if __name__=="__main__": main()
