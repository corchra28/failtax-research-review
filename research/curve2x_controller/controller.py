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
    """FORWARD PAPER autentic: doar fisiere NOI dintr-un director de colectare (colector extern aprobat separat); stare persistata atomic (Stream, seq, decided, hash-uri fisiere);
    la restart verifica integritatea si continua fara duplicate; spec_sha256 recalculat; lantul jurnalului verificat inainte de append; fara reantrenare; doar REJECT/WATCH."""
    import forward_lib as F
    if not a.paper_only: raise SystemExit("PAPER_ONLY_REQUIRED")
    spec=F.load_spec(os.path.join(HERE,"forward_spec.json")); champ=C.Champion()
    if champ.model_hash!=spec["model_hash"] or champ.feature_schema_hash!=spec["feature_schema_hash"] or champ.policy!=spec["policy"]: raise SystemExit("FORWARD_SPEC_MISMATCH (model/schema/prag diferit de spec-ul inghetat)")
    ref=json.load(open(REF)); FJ=os.path.join(ST,"forward_prediction_journal.jsonl"); SP=os.path.join(ST,"forward_state.json"); st=F.ForwardState.load(SP); bad=st.verify_files(a.source)
    if bad: raise SystemExit(f"PROCESSED_FILE_MODIFIED_OR_MISSING {bad[:3]} — refuz")
    jr=C.Journal(FJ); E=st.stream; creates=collections.deque(); seq=st.seq; n=0
    print(f"FORWARD | paper_only=True champion={champ.model_hash[:16]}.. spec={spec['spec_sha256'][:16]}.. files_done={len(st.files_done)} decided={len(st.decided)} journal={jr.n} LIVE_TRADING_ENABLED=NO",flush=True)
    files=[f for f in sorted(glob.glob(os.path.join(a.source,"events_*.jsonl.gz"))) if os.path.basename(f) not in st.files_done and os.path.getmtime(f)<time.time()-a.settle_s]
    if not files: print("FORWARD | niciun fisier nou de procesat",flush=True); return
    for fp in files:
        fh=F.sha_file(fp)
        for line in F.readlines(fp):
            if '"src":"pump"' not in line: seq+=1; continue
            try: r=json.loads(line); t=int(r["t"]); slot=r["slot"]
            except Exception: seq+=1; continue
            st.clock=max(st.clock,t)
            for k,e in enumerate(r["events"]):
                ev=e.get("ev")
                if ev=="CreateEvent" and "mint" in e and "user" in e: E.create(t,slot,seq,e["mint"],e["user"]); creates.append(t)
                elif ev=="TradeEvent" and all(x in e for x in ("mint","user","sol","tok","is_buy","rsol","rtok","vsol","vtok")): E.trade(e.get("ts") or t,slot,seq,k,e["mint"],e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"])
                elif ev=="CompleteEvent" and "mint" in e: E.complete(e["mint"])
                n+=1
            while creates and creates[0]<t-700: creates.popleft()
            while E.decisions:
                d=E.decisions.pop(0)
                if d["mint"] in st.decided: continue
                st.decided.add(d["mint"]); row=dict(f=d["f"],ts=d["ts"]); sc=C.score_with(champ,row,ref); act,why=C.decide(sc,champ.policy,False,False)
                jr.append(dict(prediction_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{champ.model_hash}:{d['mint']}:{d['seq']}:{d['k']}")),mint_hash=V.mint_id(d["mint"]),mint=d["mint"],dec_i=d["dec_i"],decision_slot=d["slot"],decision_time=d["ts"],decision_time_utc=C.utc(d["ts"]),model_role="CHAMPION",model_hash=champ.model_hash,feature_schema_hash=champ.feature_schema_hash,regime=C.regime_of(row,dict(launches_10m=sum(1 for x in creates if x>=d["ts"]-600))),**sc,action=act,reason=why,policy_enabled=False,features=d["f"],forward=True,spec_sha256=spec["spec_sha256"],source_file=os.path.basename(fp)))
            seq+=1
        st.files_done[os.path.basename(fp)]=fh; st.last_file=os.path.basename(fp); st.seq=seq; jr.f.flush(); os.fsync(jr.f.fileno()); st.save()
    print(f"FORWARD | files={len(files)} events={n} journal={jr.n} decided={len(st.decided)} clock={C.utc(st.clock)} state_saved=True",flush=True)
def cmd_label_forward(a):
    import forward_lib as F
    spec=F.load_spec(os.path.join(HERE,"forward_spec.json")); st=F.ForwardState.load(os.path.join(ST,"forward_state.json")); bad=st.verify_files(a.source)
    if bad: raise SystemExit(f"PROCESSED_FILE_MODIFIED_OR_MISSING {bad[:3]}")
    FJ=os.path.join(ST,"forward_prediction_journal.jsonl"); v=C.Journal.verify(FJ) if os.path.exists(FJ) else dict(ok=True,records=0)
    if not v.get("ok"): raise SystemExit("JOURNAL_CHAIN_BROKEN")
    n=F.label_forward(FJ,os.path.join(ST,"forward_outcomes.jsonl"),a.source,st.files_done,st.clock); print(f"LABEL_FORWARD | labeled={n} clock={C.utc(st.clock)} maturity_s={F.MATURITY_S} source=FORWARD_FILES_ONLY",flush=True)
def cmd_evaluate_forward(a):
    import forward_lib as F
    spec=F.load_spec(os.path.join(HERE,"forward_spec.json")); champ=C.Champion(); FJ=os.path.join(ST,"forward_prediction_journal.jsonl"); FO=os.path.join(ST,"forward_outcomes.jsonl")
    rows=C.join(FJ,FO) if os.path.exists(FJ) else []; ok=[r for r in rows if r.get("label_quality")=="OK" and r.get("state") in ("TP_FIRST","SL_FIRST","TIMEOUT_OTHER")]; sel=[r for r in ok if r["action"]=="WATCH"]
    # baseline state/headroom inghetat (hash in spec) cu aceeasi politica
    bl=json.load(open(os.path.join(HERE,"baseline_state_headroom.json"))); assert hashlib.sha256(open(os.path.join(HERE,"baseline_state_headroom.json"),"rb").read()).hexdigest()==spec["baseline_sha256"], "BASELINE_HASH_MISMATCH"
    bsel=[]
    if ok:
        Xb,_=L.X_of([dict(f=r["features"]) for r in ok],bl["features"],np.array(bl["fill"])); Pb=L.apply_cal(bl["models"]["cal"],L.predict(bl["models"]["clf"],Xb)); evb=L.pred_gbm_reg(bl["models"]["reg"],Xb); bsel=[r for r,p,e in zip(ok,Pb[:,0],evb) if p>=champ.policy["p_tp_min"] and e>0]
    n_tried=C.n_challengers_tried(); g,info=C.forward_gates(sel,ok,bsel,n_tried); allp=all(v is True for k,v in g.items() if k not in ("HUMAN_APPROVAL_REQUIRED","MULTIPLE_TESTING_CORRECTION"))
    ws=min((r["decision_time"] for r in rows),default=None); we=max((r["decision_time"] for r in rows),default=None)
    rep=dict(report_kind="FORWARD",label="FORWARD_PAPER (date prospective)",generated=time.strftime("%Y-%m-%d %H:%M:%S %Z"),spec_sha256=spec["spec_sha256"],model_hash=champ.model_hash,policy=champ.policy,window_start_ts=ws,window_end_ts=we,untouched_window=C.untouched_window_ok(ws) if ws else None,n_predictions=len(rows),n_labeled_ok=len(ok),n_selected=len(sel),n_baseline_selected=len(bsel),n_challengers_tried=n_tried,bonferroni_alpha=0.05/max(1,n_tried),gates=g,gate_info=dict(ci=info["ci"],stats=info["stats"],days_with_signals=info["days"],utc_days=info["all_days"]),all_forward_gates_pass=allp,
      POLICY_ENABLED=False,PROMOTION="manual only",READY_FOR_TINY_CAPITAL_REVIEW=("YES" if allp else "NO"),LIVE_TRADING_ENABLED="NO")
    F.atomic_write(os.path.join(ST,"evaluation_report_forward.json"),json.dumps(rep,indent=1,default=float)); print(json.dumps(dict(n=len(rows),ok=len(ok),sel=len(sel),gates=g,all_pass=allp),default=float)); print("EVALUATE_FORWARD_DONE")
def cmd_gates_forward(a):
    p=os.path.join(ST,"evaluation_report_forward.json")
    if not os.path.exists(p): print("GATES_FORWARD | niciun raport forward (ruleaza evaluate-forward)"); return
    r=json.load(open(p)); print(f"GATES_FORWARD | spec={r['spec_sha256'][:16]}.. n_pred={r['n_predictions']} n_sel={r['n_selected']} challengers_tried={r['n_challengers_tried']} alpha={r['bonferroni_alpha']:.4f}")
    for k,v in r["gates"].items(): print(f"  {k:45s} {v if isinstance(v,str) else ('PASS' if v else 'FAIL')}")
    print(f"  ALL_FORWARD_GATES_PASS = {r['all_forward_gates_pass']} | READY_FOR_TINY_CAPITAL_REVIEW = {r['READY_FOR_TINY_CAPITAL_REVIEW']} | POLICY_ENABLED = False | LIVE_TRADING_ENABLED = NO")
def cmd_verify_forward(a):
    import forward_lib as F
    res={}
    try: spec=F.load_spec(os.path.join(HERE,"forward_spec.json")); res["spec_sha256"]="OK"
    except SystemExit as e: res["spec_sha256"]=str(e)
    FJ=os.path.join(ST,"forward_prediction_journal.jsonl"); res["journal"]=C.Journal.verify(FJ) if os.path.exists(FJ) else "absent"
    try: st=F.ForwardState.load(os.path.join(ST,"forward_state.json")); res["state"]="OK"; res["files_done"]=len(st.files_done); res["files_modified"]=st.verify_files(a.source) if a.source else "not checked"
    except SystemExit as e: res["state"]=str(e)
    FO=os.path.join(ST,"forward_outcomes.jsonl"); res["outcomes"]=sum(1 for _ in open(FO)) if os.path.exists(FO) else 0
    ids=collections.Counter(json.loads(l)["prediction_id"] for l in open(FJ)) if os.path.exists(FJ) else {}; res["duplicate_predictions"]=sum(1 for c in ids.values() if c>1)
    print(json.dumps(res,default=str)); return res
def cmd_status(a):
    print("MODE = replay/shadow paper-only | LIVE_TRADING_ENABLED = NO | POLICY_ENABLED = False"); c=json.load(open(os.path.join(HERE,"champion.json"))); print("CHAMPION =",c["artifact_sha256"][:16],"immutable =",c["immutable"])
    if os.path.exists(J): print("JOURNAL =",C.Journal.verify(J)); 
    if os.path.exists(O): print("OUTCOMES =",sum(1 for _ in open(O)))
    if os.path.exists(os.path.join(ST,"evaluation_report.json")): r=json.load(open(os.path.join(ST,"evaluation_report.json"))); print("GATES =",r["promotion_gates"]); print("READY_FOR_TINY_CAPITAL_REVIEW =",r["READY_FOR_TINY_CAPITAL_REVIEW"])
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True); sub.add_parser("init"); r=sub.add_parser("run-cycle"); r.add_argument("--mode",required=True); r.add_argument("--source",required=True); r.add_argument("--cutoff",required=True); r.add_argument("--paper-only",action="store_true"); r.add_argument("--stop-file",default=os.path.join(ST,"STOP")); r.add_argument("--quiet",action="store_true")
    e=sub.add_parser("evaluate"); e.add_argument("--allow-rollback",action="store_true"); sub.add_parser("status"); sub.add_parser("verify-journal"); f=sub.add_parser("run-forward"); f.add_argument("--source",required=True); f.add_argument("--paper-only",action="store_true"); f.add_argument("--settle-s",type=int,default=120)
    lf=sub.add_parser("label-forward"); lf.add_argument("--source",required=True); sub.add_parser("evaluate-forward"); sub.add_parser("gates-forward"); vf=sub.add_parser("verify-forward"); vf.add_argument("--source",default=None); a=ap.parse_args()
    if a.cmd=="init": cmd_init(a)
    elif a.cmd=="run-cycle": cmd_run_cycle(a)
    elif a.cmd=="evaluate": cmd_evaluate(a)
    elif a.cmd=="status": cmd_status(a)
    elif a.cmd=="verify-journal": print(C.Journal.verify(J))
    elif a.cmd=="run-forward": cmd_run_forward(a)
    elif a.cmd=="label-forward": cmd_label_forward(a)
    elif a.cmd=="evaluate-forward": cmd_evaluate_forward(a)
    elif a.cmd=="gates-forward": cmd_gates_forward(a)
    elif a.cmd=="verify-forward": cmd_verify_forward(a)
if __name__=="__main__": main()
