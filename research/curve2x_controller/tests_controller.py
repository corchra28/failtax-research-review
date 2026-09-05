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

# registru + corectie multiple-testing + fereastra neatinsa + rollback (stare temporara)
os.environ["CURVE2X_CTRL_STATE"]=td; import importlib; C2=importlib.reload(C); C2.STATE=td
C2.register_attempt("CHALLENGER_TRAINED",dict(window_start_ts=100,window_end_ts=200)); C2.register_attempt("CHALLENGER_TRAINED",dict(window_start_ts=300,window_end_ts=400))
check("bonferroni_alpha_by_attempts",abs(C2.bonferroni_alpha()-0.025)<1e-12,C2.bonferroni_alpha()); check("untouched_window_rule",C2.untouched_window_ok(500) and not C2.untouched_window_ok(350),"")
check("rollback_condition_on_negative_lcb95",C2.rollback_check(dict(selected_region=dict(N=150,EV_LCB95=-0.01),drift=dict(SEVERE=False))) and not C2.rollback_check(dict(selected_region=dict(N=50,EV_LCB95=-0.01),drift=dict(SEVERE=False))),"")
check("rollback_noop_without_archive",C2.do_rollback("test") is False,"fara champion arhivat => niciun rollback")
g,info=C2.forward_gates([],[],[],2); check("forward_gates_fail_empty",not any(v is True for k,v in g.items() if k.startswith("MIN_")) and "PENDING" in g["HUMAN_APPROVAL_REQUIRED"],g["MULTIPLE_TESTING_CORRECTION"])


# ---------------- integrare forward fara date private: 3 fisiere, restart intre ele, exact o predictie si un outcome ----------------
import gzip,shutil,subprocess,time
V=C.V; L=C.L; LAMP=L.LAMP; VS0=30*LAMP; VT0=1_073_000_000_000_000; RT0=793_100_000_000_000
def mk(steps,t0=1_800_000_000,slot0=1000):
    vs,vt,rs,rt=VS0,VT0,0,RT0; T=[]
    for dt,ds,sol,user in steps:
        ts=t0+dt; slot=slot0+ds
        if sol>0: tok,net=L.curve_buy(vs,vt,sol); vs+=net; vt-=tok; rs+=net; rt-=tok; T.append(dict(ts=ts,slot=slot,user=user,sol=sol,tok=tok,is_buy=True,rs=rs,rt=rt,vs=vs,vt=vt))
        else:
            want=-sol; h=vt*want//(vs-want) if vs>want else vt//10; g=vs-(vs*vt)//(vt+h); g=min(g,rs); vs-=g; vt+=h; rs-=g; rt+=h; T.append(dict(ts=ts,slot=slot,user=user,sol=g,tok=h,is_buy=False,rs=rs,rt=rt,vs=vs,vt=vt))
    return T
buys=lambda n,dt0,ds0,sol,u="w":[(dt0+i,ds0+2*i,sol,f"{u}{i}") for i in range(n)]
MINT="SYNTHETICMINTFORWARDTEST00000000000001TEST"; steps=buys(36,0,0,1*LAMP)+[(40+i,80+2*i,-1*LAMP,f"s{i}") for i in range(6)]+buys(6,50,100,1*LAMP,"r")+[(60+i*30,130+i*75,(0.05*LAMP if i%2 else -0.05*LAMP),f"m{i}") for i in range(40)]
T=mk(steps); t0=T[0]["ts"]-5
def rec(t,slot,events): return json.dumps(dict(t=t,slot=slot,sig="synthetic",src="pump",events=events),separators=(",",":"))
lines=[rec(t0,T[0]["slot"]-5,[dict(ev="CreateEvent",mint=MINT,user="creator1",name="x",symbol="x",uri="x",bonding_curve="bc")])]
for x in T: lines.append(rec(x["ts"],x["slot"],[dict(ev="TradeEvent",mint=MINT,sol=x["sol"],tok=x["tok"],is_buy=x["is_buy"],user=x["user"],ts=x["ts"],vsol=x["vs"],vtok=x["vt"],rsol=x["rs"],rtok=x["rt"])]))
# umplere de context: CreateEvent-uri de alte mint-uri la fiecare 30 s ca ceasul sa avanseze dincolo de maturitate (960 s dupa decizie)
last=T[-1]["ts"]
for i in range(1,80): lines.append(rec(last+30*i,T[-1]["slot"]+75*i,[dict(ev="CreateEvent",mint=f"Filler{i}mint",user="c",name="f",symbol="f",uri="f",bonding_curve="b")]))
fwd=os.path.join(td,"fwd"); os.makedirs(fwd); cut1=1+36; cut2=1+36+6+6
for name,chunk in (("events_2026091000.jsonl.gz",lines[:cut1]),("events_2026091001.jsonl.gz",lines[cut1:cut2]),("events_2026091002.jsonl.gz",lines[cut2:])):
    with gzip.open(os.path.join(fwd,name),"wt") as f: f.write("\n".join(chunk)+"\n")
    os.utime(os.path.join(fwd,name),(time.time()-1000,time.time()-1000))
