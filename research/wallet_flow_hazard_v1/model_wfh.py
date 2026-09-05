"""WALLET_FLOW_HAZARD_V1 — MODEL: H hazarde concurente (person-period multinomial logistic), B GBM multinomial static, C baseline MARKET_STATE; calibrare pe CAL; selectie model pe CAL (log loss -> EV);
checkpoint + prag EXCLUSIV pe TRAIN/CAL (grila restransa); evaluare VAL/CONF o singura data: exit static (conservative) si exit dinamic (regula inghetata), fara alegere pe VAL/CONF; porti; Holm pe 3 modele x 2 exit-uri."""
import os,sys,gzip,json,time,math,collections,hashlib,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import wfh_lib as W; V=W.V; L=W.L
DW=os.environ.get("WFH_DERIVED_DIR",os.path.join(HERE,"derived_wfh")); D2=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(HERE),"curve2x_v2","derived")); SPEC=json.load(open(os.path.join(HERE,"frozen_spec.json")))
CLASSES=["TP_FIRST","SL_FIRST","TIMEOUT_OTHER"]; TV=["b","value_ratio","vmin","vmax","net_flow","sell_vol","n"]
def usable(r,key="bounds"): b=r["lab"][key]; return b.get("status")=="OK" and not b.get("unavailable") and not r["gap"] and r["bins"] is not None
def Y_of(rows): 
    Y=np.zeros((len(rows),3))
    for i,r in enumerate(rows): Y[i,CLASSES.index(r["lab"]["bounds"]["conservative"]["state"])]=1
    return Y
def pnl(rows,key="bounds"): return np.array([r["lab"][key]["conservative"]["pnl"] for r in rows],float)
def pp_rows(rows,X):
    """person-period: pentru fiecare decizie si bin pana la eveniment; tinta TP/SL/none in bin; covariate = X intrare + covariate variabile in timp."""
    Xs=[];Ys=[]
    for r,x in zip(rows,X):
        prev=dict(value_ratio=r["entry_ratio"],vmin=r["entry_ratio"],vmax=r["entry_ratio"],net_flow=0.0,sell_vol=0.0,n=0)   # covariatele bin-ului b sunt cele cunoscute la INCEPUTUL lui (sfarsitul bin-ului b-1); bin 0 = starea de intrare
        for b in r["bins"]:
            Xs.append(np.concatenate([x,[b["b"],prev["value_ratio"],prev["vmin"],prev["vmax"],prev["net_flow"],prev["sell_vol"],prev["n"]]])); Ys.append([b["event"]=="TP",b["event"]=="SL",b["event"] is None]); prev=b
            if b["event"]: break
    return np.array(Xs),np.array(Ys,float)
def hazard_probs(mh,x_entry,entry_ratio):
    """P_TP/P_SL/P_TO la intrare: hazarde cauza-specifice prezise cu covariate 'de intrare' (value_ratio = raportul la intrare, fluxuri 0) pe cele 15 bin-uri; S(b) = prod(1 - hTP - hSL)."""
    Xb=np.array([np.concatenate([x_entry,[b,entry_ratio,entry_ratio,entry_ratio,0.0,0.0,0.0]]) for b in range(W.NBINS)]); Xb=np.sign(Xb)*np.log1p(np.abs(Xb)); P=L.pred_mlogit(mh,Xb); S=1.0; ptp=psl=0.0
    for b in range(W.NBINS): ptp+=S*P[b,0]; psl+=S*P[b,1]; S*=max(0.0,1-P[b,0]-P[b,1])
    return np.array([ptp,psl,max(0.0,1-ptp-psl)])
def hz_bin(mh,x_entry,b,entry_ratio=None):
    """hazardul prezis pentru bin-ul URMATOR: covariate = starea cunoscuta la sfarsitul bin-ului b (sau starea de intrare daca b is None)."""
    if b is None: Xb=np.array([np.concatenate([x_entry,[0,entry_ratio,entry_ratio,entry_ratio,0.0,0.0,0.0]])])
    else: Xb=np.array([np.concatenate([x_entry,[b["b"]+1,b["value_ratio"],b["vmin"],b["vmax"],b["net_flow"],b["sell_vol"],b["n"]]])])
    Xb=np.sign(Xb)*np.log1p(np.abs(Xb)); return L.pred_mlogit(mh,Xb)[0]
