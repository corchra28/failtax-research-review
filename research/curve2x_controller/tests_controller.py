"""Teste controller (fara date private): jurnal append-only cu lant de hash-uri (detectie alterare), Champion imuabil (hash gresit => refuz), labeler doar dupa maturizare,
Challenger doar pe outcome-uri maturizate inainte de cutoff-embargo, drift sever => WATCH/MODEL_DRIFT, promovare fara aprobare umana => refuz, porti minime."""
import os,sys,json,tempfile,subprocess,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import controller_lib as C
R={}
def check(n,c,d=""): R[n]=dict(pass_=bool(c),detail=str(d)[:200]); print("PASS" if c else "FAIL",n,d)
td=tempfile.mkdtemp(); jp=os.path.join(td,"j.jsonl"); J=C.Journal(jp); J.append(dict(prediction_id="a",x=1)); J.append(dict(prediction_id="b",x=2)); J.f.close(); ok=C.Journal.verify(jp); check("journal_hash_chain_ok",ok["ok"] and ok["records"]==2,ok)
lines=open(jp).read().split("\n"); r=json.loads(lines[0]); r["x"]=99; lines[0]=json.dumps(r); open(jp,"w").write("\n".join(lines)); check("journal_tamper_detected",not C.Journal.verify(jp)["ok"],C.Journal.verify(jp))
# champion imuabil: manifest cu hash gresit
mp=os.path.join(td,"champ.json"); json.dump(dict(artifact_path="research/curve2x_v3_reclaim/model_artifact.json",artifact_sha256="00"*32),open(mp,"w"))
try: C.Champion(mp); check("champion_hash_mismatch_refused",False,"a acceptat")
except SystemExit as e: check("champion_hash_mismatch_refused","CHAMPION_HASH_MISMATCH" in str(e),e)
# labeler: nu eticheteaza inainte de maturizare
jp2=os.path.join(td,"j2.jsonl"); J2=C.Journal(jp2); J2.append(dict(prediction_id="p1",mint="M",mint_hash="h",model_role="CHAMPION",dec_i=0,decision_time=1000,decision_slot=1)); J2.f.close(); op=os.path.join(td,"o.jsonl")
n1=C.label_matured(jp2,op,{},1000+C.HORIZON_S); n2=C.label_matured(jp2,op,{},1000+C.HORIZON_S+C.MATURITY_MARGIN_S+1); check("labeler_only_after_maturity",n1==0 and n2==1,(n1,n2))
# challenger: doar outcome-uri maturizate inainte de cutoff - embargo
rows=[dict(model_role="CHAMPION",label_quality="OK",decision_time=t,state=("TP_FIRST" if i%4==0 else "SL_FIRST"),realized_net_pnl=(0.2 if i%4==0 else -0.09),features={k:float(i%7) for k in C.FEATURE_SCHEMA}) for i,t in enumerate(range(0,200000,1000))]
cut=100000; art,info=C.train_challenger(rows,cut,C.FEATURE_SCHEMA,[0.0]*len(C.FEATURE_SCHEMA),"t"); last=max(r["decision_time"] for r in rows if r["decision_time"]+C.HORIZON_S+C.EMBARGO_S<=cut)
check("challenger_trained_only_before_cutoff_embargo",art is not None and info["n"]==sum(1 for r in rows if r["decision_time"]+C.HORIZON_S+C.EMBARGO_S<=cut) and art["trained_on"]["last_decision_time"]==C.utc(last),info)
check("challenger_policy_disabled",art is not None and art["policy_enabled"] is False and art["policy"] is None,"")
# drift sever => WATCH / MODEL_DRIFT
sc=dict(P_TP_FIRST=0.9,EV_NET=0.5); check("severe_drift_forces_watch",C.decide(sc,dict(p_tp_min=0.25),False,True)==("WATCH","MODEL_DRIFT"),C.decide(sc,dict(p_tp_min=0.25),False,True))
check("no_paper_candidate_ever",C.decide(sc,dict(p_tp_min=0.25),False,False)[0]=="WATCH" and C.decide(sc,dict(p_tp_min=0.25),True,False)[0]=="WATCH","actiunile posibile sunt doar WATCH/REJECT")
# promovare fara aprobare umana => refuz
r=subprocess.run([sys.executable,os.path.join(HERE,"promote.py"),"--human-approval-file",os.path.join(td,"none.json")],capture_output=True,text=True); check("promotion_refused_without_human",r.returncode!=0 and "REFUSED" in (r.stderr+r.stdout),(r.stderr+r.stdout).strip()[:80])
g,allp=C.promotion_gates(dict(selected_region=dict(N=10,forward_days=1),drift=dict(SEVERE=False)),dict(land5=0.01,cost125=0.01)); check("gates_fail_on_small_sample",not allp and g["FORWARD_CANDIDATES_ge_100"] is False and g["HUMAN_APPROVAL_REQUIRED"].startswith("PENDING"),g)
json.dump(dict(tests=R,all_pass=all(v["pass_"] for v in R.values())),open(os.path.join(HERE,"test_results.json"),"w"),indent=1); print("ALL_PASS" if all(v["pass_"] for v in R.values()) else "SOME_FAIL")
# registru + corectie multiple-testing + fereastra neatinsa + rollback (stare temporara)
os.environ["CURVE2X_CTRL_STATE"]=td; import importlib; C2=importlib.reload(C); C2.STATE=td
C2.register_attempt("CHALLENGER_TRAINED",dict(window_start_ts=100,window_end_ts=200)); C2.register_attempt("CHALLENGER_TRAINED",dict(window_start_ts=300,window_end_ts=400))
check("bonferroni_alpha_by_attempts",abs(C2.bonferroni_alpha()-0.025)<1e-12,C2.bonferroni_alpha()); check("untouched_window_rule",C2.untouched_window_ok(500) and not C2.untouched_window_ok(350),"")
check("rollback_condition_on_negative_lcb95",C2.rollback_check(dict(selected_region=dict(N=150,EV_LCB95=-0.01),drift=dict(SEVERE=False))) and not C2.rollback_check(dict(selected_region=dict(N=50,EV_LCB95=-0.01),drift=dict(SEVERE=False))),"")
check("rollback_noop_without_archive",C2.do_rollback("test") is False,"fara champion arhivat => niciun rollback")
g,info=C2.forward_gates([],[],[],2); check("forward_gates_fail_empty",not any(v is True for k,v in g.items() if k.startswith("MIN_")) and "PENDING" in g["HUMAN_APPROVAL_REQUIRED"],g["MULTIPLE_TESTING_CORRECTION"])
json.dump(dict(tests=R,all_pass=all(v["pass_"] for v in R.values())),open(os.path.join(HERE,"test_results.json"),"w"),indent=1); print("ALL_PASS" if all(v["pass_"] for v in R.values()) else "SOME_FAIL")
