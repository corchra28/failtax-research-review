"""CURVE2X V3 — REEVALUARE FARA REANTRENARE si fara cautare de prag: acelasi model_artifact (hash verificat), acelasi p_tp_min=0,25; etichete remediate (migrare doar in orizont,
limite de ordine in slotul de aterizare: primar = conservative; optimistic si midpoint raportate); porti; diferente fata de V3-original (original/results.json)."""
import os,sys,gzip,json,hashlib,collections,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L; import model_v3 as M3
D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(HERE,"derived_v3")); art=json.load(open(os.path.join(HERE,"model_artifact.json"))); mh=hashlib.sha256(open(os.path.join(HERE,"model_artifact.json"),"rb").read()).hexdigest()
ORIG=json.load(open(os.path.join(HERE,"original","results.json"))); ODM=json.load(open(os.path.join(HERE,"original","dataset_manifest.json"))); DM=json.load(open(os.path.join(HERE,"dataset_manifest.json")))
assert art["policy"]["p_tp_min"]==0.25 and ORIG["model_hash"]==mh, "artefactul sau pragul difera de original"
rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt")]; fl=art["features"]; fill=np.array(art["fill"]); pol=art["policy"]
def usable_b(r,key="bounds"): b=r["lab"][key]; return b.get("status")=="OK" and not b.get("unavailable") and not r["gap"]
def stats_b(sel,key,which):
    ok=[r for r in sel if usable_b(r,key)]
    if not ok: return dict(signals=len(sel),usable=0)
    v=np.array([r["lab"][key][which]["pnl"] for r in ok]); st=L.evstats(v,[r["mint"] for r in ok]); states=collections.Counter(r["lab"][key][which]["state"] for r in ok); rng=np.random.default_rng(20260905); bs=np.sort([v[rng.integers(0,len(v),len(v))].mean() for _ in range(4000)])
    pos=collections.defaultdict(float); [pos.__setitem__(r["hour"],pos[r["hour"]]+max(0.0,x)) for r,x in zip(ok,v)]; gp=sum(pos.values()) or 1e-12; hrs=collections.Counter(r["hour"] for r in ok)
    return dict(signals=len(sel),usable=len(ok),TP_FIRST_rate=states["TP_FIRST"]/len(ok),SL_FIRST_rate=states["SL_FIRST"]/len(ok),timeout_rate=states["TIMEOUT_OTHER"]/len(ok),**{k:st[k] for k in ("EV","median","PF","win_rate","EX_BEST_1PCT")},max_mint_share=st["max_group_share"],max_creator_share=L.evstats(v,[r["creator"] for r in ok])["max_group_share"],max_hour_share=float(max(pos.values())/gp),CI95=(float(bs[100]),float(bs[3899])),LCB90=float(bs[400]),max_signal_share_same_hour=max(hrs.values())/len(ok))
S={s:[r for r in rows if r["split"]==s] for s in ("TRAIN","CAL","VAL","CONF")}; EV={}; 
for seg in ("VAL","CONF","VAL+CONF"):
    rr=S["VAL"]+S["CONF"] if seg=="VAL+CONF" else S[seg]; rr=[r for r in rr if r["lab"]["bounds"].get("status")=="OK"]
    if not rr: EV[seg]={}; continue
    X,_=L.X_of(rr,fl,fill); sc=M3.score(rr,X,art["models"],fl); sel=[r for r,s in zip(rr,sc) if M3.decide(s,pol)[0]=="WATCH"]
    res=dict(conservative=stats_b(sel,"bounds","conservative"),midpoint=stats_b(sel,"bounds","midpoint"),optimistic=stats_b(sel,"bounds","optimistic"),land5_conservative=stats_b(sel,"bounds_land5","conservative"),cost125_conservative=stats_b(sel,"bounds_cost125","conservative"),legacy_after_all_trades=M3.stats(sel,"base"))
    us=[(r,s) for r,s in zip(rr,sc) if usable_b(r)]
    if us: res["selected_region_calibration"]=M3.region_cal(np.array([[s["p_tp"],s["p_sl"],s["p_to"]] for r,s in us if M3.decide(s,pol)[0]=="WATCH"]),np.array([[r["lab"]["bounds"]["conservative"]["state"]=="TP_FIRST",r["lab"]["bounds"]["conservative"]["state"]=="SL_FIRST",r["lab"]["bounds"]["conservative"]["state"]=="TIMEOUT_OTHER"] for r,s in us if M3.decide(s,pol)[0]=="WATCH"],float)) if any(M3.decide(s,pol)[0]=="WATCH" for r,s in us) else None
    EV[seg]=res