def stats(v,groups=None,hours=None):
    v=np.asarray(v,float)
    if len(v)==0: return dict(usable=0)
    st=L.evstats(v,groups); rng=np.random.default_rng(20260905); bs=np.sort([v[rng.integers(0,len(v),len(v))].mean() for _ in range(4000)]); out=dict(usable=len(v),**{k:st[k] for k in ("EV","median","PF","win_rate","EX_BEST_1PCT")},max_mint_share=st.get("max_group_share"),CI95=(float(bs[100]),float(bs[3899])),LCB90=float(bs[400]),p_one_sided=float(np.mean(bs<=0)))
    if hours is not None:
        pos=collections.defaultdict(float); [pos.__setitem__(h,pos[h]+max(0.0,x)) for h,x in zip(hours,v)]; gp=sum(pos.values()) or 1e-12; out["max_hour_share"]=float(max(pos.values())/gp); hc=collections.Counter(hours); out["max_signal_share_same_hour"]=max(hc.values())/len(v)
    return out
def holm(pvals):
    idx=sorted(range(len(pvals)),key=lambda i:pvals[i]); m=len(pvals); adj=[0]*m; run=0
    for rank,i in enumerate(idx): run=max(run,(m-rank)*pvals[i]); adj[i]=min(1.0,run)
    return adj
