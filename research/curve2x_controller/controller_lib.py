"""PROSPECTIVE_SELF_LEARNING_CONTROLLER pentru CURVE2X — paper/shadow only. Componente: Champion imuabil (hash fixat), jurnal de predictii append-only cu lant de hash-uri,
labeler separat (doar dupa maturizarea orizontului), evaluare prequentiala, un singur Challenger per ciclu antrenat doar pe outcome-uri maturizate inainte de cutoff (embargo),
monitoare de drift, porti de promovare cu aprobare umana obligatorie. Zero RPC, zero live. Reutilizeaza read-only v3_lib / watcher_v3 (nu le modifica)."""
import os,sys,json,time,hashlib,math,collections,datetime,gzip,uuid,glob
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE)); V3=os.path.join(ROOT,"research","curve2x_v3_reclaim")
sys.path.insert(0,V3); import v3_lib as V; L=V.L; from watcher_v3 import Stream
import numpy as np
STATE=os.environ.get("CURVE2X_CTRL_STATE",os.path.join(HERE,"state")); HORIZON_S=V.H_PRIMARY; MATURITY_MARGIN_S=60; EMBARGO_S=1800; FEATURE_SCHEMA=V.FEATS
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
def utc(ts): return datetime.datetime.fromtimestamp(ts,datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
# ---------------- Champion imuabil ----------------
class Champion:
    """artefact fixat prin hash in champion.json; orice nepotrivire => refuz. Nu exista cale de scriere."""
    def __init__(self,manifest=os.path.join(HERE,"champion.json")):
        c=json.load(open(manifest)); raw=open(c["artifact_path"] if os.path.isabs(c["artifact_path"]) else os.path.join(ROOT,c["artifact_path"]),"rb").read(); h=sha_bytes(raw)
        if h!=c["artifact_sha256"]: raise SystemExit(f"CHAMPION_HASH_MISMATCH {h[:16]} != {c['artifact_sha256'][:16]}")
        self.art=json.loads(raw); self.model_hash=h; self.role="CHAMPION"; self.feature_schema_hash=sha_bytes(json.dumps(self.art["features"]).encode()); self.policy=self.art["policy"]
        if self.art.get("policy_enabled") is not False: raise SystemExit("CHAMPION_POLICY_MUST_BE_DISABLED")
class Challenger:
    def __init__(self,art,model_hash): self.art=art; self.model_hash=model_hash; self.role="CHALLENGER"; self.feature_schema_hash=sha_bytes(json.dumps(art["features"]).encode()); self.policy=art["policy"]
def score_with(model,row,ref):
    """probabilitati, EV, LCB90, suport local, OOD; NU decide nimic despre live."""
    art=model.art; M=art["models"]; fl=art["features"]; X,_=L.X_of([row],fl,np.array(art["fill"])); P=L.apply_cal(M["cal"],L.predict(M["clf"],X)); ev=float(L.pred_gbm_reg(M["reg"],X)[0]); rs=M["regstats"]
    dec=int(np.clip(np.searchsorted(rs["edges"],ev,side="right"),0,len(rs["sd"])-1)); n=max(1,rs["n"][dec]); p=float(P[0,0]); z=(X[0]-np.array(ref["mu"]))/np.array(ref["sd"]); ood=float(np.mean(np.abs(z)>3.0))
    return dict(P_TP_FIRST=p,P_SL_FIRST=float(P[0,1]),P_TIMEOUT=float(P[0,2]),P_2X_LCB90=max(0.0,p-1.2816*math.sqrt(p*(1-p)/n)),EV_NET=ev,EV_NET_LCB90=ev-1.2816*rs["sd"][dec]/math.sqrt(n),local_support=int(n),OOD_score=ood)
def regime_of(row,ctx):
    h=int((row["ts"]%86400)//3600); return dict(hour_bucket=f"H{h//6*6:02d}-{h//6*6+5:02d}",progress_band=("P40-55" if row["f"]["progress"]<0.55 else "P55-70" if row["f"]["progress"]<0.70 else "P70+"),launch_rate_bucket=("LOW" if ctx.get("launches_10m",0)<30 else "MID" if ctx.get("launches_10m",0)<80 else "HIGH"),mayhem="UNKNOWN")
def decide(sc,policy,policy_enabled,drift_severe):
    if drift_severe: return "WATCH","MODEL_DRIFT"
    if sc["P_TP_FIRST"]>=policy["p_tp_min"] and sc["EV_NET"]>0: return ("WATCH","ELIGIBLE_POLICY_DISABLED") if not policy_enabled else ("WATCH","ELIGIBLE_NO_LIVE_PATH")
    return "REJECT",("P_TP_BELOW_MIN" if sc["P_TP_FIRST"]<policy["p_tp_min"] else "EV_NOT_POSITIVE")
# ---------------- jurnal append-only cu lant de hash-uri ----------------
class Journal:
    def __init__(self,path):
        self.path=path; self.prev="0"*64; self.n=0
        if os.path.exists(path):
            for l in open(path): r=json.loads(l); self.prev=r["record_hash"]; self.n+=1
        self.f=open(path,"a")
    def append(self,rec):
        rec=dict(rec); rec["prev_hash"]=self.prev; body=json.dumps({k:v for k,v in rec.items() if k!="record_hash"},sort_keys=True,default=float); rec["record_hash"]=sha_bytes(body.encode()); self.f.write(json.dumps(rec,default=float)+"\n"); self.f.flush(); self.prev=rec["record_hash"]; self.n+=1; return rec["record_hash"]
    @staticmethod
    def verify(path):
        prev="0"*64; n=0
        for l in open(path):
            r=json.loads(l); h=r.pop("record_hash"); 
            if r.get("prev_hash")!=prev or sha_bytes(json.dumps(r,sort_keys=True,default=float).encode())!=h: return dict(ok=False,at=n)
            prev=h; n+=1
        return dict(ok=True,records=n)
# ---------------- labeler separat (doar dupa maturizare) ----------------
def label_matured(journal_path,outcomes_path,curves_index,clock_ts):
    """eticheteaza predictiile cu decision_time + orizont + marja <= clock_ts si neetichetate inca; foloseste exclusiv trade-uri cu ts <= decision_time + orizont (simulate_v3 taie la orizont)."""
    done=set()
    if os.path.exists(outcomes_path):
        for l in open(outcomes_path): done.add(json.loads(l)["prediction_id"])
    out=open(outcomes_path,"a"); n=0
    for l in open(journal_path):
        p=json.loads(l)
        if p["prediction_id"] in done or p["decision_time"]+HORIZON_S+MATURITY_MARGIN_S>clock_ts: continue
        rec=curves_index.get(p["mint"])
        if rec is None: o=dict(state=None,label_quality="NO_RECORD"); 
        else:
            pool=L.pool_prepare(rec.get("pool")) if rec.get("pool") else None; s=V.simulate_v3(rec,p["dec_i"],p["decision_time"],pool=pool); s5=V.simulate_v3(rec,p["dec_i"],p["decision_time"],pool=pool,land=V.LAND_STRESS); sc=V.simulate_v3(rec,p["dec_i"],p["decision_time"],pool=pool,cost_mult=V.COST_STRESS)
            if s.get("status")!="OK": o=dict(state=None,label_quality=s.get("status"))
            else:
                r=s["15M"]; o=dict(state=r["state"],exit_slot=(None if r["t_exit"] is None else p["decision_slot"]+3+int(round(r["t_exit"]/0.4))),execution_venue=r["venue"],realized_net_pnl=r["pnl"],realized_net_pnl_land5=(s5["15M"]["pnl"] if s5.get("status")=="OK" else None),realized_net_pnl_cost125=(sc["15M"]["pnl"] if sc.get("status")=="OK" else None),label_quality=("GAP" if p.get("gap_known") else ("UNAVAILABLE" if r["state"] is None else "OK")),splice_quality=r["label_kind"])
        out.write(json.dumps(dict(prediction_id=p["prediction_id"],mint_hash=p["mint_hash"],model_role=p["model_role"],labeled_at_clock=clock_ts,**o),default=float)+"\n"); n+=1
    out.close(); return n
def load_curves_index(path,mints):
    idx={}
    with gzip.open(path,"rt") as f:
        for line in f:
            m=line[9:60].split('"')[0]
            if m in mints: idx[m]=json.loads(line)
    return idx
# ---------------- evaluare prequentiala + monitoare ----------------
def join(journal_path,outcomes_path):
    O={}
    if os.path.exists(outcomes_path):
        for l in open(outcomes_path): o=json.loads(l); O[o["prediction_id"]]=o
    rows=[]
    for l in open(journal_path):
        p=json.loads(l); o=O.get(p["prediction_id"])
        if o: rows.append(dict(p,**{k:v for k,v in o.items() if k not in ("prediction_id","mint_hash","model_role")}))
    return rows
def evstats(v):
    v=np.asarray(v,float)
    if len(v)==0: return None
    w=v[v>0]; l=v[v<=0]; srt=np.sort(v)[::-1]; n=len(v); return dict(N=n,EV=float(v.mean()),median=float(np.median(v)),PF=float(w.sum()/abs(l.sum())) if len(l) and l.sum()<0 else (float("inf") if len(w) else 0.0),win_rate=float((v>0).mean()),EX_BEST_1PCT=float(srt[max(1,int(math.ceil(n*0.01))):].mean()) if n>1 else float(v.mean()))
def prequential(rows,policy,ref):
    """metrici cumulate in ordinea deciziilor; calibrare globala si in regiunea selectata; rate TP/SL; per regim; concentrare; drift."""
    ok=[r for r in rows if r.get("state") in ("TP_FIRST","SL_FIRST","TIMEOUT_OTHER") and r.get("label_quality")=="OK"]; res=dict(n_predictions=len(rows),n_labeled_ok=len(ok),n_unusable=len(rows)-len(ok))
    if not ok: return res
    P=np.array([[r["P_TP_FIRST"],r["P_SL_FIRST"],r["P_TIMEOUT"]] for r in ok]); Y=np.array([[r["state"]=="TP_FIRST",r["state"]=="SL_FIRST",r["state"]=="TIMEOUT_OTHER"] for r in ok],float)
    res["log_loss"]=L.log_loss(P,Y); res["brier"]=L.brier_mc(P,Y); res["ece_tp_global"]=L.ece_bin(P[:,0],Y[:,0]); res["tp_rate"]=float(Y[:,0].mean()); res["sl_rate"]=float(Y[:,1].mean()); res["reliability_tp"]=L.reliability(P[:,0],Y[:,0])
    sel=[r for r in ok if r["action"]=="WATCH" and r["reason"] in ("ELIGIBLE_POLICY_DISABLED","ELIGIBLE_NO_LIVE_PATH")]; res["selected_region"]=dict(n=len(sel))
    if sel:
        Ps=np.array([r["P_TP_FIRST"] for r in sel]); Ys=np.array([r["state"]=="TP_FIRST" for r in sel],float); v=np.array([r["realized_net_pnl"] for r in sel]); st=evstats(v); rng=np.random.default_rng(7); bs=np.sort([v[rng.integers(0,len(v),len(v))].mean() for _ in range(2000)])
        pos=collections.defaultdict(float); [pos.__setitem__(r["mint_hash"],pos[r["mint_hash"]]+max(0.0,r["realized_net_pnl"])) for r in sel]; hp=collections.defaultdict(float); [hp.__setitem__(r["regime"]["hour_bucket"],hp[r["regime"]["hour_bucket"]]+max(0.0,r["realized_net_pnl"])) for r in sel]; gp=sum(pos.values()) or 1e-12
        days=collections.defaultdict(list); [days[utc(r["decision_time"])[:10]].append(r["realized_net_pnl"]) for r in sel]
        res["selected_region"].update(calibration_gap_tp=float(abs(Ps.mean()-Ys.mean())),pred_tp=float(Ps.mean()),obs_tp=float(Ys.mean()),**st,EV_LCB95=float(bs[int(0.05*len(bs))]),CI95=(float(bs[int(0.025*len(bs))]),float(bs[int(0.975*len(bs))-1])),max_concentration=float(max(max(pos.values()),max(hp.values()))/gp),by_day={d:dict(n=len(v_),EV=float(np.mean(v_))) for d,v_ in days.items()},positive_days=sum(1 for v_ in days.values() if np.mean(v_)>0),forward_days=len(days))
    reg=collections.defaultdict(list)
    for r in ok: reg[(r["regime"]["hour_bucket"],r["regime"]["progress_band"])].append(r)
    res["per_regime"]={f"{k[0]}|{k[1]}":dict(n=len(v),tp_rate=float(np.mean([x["state"]=="TP_FIRST" for x in v])),log_loss=L.log_loss(np.array([[x["P_TP_FIRST"],x["P_SL_FIRST"],x["P_TIMEOUT"]] for x in v]),np.array([[x["state"]=="TP_FIRST",x["state"]=="SL_FIRST",x["state"]=="TIMEOUT_OTHER"] for x in v],float))) for k,v in reg.items()}
    res["mayhem_separate"]=dict(note="modul Mayhem nu este observabil in CreateEvent-urile locale; toate deciziile sunt in bucket-ul UNKNOWN",UNKNOWN=dict(n=len(ok),tp_rate=res["tp_rate"]))
    res["drift"]=drift_report(rows,ok,ref); return res
def psi(ref_edges,ref_frac,x):
    if len(x)<20: return None
    cnt=np.histogram(x,bins=ref_edges)[0].astype(float); frac=(cnt+0.5)/(cnt.sum()+0.5*len(cnt)); rf=(np.array(ref_frac)+0.5/len(cnt)); rf=rf/rf.sum(); return float(np.sum((frac-rf)*np.log(frac/rf)))
def drift_report(rows,ok,ref):
    F=collections.defaultdict(list); [F[k].append(r["features"][k]) for r in rows for k in ref["features"] if r["features"].get(k) is not None]
    ps={k:psi(ref["hist"][k]["edges"],ref["hist"][k]["frac"],np.array(F[k])) for k in ref["features"] if F[k]}; hi=[k for k,v in ps.items() if v is not None and v>0.25]
    lab=None
    if ok:
        tp=np.mean([r["state"]=="TP_FIRST" for r in ok]); p0=ref["tp_rate"]; z=(tp-p0)/math.sqrt(p0*(1-p0)/len(ok)); lab=dict(tp_rate=float(tp),ref_tp_rate=p0,z=float(z),n=len(ok))
    ood=[r["OOD_score"] for r in rows]; severe=(len(hi)>=3) or (lab is not None and abs(lab["z"])>3 and lab["n"]>=50) or (len(ood)>=50 and float(np.mean(np.array(ood)>0.25))>0.30)
    return dict(feature_psi=ps,features_psi_gt_025=hi,label_drift=lab,ood_share_gt_025=float(np.mean(np.array(ood)>0.25)) if ood else None,SEVERE=bool(severe))
def reference_stats(train_rows,features):
    mu=[];sd=[];hist={}
    Xa=np.array([[r["f"].get(k) if r["f"].get(k) is not None else np.nan for k in features] for r in train_rows],float); Xa=np.sign(Xa)*np.log1p(np.abs(Xa)); med=np.nanmedian(Xa,0); Xa=np.where(np.isnan(Xa),med,Xa)
    for j,k in enumerate(features):
        col=Xa[:,j]; mu.append(float(col.mean())); sd.append(float(col.std()+1e-9)); raw=np.array([r["f"][k] for r in train_rows if r["f"].get(k) is not None],float); e=np.unique(np.quantile(raw,np.linspace(0,1,11))); e[0]=-np.inf; e[-1]=np.inf; c=np.histogram(raw,bins=e)[0]; hist[k]=dict(edges=e.tolist(),frac=(c/c.sum()).tolist())
    tp=float(np.mean([r["lab"]["base"]["15M"]["state"]=="TP_FIRST" for r in train_rows if r["lab"]["base"].get("status")=="OK" and r["lab"]["base"]["15M"]["state"]]))
    return dict(features=features,mu=mu,sd=sd,hist=hist,tp_rate=tp,n=len(train_rows))
# ---------------- Challenger: un singur model per ciclu, doar pe outcome-uri maturizate inainte de cutoff ----------------
def train_challenger(rows_joined,cutoff_ts,features,fill,cycle_id):
    """rows_joined: jurnal+outcome (champion). Foloseste doar predictii cu decision_time + orizont + embargo <= cutoff si outcome OK. Nu schimba tinta, pragurile, trasaturile."""
    tr=[r for r in rows_joined if r["model_role"]=="CHAMPION" and r.get("label_quality")=="OK" and r["decision_time"]+HORIZON_S+EMBARGO_S<=cutoff_ts]
    if len(tr)<80: return None,dict(reason="INSUFFICIENT_MATURED_OUTCOMES",n=len(tr))
    X,_=L.X_of([dict(f=r["features"]) for r in tr],features,np.array(fill)); Y=np.array([[r["state"]=="TP_FIRST",r["state"]=="SL_FIRST",r["state"]=="TIMEOUT_OTHER"] for r in tr],float); y=np.array([r["realized_net_pnl"] for r in tr])
    clf=L.fit_mlogit(X,Y); cal=dict(a=[1.0,1.0,1.0],b=[0.0,0.0,0.0]); reg=L.fit_gbm_reg(X,y); p=L.pred_gbm_reg(reg,X); edges=np.quantile(p,np.linspace(0,1,6)[1:-1]).tolist(); dec=np.clip(np.searchsorted(edges,p,side="right"),0,4)
    rs=dict(edges=edges,sd=[float((p[dec==d]-y[dec==d]).std()) if (dec==d).sum()>=5 else float((p-y).std()) for d in range(5)],n=[int((dec==d).sum()) for d in range(5)])
    art=dict(label="CHALLENGER_SHADOW",cycle_id=cycle_id,trained_on=dict(n=len(tr),cutoff=utc(cutoff_ts),embargo_s=EMBARGO_S,last_decision_time=utc(max(r["decision_time"] for r in tr))),model_kind="A",features=features,fill=list(fill),policy=None,policy_enabled=False,models=dict(clf=clf,cal=cal,reg=reg,regstats=rs,drv=dict(W=clf["W"],mu=clf["mu"],sd=clf["sd"])))
    s=json.dumps(art,sort_keys=True,separators=(",",":"),default=float); return json.loads(s),dict(n=len(tr),sha256=sha_bytes(s.encode()))
GATES=dict(FORWARD_CANDIDATES=100,FORWARD_DAYS=3,CALIBRATION_GAP_SELECTED_REGION=0.05,EV_NET_LCB95=0.0,PF=1.30,EX_BEST_1PCT_EV=0.0,POSITIVE_DAYS=2,MAX_CONCENTRATION=0.20,STRESS_5_SLOT_EV=0.0,STRESS_COST_125_EV=0.0)
def promotion_gates(ev_ch,stress):
    s=ev_ch.get("selected_region") or {}; d=ev_ch.get("drift") or {}; g={}
    g["FORWARD_CANDIDATES_ge_100"]=(s.get("N") or 0)>=100; g["FORWARD_DAYS_ge_3"]=(s.get("forward_days") or 0)>=3; g["CALIBRATION_GAP_SELECTED_REGION_le_0.05"]=(s.get("calibration_gap_tp") is not None and s["calibration_gap_tp"]<=0.05)
    g["EV_NET_LCB95_gt_0"]=(s.get("EV_LCB95") or -1)>0; g["PF_ge_1.30"]=(s.get("PF") or 0)>=1.30; g["EX_BEST_1PCT_EV_gt_0"]=(s.get("EX_BEST_1PCT") or -1)>0; g["POSITIVE_DAYS_ge_2"]=(s.get("positive_days") or 0)>=2; g["MAX_CONCENTRATION_le_0.20"]=(s.get("max_concentration") or 1)<=0.20
    g["STRESS_5_SLOT_EV_gt_0"]=(stress.get("land5") or -1)>0; g["STRESS_COST_125_EV_gt_0"]=(stress.get("cost125") or -1)>0; g["OOD_AND_DRIFT_PASS"]=not d.get("SEVERE",True); g["HUMAN_APPROVAL_REQUIRED"]="PENDING (nicio promovare automata)"
    allstat=all(v is True for k,v in g.items() if k!="HUMAN_APPROVAL_REQUIRED"); return g,allstat
# ---------------- registru global al incercarilor, corectie multiple-testing, rollback automat, ferestre prospective neatinse ----------------
def registry_path(): return os.path.join(STATE,"attempts_registry.jsonl")
def register_attempt(kind,payload):
    """append-only: fiecare challenger antrenat / evaluare de promovare / rollback. Corectia multiple-testing foloseste numarul total de challengere incercate."""
    rec=dict(attempt_id=str(uuid.uuid4()),kind=kind,at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),**payload); open(registry_path(),"a").write(json.dumps(rec,default=float)+"\n"); return rec["attempt_id"]
def attempts():
    return [json.loads(l) for l in open(registry_path())] if os.path.exists(registry_path()) else []
def n_challengers_tried(): return sum(1 for a in attempts() if a["kind"]=="CHALLENGER_TRAINED")
def bonferroni_alpha(alpha=0.05): return alpha/max(1,n_challengers_tried())
def untouched_window_ok(window_start_ts):
    """o promovare cere o fereastra prospectiva NOUA, neatinsa de evaluarile anterioare: startul ferestrei trebuie sa fie dupa sfarsitul oricarei ferestre folosite de o incercare precedenta."""
    ends=[a.get("window_end_ts") for a in attempts() if a["kind"] in ("PROMOTION_EVAL","CHALLENGER_TRAINED") and a.get("window_end_ts")]
    return (not ends) or window_start_ts>max(ends)
def cluster_ci(v,clusters,B=4000,alpha=0.05,seed=20260905):
    """bootstrap pe clustere (mint x zi): CI la nivel 1-alpha (alpha corectat Bonferroni pentru numarul de challengere incercate)."""
    v=np.asarray(v,float); cl=np.asarray(clusters); u=np.unique(cl)
    if len(v)==0: return None
    rng=np.random.default_rng(seed); groups=[v[cl==c] for c in u]; means=np.sort([np.concatenate([groups[i] for i in rng.integers(0,len(u),len(u))]).mean() for _ in range(B)])
    return dict(lo=float(means[int(alpha/2*B)]),hi=float(means[min(B-1,int((1-alpha/2)*B))]),alpha=alpha,clusters=int(len(u)))
def rollback_check(ev_champion,thresholds=dict(min_n=100,lcb95_max=0.0)):
    """rollback AUTOMAT la ultimul champion arhivat daca champion-ul curent, pe fereastra prospectiva, are LCB95(EV) < 0 cu >= min_n semnale sau drift sever. Promovarea ramane manuala."""
    s=(ev_champion or {}).get("selected_region") or {}; d=(ev_champion or {}).get("drift") or {}
    return bool(d.get("SEVERE")) or ((s.get("N") or 0)>=thresholds["min_n"] and (s.get("EV_LCB95") if s.get("EV_LCB95") is not None else 1)<thresholds["lcb95_max"])
def do_rollback(reason):
    arch=sorted(glob.glob(os.path.join(STATE,"champion_archived_*.json")))
    if not arch: register_attempt("ROLLBACK_NOOP",dict(reason=reason,note="niciun champion arhivat")); return False
    prev=json.load(open(arch[-1])); cur=json.load(open(os.path.join(HERE,"champion.json"))); json.dump(cur,open(os.path.join(STATE,f"champion_rolledback_{int(time.time())}.json"),"w"),indent=1)
    prev["policy_enabled"]=False; prev["rolled_back_at"]=time.strftime("%Y-%m-%d %H:%M:%S %Z"); prev["rollback_reason"]=reason; json.dump(prev,open(os.path.join(HERE,"champion.json"),"w"),indent=1); register_attempt("ROLLBACK",dict(reason=reason,to=prev["artifact_sha256"],from_=cur["artifact_sha256"])); return True
FORWARD_GATES=dict(MIN_SIGNALS=300,MIN_UTC_DAYS=7,MIN_DAYS_WITH_SIGNALS=5,CI_LOWER_EV_GT=0.0,PF_MIN=1.30,MIN_POSITIVE_DAYS=4,EV_CONSERVATIVE_LANDING_GT=0.0,EV_LAND5_GT=0.0,EX_BEST_1PCT_GT=0.0,MAX_SHARE_DAY_HOUR_ENTITY=0.20,BASELINE_COMPARISON=True,MULTIPLE_TESTING="Bonferroni pe numarul de challengere incercate",MATURITY_S=960,ONE_DECISION_PER_MINT=True,NO_RETRAIN_IN_CONFIRMATION=True)
def forward_gates(rows_sel,rows_all_ok,baseline_rows_sel,n_tried):
    """portile prospective (regula 6). rows_sel: predictii selectate (WATCH) cu outcome OK; foloseste pnl conservative (limite de ordine) si land5."""
    alpha=0.05/max(1,n_tried); g={}; s=rows_sel
    days=sorted({utc(r["decision_time"])[:10] for r in s}); all_days=sorted({utc(r["decision_time"])[:10] for r in rows_all_ok}); v=np.array([r.get("realized_net_pnl_conservative",r["realized_net_pnl"]) for r in s]) if s else np.array([])
    g["MIN_SIGNALS_300"]=len(s)>=300; g["MIN_UTC_DAYS_7"]=len(all_days)>=7; g["MIN_DAYS_WITH_SIGNALS_5"]=len(days)>=5
    ci=cluster_ci(v,[r["mint_hash"]+utc(r["decision_time"])[:10] for r in s],alpha=alpha) if len(v) else None; g["CI_LOWER_EV_GT_0 (alpha=%.4f)"%alpha]=bool(ci and ci["lo"]>0); st=evstats(v) if len(v) else None
    g["PF_GE_1.30"]=bool(st and st["PF"]>=1.30); byd=collections.defaultdict(list); [byd[utc(r["decision_time"])[:10]].append(r.get("realized_net_pnl_conservative",r["realized_net_pnl"])) for r in s]; g["EV_POSITIVE_DAYS_GE_4"]=sum(1 for x in byd.values() if np.mean(x)>0)>=4
    g["EV_CONSERVATIVE_LANDING_GT_0"]=bool(len(v) and v.mean()>0); l5=[r["realized_net_pnl_land5"] for r in s if r.get("realized_net_pnl_land5") is not None]; g["EV_LAND5_GT_0"]=bool(l5 and np.mean(l5)>0); g["EX_BEST_1PCT_GT_0"]=bool(st and st["EX_BEST_1PCT"]>0)
    pos=lambda key: (max((sum(max(0.0,x.get("realized_net_pnl_conservative",x["realized_net_pnl"])) for x in s if key(x)==k) for k in {key(x) for x in s}),default=0)/max(1e-12,sum(max(0.0,x.get("realized_net_pnl_conservative",x["realized_net_pnl"])) for x in s)))
    g["MAX_SHARE_DAY_HOUR_ENTITY_LE_0.20"]=bool(s) and max(pos(lambda x:utc(x["decision_time"])[:10]),pos(lambda x:utc(x["decision_time"])[:13]),pos(lambda x:x["mint_hash"]))<=0.20
    bv=np.array([r.get("realized_net_pnl_conservative",r["realized_net_pnl"]) for r in baseline_rows_sel]) if baseline_rows_sel else np.array([]); g["BEATS_STATE_HEADROOM_BASELINE"]=(bool(len(v) and len(bv) and v.mean()>bv.mean()) if (len(bv) and len(v)) else "N/A (baseline sau politica fara semnale)")
    g["MULTIPLE_TESTING_CORRECTION"]=f"Bonferroni: {n_tried} challengere incercate => alpha {alpha:.4f}"; g["HUMAN_APPROVAL_REQUIRED"]="PENDING"
    return g,dict(ci=ci,stats=st,days=days,all_days=all_days,n=len(s))