ST2=os.path.join(td,"state2"); os.makedirs(ST2); env=dict(os.environ,CURVE2X_CTRL_STATE=ST2); PY=sys.executable; CTRL=os.path.join(HERE,"controller.py")
if not os.path.exists(os.path.join(ST2,"reference_stats.json")):
    import shutil as _sh; src=os.path.join(HERE,"state","reference_stats.json")
    if os.path.exists(src): _sh.copy(src,os.path.join(ST2,"reference_stats.json"))
    else:
        # referinta sintetica (fara date private): mu/sd/hist din trasaturile unei singure decizii sintetice
        import numpy as np; E=C.Stream(); E.create(t0,T[0]["slot"]-5,0,MINT,"creator1")
        for i,x in enumerate(T): E.trade(x["ts"],x["slot"],i+1,0,MINT,x["user"],x["sol"],x["tok"],1 if x["is_buy"] else 0,x["rs"],x["rt"],x["vs"],x["vt"])
        f0=E.decisions[0]["f"]; feats=json.load(open(os.path.join(HERE,"forward_spec.json")))["feature_schema"]; json.dump(dict(features=feats,mu=[float(f0.get(k) or 0) for k in feats],sd=[1.0]*len(feats),hist={k:dict(edges=[-1e18,0,1e18],frac=[0.5,0.5]) for k in feats},tp_rate=0.25,n=1),open(os.path.join(ST2,"reference_stats.json"),"w"))