v,c_,a_=EV["VAL"].get("conservative",{}),EV["CONF"].get("conservative",{}),EV["VAL+CONF"].get("conservative",{}); A=EV["VAL+CONF"]; g={}
g["min_mints_val_conf_100"]=a_.get("usable",0)>=100; g["min_mints_conf_30"]=c_.get("usable",0)>=30; g["ev_combined_positive_conservative"]=(a_.get("EV") or -1)>0; g["ci95_lower_positive"]=((a_.get("CI95") or (-1,))[0])>0; g["pf_ge_1_30"]=(a_.get("PF") or 0)>=1.30
g["ev_positive_val_and_conf"]=(v.get("EV") or -1)>0 and (c_.get("EV") or -1)>0; g["ex_best_1pct_positive"]=(a_.get("EX_BEST_1PCT") or -1)>0; g["no_concentration_gt_20pct"]=all((a_.get(k) or 1)<=0.20 for k in ("max_mint_share","max_creator_share","max_hour_share"))
g["stress_land5_conservative_ev_positive"]=(A.get("land5_conservative",{}).get("EV") or -1)>0; g["stress_cost125_conservative_ev_positive"]=(A.get("cost125_conservative",{}).get("EV") or -1)>0; rc=A.get("selected_region_calibration") or {}; g["calibration_region_min_30"]=(rc.get("n") or 0)>=30; g["calibration_gap_le_8pp"]=(rc.get("gap_tp") is not None and rc["gap_tp"]<=0.08)
g["beats_state_headroom_baseline"]=ORIG["gates"].get("beats_state_headroom_baseline"); g["hour_diversity_ge_50pct"]=(a_.get("max_signal_share_same_hour") or 1)<=0.5; g["policy_feasible_on_cal"]=ORIG["policy_feasible_on_cal"]
verdict="HISTORICAL_PAPER_CANDIDATE_REQUIRES_FRESH_FORWARD" if all(x is True for x in g.values()) else "NO_VERIFIED_EDGE"
# reparari: randuri UNAVAILABLE in original vs remediat
unav_orig=ODM["status_base"].get("UNAVAILABLE",0); unav_new=DM["status_base"].get("UNAVAILABLE",0); repaired=unav_orig-unav_new
diff=dict(unavailable_original=unav_orig,unavailable_remediated=unav_new,repaired_by_horizon_fix=repaired,migrated_in_window_original=ODM["migrated"],migrated_in_window_remediated=DM["migrated"],splice_ok_original=ODM["splice_ok"],splice_ok_remediated=DM["splice_ok"],bounds_status=DM.get("bounds_status"),entry_positions_hist=DM.get("bounds_entry_positions_hist"),
    val_conf_original_base=ORIG["evaluation"]["VAL+CONF"]["base"],val_conf_remediated_conservative=a_,val_conf_remediated_midpoint=A.get("midpoint"),val_conf_remediated_optimistic=A.get("optimistic"),val_conf_remediated_legacy_after_all_trades=A.get("legacy_after_all_trades"),gates_original=ORIG["gates"],gates_remediated=g,verdict_original=ORIG["FINAL_VERDICT"],verdict_remediated=verdict,tests_original=len(json.load(open(os.path.join(HERE,"original","test_results.json")))["tests"]),tests_remediated=len(json.load(open(os.path.join(HERE,"test_results.json")))["tests"]))
R=dict(label="HISTORICAL_DEV_NOT_SEALED / V3_REMEDIATED (fara reantrenare, fara cautare de prag)",model_hash=mh,policy=pol,primary_estimate="conservative (worst-case al pozitiei tranzactiei in sloturile de intrare si iesire)",evaluation=EV,gates=g,FINAL_VERDICT=verdict,diff_vs_original=diff)
json.dump(R,open(os.path.join(HERE,"results_remediated.json"),"w"),indent=1,default=float); print(json.dumps(dict(verdict=verdict,repaired=repaired,unav=(unav_orig,unav_new),cons=a_,mid={k:A.get("midpoint",{}).get(k) for k in ("usable","EV","PF")},opt={k:A.get("optimistic",{}).get(k) for k in ("usable","EV","PF")},gates=g),default=float)[:2500])