def main():
    t0=time.time(); rows=[json.loads(l) for l in gzip.open(f"{DW}/wfh_rows.jsonl.gz","rt")]; S={s:[r for r in rows if r["split"]==s] for s in ("TRAIN","CAL","VAL","CONF")}
    tr=[r for r in S["TRAIN"] if usable(r)]; ca=[r for r in S["CAL"] if usable(r)]; R=dict(label="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED",split_counts={s:len(v) for s,v in S.items()},usable=dict(TRAIN=len(tr),CAL=len(ca)))
    Xtr,fill=L.X_of(tr,W.FEATS); Xca,_=L.X_of(ca,W.FEATS,fill); Ytr=Y_of(tr); Yca=Y_of(ca); R["base_rates"]={"TRAIN":dict(zip(CLASSES,Ytr.mean(0).tolist())),"CAL":dict(zip(CLASSES,Yca.mean(0).tolist()))}
    raw_tr=np.array([[r["f"].get(k) if r["f"].get(k) is not None else np.nan for k in W.FEATS] for r in tr],float); raw_tr=np.where(np.isnan(raw_tr),np.nanmedian(raw_tr,0),raw_tr); raw_ca=np.array([[r["f"].get(k) if r["f"].get(k) is not None else np.nan for k in W.FEATS] for r in ca],float); raw_ca=np.where(np.isnan(raw_ca),np.nanmedian(raw_tr,0),raw_ca)
    # H: hazarde concurente (covariate brute -> signed log1p in interior)
    Xpp,Ypp=pp_rows(tr,raw_tr); Xpp=np.sign(Xpp)*np.log1p(np.abs(Xpp)); mh=L.fit_mlogit(Xpp,Ypp,l2=1.0,it=1200,lr=0.1); R["person_periods_train"]=len(Xpp)
    def entry_ratio(r): return r["entry_ratio"] if r.get("entry_ratio") is not None else 0.97   # raportul executabil la INTRARE (fara nicio stare ulterioara)
    PH_ca=np.array([hazard_probs(mh,x,entry_ratio(r)) for r,x in zip(ca,raw_ca)]); PH_ca=PH_ca/PH_ca.sum(1,keepdims=True)
    mb=L.fit_mgbm(Xtr,Ytr); PB_ca=L.predict(mb,Xca); Xc_tr,fillc=L.X_of(tr,W.STATE_FEATS); Xc_ca,_=L.X_of(ca,W.STATE_FEATS,fillc); mc=L.fit_mlogit(Xc_tr,Ytr); PC_ca=L.predict(mc,Xc_ca)
    cand={}
    for name,P in (("H",PH_ca),("B",PB_ca),("C",PC_ca)):
        cal=L.fit_vector_scaling(P,Yca); Pc=L.apply_cal(cal,P); top=Pc[:,0]>=min(SPEC["policy"]["p_tp_grid"]); cand[name]=dict(cal=cal,log_loss=L.log_loss(Pc,Yca),brier=L.brier_mc(Pc,Yca),ece_tp=L.ece_bin(Pc[:,0],Yca[:,0]),gap_top=float(abs(Pc[top,0].mean()-Yca[top,0].mean())) if top.any() else None,n_top=int(top.sum()),rel_tp=L.reliability(Pc[:,0],Yca[:,0]))
    R["cal_prior_log_loss"]=L.log_loss(np.tile(Ytr.mean(0),(len(ca),1)),Yca); R["candidates"]={k:{kk:vv for kk,vv in v.items() if kk!="cal"} for k,v in cand.items()}
    sel=min(("H","B"),key=lambda k:cand[k]["log_loss"]); R["selected_model_on_cal"]=sel
    reg=L.fit_gbm_reg(Xtr,pnl(tr)); regC=L.fit_gbm_reg(Xc_tr,pnl(tr))
    def scores(rr,which):
        X,_=L.X_of(rr,W.FEATS,fill); raw=np.array([[r["f"].get(k) if r["f"].get(k) is not None else np.nan for k in W.FEATS] for r in rr],float); raw=np.where(np.isnan(raw),np.nanmedian(raw_tr,0),raw)
        if which=="H": P=np.array([hazard_probs(mh,x,entry_ratio(r)) for r,x in zip(rr,raw)]); P=P/P.sum(1,keepdims=True)
        elif which=="B": P=L.predict(mb,X)
        else: Xc,_=L.X_of(rr,W.STATE_FEATS,fillc); P=L.predict(mc,Xc)
        Pc=L.apply_cal(cand[which]["cal"],P); ev=L.pred_gbm_reg(regC if which=="C" else reg,L.X_of(rr,W.STATE_FEATS,fillc)[0] if which=="C" else X); return Pc,ev,raw
    # ---- selectia checkpoint + prag pe TRAIN/CAL (grila restransa) ----
    def policy_rows(rr,Pc,ev,Lmin,p):
        by=collections.defaultdict(list)
        for k,r in enumerate(rr): by[r["mint"]].append((r["landmark"],k))
        sel_=[]
        for m,lst in by.items():
            for lm,k in sorted(lst):
                if lm>=Lmin and Pc[k,0]>=p and ev[k]>0: sel_.append(k); break
        return sel_
    ca_ok=[r for r in S["CAL"] if r["lab"]["bounds"].get("status")=="OK"]; Pc_ca,ev_ca,_=scores(ca_ok,sel); grid=[]
    for Lm in SPEC["policy"]["checkpoint_grid"]:
        for p in SPEC["policy"]["p_tp_grid"]:
            ks=[k for k in policy_rows(ca_ok,Pc_ca,ev_ca,Lm,p) if usable(ca_ok[k])]; st=stats([ca_ok[k]["lab"]["bounds"]["conservative"]["pnl"] for k in ks]); grid.append(dict(Lmin=Lm,p_tp_min=p,cal=st))
    ok=[g for g in grid if g["cal"].get("usable",0)>=30 and (g["cal"].get("EV") or -1)>0]; best=max(ok,key=lambda g:g["cal"]["LCB90"]) if ok else max(grid,key=lambda g:(g["cal"].get("LCB90") if g["cal"].get("usable") else -9))
    pol=dict(Lmin=best["Lmin"],p_tp_min=best["p_tp_min"]); R["policy_grid_cal"]=grid; R["policy_selected"]=pol; R["policy_feasible_on_cal"]=bool(ok)
    art=dict(label="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED",model=sel,features=W.FEATS,fill=fill.tolist(),train_median_raw=np.nanmedian(raw_tr,0).tolist(),hazard=mh,gbm=mb,state=mc,cal={k:v["cal"] for k,v in cand.items()},reg=reg,regC=regC,fillc=fillc.tolist(),policy=pol,policy_enabled=False); s=json.dumps(art,sort_keys=True,separators=(",",":"),default=float); open(os.path.join(HERE,"model_artifact.json"),"w").write(s); R["model_hash"]=hashlib.sha256(s.encode()).hexdigest()
    # ---- evaluare VAL/CONF o singura data: static conservative + exit dinamic (regula inghetata), pentru H, B, C ----
    need=set(); EV={}
    for seg in ("VAL","CONF","VAL+CONF"):
        rr=[r for r in (S["VAL"]+S["CONF"] if seg=="VAL+CONF" else S[seg]) if r["lab"]["bounds"].get("status")=="OK"]; EV[seg]={}
        for which in ("H","B","C"):
            Pc,ev,raw=scores(rr,which); ks=[k for k in policy_rows(rr,Pc,ev,pol["Lmin"],pol["p_tp_min"]) if usable(rr[k])]; selr=[rr[k] for k in ks]; need|={r["mint"] for r in selr}
            res=dict(static=stats([r["lab"]["bounds"]["conservative"]["pnl"] for r in selr],[r["mint"] for r in selr],[r["hour"] for r in selr]),land5=stats([r["lab"]["bounds_land5"]["conservative"]["pnl"] for r in selr if r["lab"]["bounds_land5"].get("status")=="OK" and not r["lab"]["bounds_land5"].get("unavailable")]),cost125=stats([r["lab"]["bounds_cost125"]["conservative"]["pnl"] for r in selr if r["lab"]["bounds_cost125"].get("status")=="OK" and not r["lab"]["bounds_cost125"].get("unavailable")]),n_signals=len(selr),TP_rate=float(np.mean([r["lab"]["bounds"]["conservative"]["state"]=="TP_FIRST" for r in selr])) if selr else None,SL_rate=float(np.mean([r["lab"]["bounds"]["conservative"]["state"]=="SL_FIRST" for r in selr])) if selr else None,mean_P_TP=float(np.mean([Pc[k,0] for k in ks])) if ks else None,mean_P_SL=float(np.mean([Pc[k,1] for k in ks])) if ks else None,max_creator_share=(L.evstats([r["lab"]["bounds"]["conservative"]["pnl"] for r in selr],[r["creator"] for r in selr]) or {}).get("max_group_share") if selr else None,by_day={d:float(np.mean([r["lab"]["bounds"]["conservative"]["pnl"] for r in selr if r["day"]==d])) for d in sorted({r["day"] for r in selr})},sel_keys=[(r["mint"],r["landmark"]) for r in selr],raw_sel=[raw[k].tolist() for k in ks])
            if selr: Ps=np.array([[Pc[k,0],Pc[k,1],Pc[k,2]] for k in ks]); Ys=Y_of(selr); res["calibration_selected"]=dict(n=len(selr),gap_tp=float(abs(Ps[:,0].mean()-Ys[:,0].mean())),pred_tp=float(Ps[:,0].mean()),obs_tp=float(Ys[:,0].mean()))
            EV[seg][which]=res
    # exit dinamic: recalculam traiectoriile pentru mint-urile selectate (subset), regula inghetata cu hazardele H
    recs={}
    with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
        for line in f:
            m=line[9:60].split('"')[0]
            if m in need: recs[m]=json.loads(line)
    idx={(r["mint"],r["landmark"]):r for r in rows}
    for seg in EV:
        for which in EV[seg]:
            res=EV[seg][which]; dyn=[]; changed=0
            for (m,lm),xraw in zip(res["sel_keys"],res["raw_sel"]):
                r=idx[(m,lm)]; rec=recs[m]; pool=L.pool_prepare(rec.get("pool")) if rec.get("pool") else None; pb=W.path_bins(rec,r["i"],r["ts"],pool=pool)
                if pb is None or pb.get("unavailable"): dyn.append(r["lab"]["bounds"]["conservative"]["pnl"]); continue
                x=np.array(xraw); h0=hz_bin(mh,x,None,pb["entry_ratio"]); out=None
                for b in pb["bins"]:
                    if b["event"]: break
                    if b["b"]>=1:
                        h=hz_bin(mh,x,b)   # decizie la SFARSITUL bin-ului b, cu informatia de pana atunci
                        if h[0]<h0[0] and h[1]>h0[1] and b["exit_state"] is not None:
                            p_=W.dynamic_exit_pnl(rec,pb,b["b"],b["exit_state"][1]); out=p_; break
                if out is None: dyn.append(r["lab"]["bounds"]["conservative"]["pnl"])
                else: dyn.append(out); changed+=1
            res["dynamic"]=stats(dyn,[k[0] for k in res["sel_keys"]]); res["dynamic_exits_triggered"]=changed; res["dynamic_delta_EV"]=(res["dynamic"].get("EV") or 0)-(res["static"].get("EV") or 0) if res["static"].get("usable") else None; res.pop("sel_keys"); res.pop("raw_sel")
    R["evaluation"]=EV
    # ---- porti (model selectat, exit static conservative = primar) + Holm pe 3 modele x 2 exit-uri ----
    a=EV["VAL+CONF"][sel]; v=EV["VAL"][sel]; c_=EV["CONF"][sel]; st=a["static"]; g={}
    g["min_signals_val_conf_100"]=st.get("usable",0)>=100; g["min_conf_30"]=c_["static"].get("usable",0)>=30; g["ev_conservative_gt_0"]=(st.get("EV") or -1)>0; g["ci95_lower_gt_0"]=((st.get("CI95") or (-1,))[0])>0; g["pf_ge_1_30"]=(st.get("PF") or 0)>=1.30
    g["val_and_conf_positive"]=(v["static"].get("EV") or -1)>0 and (c_["static"].get("EV") or -1)>0; g["land5_gt_0"]=(a["land5"].get("EV") or -1)>0; g["cost125_gt_0"]=(a["cost125"].get("EV") or -1)>0; g["ex_best_1pct_gt_0"]=(st.get("EX_BEST_1PCT") or -1)>0
    g["beats_v3_conservative"]=(st.get("EV") or -1)>SPEC["gates"]["beats_v3_conservative"]; bc=EV["VAL+CONF"]["C"]["static"]; g["beats_state_headroom_baseline"]=((st.get("EV") or -1)>(bc.get("EV") or -1)) if (bc.get("usable") and st.get("usable")) else "N/A"
    g["no_entity_hour_day_gt_20pct"]=all((x or 1)<=0.20 for x in (st.get("max_mint_share"),a.get("max_creator_share"),st.get("max_hour_share"))) and (max((abs(x) for x in a["by_day"].values()),default=0)<=0.2*abs(sum(a["by_day"].values())) if len(a["by_day"])>1 else False)
    tests=[]; 
    for which in ("H","B","C"):
        for ex in ("static","dynamic"): tests.append((f"{which}/{ex}",EV["VAL+CONF"][which][ex].get("p_one_sided",1.0) if EV["VAL+CONF"][which][ex].get("usable") else 1.0))
    adj=holm([p for _,p in tests]); R["holm"]={t:dict(p=p,p_holm=q) for (t,p),q in zip(tests,adj)}; g["holm_significant_primary"]=R["holm"].get(f"{sel}/static",{}).get("p_holm",1.0)<0.05
    R["gates"]=g; R["FINAL_VERDICT"]="HISTORICAL_PAPER_CANDIDATE_REQUIRES_FRESH_FORWARD" if all(x is True for x in g.values()) else "NO_VERIFIED_EDGE"; R["runtime_s"]=round(time.time()-t0,1)
    json.dump(R,open(os.path.join(HERE,"results.json"),"w"),indent=1,default=float); print(json.dumps(dict(sel=sel,policy=pol,feasible=bool(ok),val=v["static"],conf=c_["static"],all=st,dyn=a["dynamic"],gates=g,verdict=R["FINAL_VERDICT"]),default=float)[:2500]); print("MODEL_DONE",flush=True)
if __name__=="__main__": main()