outs=[]
for i in range(3):
    r=subprocess.run([PY,CTRL,"run-forward","--source",fwd,"--paper-only","--settle-s","0"],capture_output=True,text=True,env=env); outs.append(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
    # simulam sosirea fisierului urmator: fisierele exista deja; run-forward proceseaza doar fisierele noi => la a doua/a treia rulare nu mai exista fisiere noi. Ca sa testam restart-ul intre fisiere, ascundem fisierele viitoare:
    break
# varianta reala de test cross-file: ascundem fisierele 2 si 3, rulam, apoi le expunem pe rand (restart de proces intre ele)
for f in os.listdir(fwd): os.remove(os.path.join(fwd,f))
shutil.rmtree(ST2); os.makedirs(ST2); import shutil as _sh
if os.path.exists(os.path.join(HERE,"state","reference_stats.json")): _sh.copy(os.path.join(HERE,"state","reference_stats.json"),os.path.join(ST2,"reference_stats.json"))
else: json.dump(dict(features=json.load(open(os.path.join(HERE,"forward_spec.json")))["feature_schema"],mu=[0.0]*41,sd=[1.0]*41,hist={},tp_rate=0.25,n=1),open(os.path.join(ST2,"reference_stats.json"),"w"))
logs=[]
for name,chunk in (("events_2026091000.jsonl.gz",lines[:cut1]),("events_2026091001.jsonl.gz",lines[cut1:cut2]),("events_2026091002.jsonl.gz",lines[cut2:])):
    with gzip.open(os.path.join(fwd,name),"wt") as f: f.write("\n".join(chunk)+"\n")
    os.utime(os.path.join(fwd,name),(time.time()-1000,time.time()-1000)); r=subprocess.run([PY,CTRL,"run-forward","--source",fwd,"--paper-only","--settle-s","0"],capture_output=True,text=True,env=env); logs.append((r.returncode,(r.stdout+r.stderr).strip().splitlines()[-1][:200] if (r.stdout+r.stderr).strip() else ""))
FJ=os.path.join(ST2,"forward_prediction_journal.jsonl"); npred=sum(1 for _ in open(FJ)) if os.path.exists(FJ) else 0
check("cross_file_state_persistence_one_prediction",npred==1 and all(rc==0 for rc,_ in logs),dict(npred=npred,logs=logs))
r=subprocess.run([PY,CTRL,"label-forward","--source",fwd],capture_output=True,text=True,env=env); FO=os.path.join(ST2,"forward_outcomes.jsonl"); outc=[json.loads(l) for l in open(FO)] if os.path.exists(FO) else []
check("label_forward_one_matured_outcome",len(outc)==1 and outc[0].get("state") in ("TP_FIRST","SL_FIRST","TIMEOUT_OTHER") and outc[0].get("label_quality") in ("OK","GAP") and outc[0].get("source")=="FORWARD_FILES_ONLY",[(o.get("state"),o.get("label_quality"),o.get("splice_quality")) for o in outc] or (r.stdout+r.stderr)[-300:])
r=subprocess.run([PY,CTRL,"run-forward","--source",fwd,"--paper-only","--settle-s","0"],capture_output=True,text=True,env=env); npred2=sum(1 for _ in open(FJ)); check("restart_no_duplicates",npred2==1 and "niciun fisier nou" in r.stdout,r.stdout.strip().splitlines()[-1][:120])
# fisier procesat modificat => refuz
p1=os.path.join(fwd,"events_2026091000.jsonl.gz"); 
with gzip.open(p1,"at") as f: f.write(rec(t0+1,T[0]["slot"]-4,[dict(ev="CreateEvent",mint="Tamper",user="c",name="f",symbol="f",uri="f",bonding_curve="b")])+"\n")
r=subprocess.run([PY,CTRL,"run-forward","--source",fwd,"--paper-only","--settle-s","0"],capture_output=True,text=True,env=env); check("modified_processed_file_refused",r.returncode!=0 and "PROCESSED_FILE_MODIFIED" in (r.stdout+r.stderr),(r.stdout+r.stderr).strip()[-120:])
# jurnal alterat => append refuzat
lines_j=open(FJ).read().split("\n"); jr0=json.loads(lines_j[0]); jr0["P_TP_FIRST"]=0.99; lines_j[0]=json.dumps(jr0); open(FJ,"w").write("\n".join(lines_j))
try: C.Journal(FJ); check("tampered_journal_refuses_append",False,"a acceptat")
except SystemExit as e: check("tampered_journal_refuses_append","JOURNAL_CHAIN_BROKEN" in str(e),str(e)[:80])
# spec sha nepotrivit => refuz
import forward_lib as F; sp=json.load(open(os.path.join(HERE,"forward_spec.json"))); sp["maturity_s"]=961; bad=os.path.join(td,"spec_bad.json"); json.dump(sp,open(bad,"w"))
try: F.load_spec(bad); check("spec_sha_mismatch_refused",False,"a acceptat")
except SystemExit as e: check("spec_sha_mismatch_refused","FORWARD_SPEC_SHA_MISMATCH" in str(e),"")
# evaluate-forward + gates-forward + verify-forward pe starea sintetica (jurnal refacut curat)
open(FJ,"w").write("\n".join(lines_j[:0])); shutil.rmtree(ST2); os.makedirs(ST2)
if os.path.exists(os.path.join(HERE,"state","reference_stats.json")): _sh.copy(os.path.join(HERE,"state","reference_stats.json"),os.path.join(ST2,"reference_stats.json"))
else: json.dump(dict(features=json.load(open(os.path.join(HERE,"forward_spec.json")))["feature_schema"],mu=[0.0]*41,sd=[1.0]*41,hist={},tp_rate=0.25,n=1),open(os.path.join(ST2,"reference_stats.json"),"w"))
for f in os.listdir(fwd): os.remove(os.path.join(fwd,f))
for name,chunk in (("events_2026091000.jsonl.gz",lines[:cut1]),("events_2026091001.jsonl.gz",lines[cut1:cut2]),("events_2026091002.jsonl.gz",lines[cut2:])):
    with gzip.open(os.path.join(fwd,name),"wt") as f: f.write("\n".join(chunk)+"\n")
    os.utime(os.path.join(fwd,name),(time.time()-1000,time.time()-1000))
subprocess.run([PY,CTRL,"run-forward","--source",fwd,"--paper-only","--settle-s","0"],capture_output=True,text=True,env=env); subprocess.run([PY,CTRL,"label-forward","--source",fwd],capture_output=True,text=True,env=env)
r=subprocess.run([PY,CTRL,"evaluate-forward"],capture_output=True,text=True,env=env); rep=json.load(open(os.path.join(ST2,"evaluation_report_forward.json"))) if os.path.exists(os.path.join(ST2,"evaluation_report_forward.json")) else {}
check("evaluate_forward_uses_frozen_gates",rep.get("report_kind")=="FORWARD" and rep.get("all_forward_gates_pass") is False and set(k for k in rep.get("gates",{}) if k.startswith("MIN_"))=={"MIN_SIGNALS_300","MIN_UTC_DAYS_7","MIN_DAYS_WITH_SIGNALS_5"} and rep.get("spec_sha256")==sp0 if (sp0:=json.load(open(os.path.join(HERE,"forward_spec.json")))["spec_sha256"]) else False,(r.stdout+r.stderr).strip()[-200:])
r=subprocess.run([PY,CTRL,"gates-forward"],capture_output=True,text=True,env=env); check("gates_forward_prints",r.returncode==0 and "ALL_FORWARD_GATES_PASS = False" in r.stdout,"")
r=subprocess.run([PY,CTRL,"verify-forward","--source",fwd],capture_output=True,text=True,env=env); vr=json.loads(r.stdout.strip().splitlines()[-1]); check("verify_forward_ok",vr.get("spec_sha256")=="OK" and vr.get("state")=="OK" and vr.get("duplicate_predictions")==0 and vr.get("files_modified")==[],vr)
# promote: raport replay respins; raport forward cu porti picate respins
apf=os.path.join(td,"appr.json"); json.dump(dict(evaluation_report_sha256="x",confirmation="I approve promoting the challenger to champion for PAPER/SHADOW use only"),open(apf,"w"))
rp=os.path.join(ST2,"evaluation_report.json"); json.dump(dict(report_kind="REPLAY",label="REPLAY_DEMONSTRATION",all_statistical_gates_pass=True),open(rp,"w"))
r=subprocess.run([PY,os.path.join(HERE,"promote.py"),"--report",rp,"--human-approval-file",apf,"--i-am-a-human"],capture_output=True,text=True,env=env); check("promote_rejects_replay_report",r.returncode!=0 and "REFUSED" in r.stdout+r.stderr,(r.stdout+r.stderr).strip()[:100])
r=subprocess.run([PY,os.path.join(HERE,"promote.py"),"--human-approval-file",apf,"--i-am-a-human"],capture_output=True,text=True,env=env); check("promote_rejects_forward_report_with_failed_gates",r.returncode!=0 and "REFUSED" in r.stdout+r.stderr and ("porti" in r.stdout+r.stderr or "neatinsa" in r.stdout+r.stderr or "spec" in r.stdout+r.stderr),(r.stdout+r.stderr).strip()[:120])
OUTD=os.environ.get("CURVE2X_TEST_OUT",HERE); os.makedirs(OUTD,exist_ok=True); json.dump(dict(tests=R,n_tests=len(R),all_pass=all(v["pass_"] for v in R.values())),open(os.path.join(OUTD,"test_results.json"),"w"),indent=1); print("ALL_PASS" if all(v["pass_"] for v in R.values()) else "SOME_FAIL")
