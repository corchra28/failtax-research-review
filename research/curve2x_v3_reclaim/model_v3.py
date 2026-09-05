"""CURVE2X V3 RECLAIM — MODEL: A multinomial logistic L2, B GBM depth-2 multiclass, C baseline state/headroom (logit); calibrare vector scaling pe CAL; selectie pe CAL
(log loss -> calibrare -> EV estimat, tolerante fixe); prag P_TP_FIRST din grila fixa, ales pe CAL (max LCB90 al EV per mint, >= 30 mint-uri); INGHETARE; evaluare VAL/CONF o singura
data la nivel de mint; porti; verdict maxim HISTORICAL_PAPER_CANDIDATE_REQUIRES_FRESH_FORWARD; policy_enabled=false. Zero RPC."""
import os,sys,gzip,json,time,math,collections,hashlib,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L
D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(HERE,"derived_v3")); SPEC=json.load(open(os.path.join(HERE,"frozen_spec.json"))); CLASSES=["TP_FIRST","SL_FIRST","TIMEOUT_OTHER"]; TOL=SPEC["model_selection"]["tolerance_rel"]
P_GRID=SPEC["policy"]["p_tp_grid"]; MIN_CAL=SPEC["policy"]["min_mints_cal"]
def usable(r,var="base"): x=r["lab"][var]; return x.get("status")=="OK" and x["15M"]["state"] is not None and not r["gap"]
def Y_of(rows,var="base"):
    Y=np.zeros((len(rows),3))
    for i,r in enumerate(rows): Y[i,CLASSES.index(r["lab"][var]["15M"]["state"])]=1
    return Y
def pnl_of(rows,var="base"): return np.array([r["lab"][var]["15M"]["pnl"] for r in rows],float)
def region_cal(P,Y):
    if len(P)==0: return dict(n=0,gap_tp=None)
    return dict(n=int(len(P)),gap_tp=float(abs(P[:,0].mean()-Y[:,0].mean())),pred_tp=float(P[:,0].mean()),obs_tp=float(Y[:,0].mean()),gap_sl=float(abs(P[:,1].mean()-Y[:,1].mean())),ece_tp=L.ece_bin(P[:,0],Y[:,0],5))
def regstats_of(reg,Xc,yc):
    p=L.pred_gbm_reg(reg,Xc); edges=np.quantile(p,np.linspace(0,1,6)[1:-1]).tolist(); dec=np.clip(np.searchsorted(edges,p,side="right"),0,4); sd=[];n=[]
    for d in range(5):
        m=dec==d; n.append(int(m.sum())); sd.append(float((p[m]-yc[m]).std()) if m.sum()>=5 else float((p-yc).std()))
    return dict(edges=edges,sd=sd,n=n,resid_sd_all=float((p-yc).std()))
def score(rows,X,art_models,fl):
    m=art_models; P=L.apply_cal(m["cal"],L.predict(m["clf"],X)); ev=L.pred_gbm_reg(m["reg"],X); rs=m["regstats"]; W=np.array(m["drv"]["W"]); mu=np.array(m["drv"]["mu"]); sd=np.array(m["drv"]["sd"]); out=[]
    for i,r in enumerate(rows):
        dec=int(np.clip(np.searchsorted(rs["edges"],ev[i],side="right"),0,4)); n=max(1,rs["n"][dec]); p=float(P[i,0]); z=(X[i]-mu)/sd; contrib=z*(W[:,0]-W[:,1])   # directie TP vs SL in logit-ul companion
        top=np.argsort(-contrib)[:3]; bot=np.argsort(contrib)[:3]
        out.append(dict(p_tp=p,p_sl=float(P[i,1]),p_to=float(P[i,2]),ev=float(ev[i]),ev_lcb=float(ev[i]-1.2816*rs["sd"][dec]/math.sqrt(n)),uncertainty=float(math.sqrt(p*(1-p)/n)),n_similar=int(n),top_positive=[fl[j] for j in top],top_risk=[fl[j] for j in bot]))
    return out
def decide(sc,pol): 
    if sc["p_tp"]>=pol["p_tp_min"] and sc["ev"]>0: return "WATCH","ELIGIBLE_POLICY_DISABLED"
    return "REJECT",("P_TP_BELOW_MIN" if sc["p_tp"]<pol["p_tp_min"] else "EV_NOT_POSITIVE")
def stats(rows_sel,var="base"):
    ok=[r for r in rows_sel if usable(r,var)]
    if not ok: return dict(signals=len(rows_sel),usable=0)
    v=pnl_of(ok,var); st=L.evstats(v,[r["mint"] for r in ok]); states=collections.Counter(r["lab"][var]["15M"]["state"] for r in ok)
    rng=np.random.default_rng(20260905); bs=np.sort([v[rng.integers(0,len(v),len(v))].mean() for _ in range(4000)])   # bootstrap mint x zi (un rand = un mint)
    hrs=collections.Counter(r["hour"] for r in ok); pos=collections.defaultdict(float)
    for r,x in zip(ok,v): pos[r["hour"]]+=max(0.0,x)
    gp=sum(pos.values()) or 1e-12
    return dict(signals=len(rows_sel),usable=len(ok),TP_FIRST_rate=states["TP_FIRST"]/len(ok),SL_FIRST_rate=states["SL_FIRST"]/len(ok),timeout_rate=states["TIMEOUT_OTHER"]/len(ok),**{k:st[k] for k in ("EV","median","PF","win_rate","EX_BEST_1PCT")},max_mint_share=st["max_group_share"],max_creator_share=L.evstats(v,[r["creator"] for r in ok])["max_group_share"],max_hour_share=float(max(pos.values())/gp),CI95=(float(bs[100]),float(bs[3899])),LCB90=float(bs[400]),max_signal_share_same_hour=max(hrs.values())/len(ok),by_day=dict(collections.Counter(r["day"] for r in ok)))
def main():
    t0=time.time(); rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt")]; S={s:[r for r in rows if r["split"]==s] for s in ("TRAIN","CAL","VAL","CONF")}
    R=dict(label="HISTORICAL_DEV_NOT_SEALED",split_counts={s:len(v) for s,v in S.items()},classes=CLASSES,notional=V.N_REF,horizon="15M",tp=V.TP_MULT,sl=V.SL_MULT)
    tr=[r for r in S["TRAIN"] if usable(r)]; ca=[r for r in S["CAL"] if usable(r)]; R["usable"]={"TRAIN":len(tr),"CAL":len(ca)}
    if len(tr)<50 or len(ca)<20: R["FINAL_VERDICT"]="NO_VERIFIED_EDGE"; R["reason"]="INSUFFICIENT_SAMPLE"; json.dump(R,open(os.path.join(HERE,"results.json"),"w"),indent=1); print(json.dumps(R)); print("MODEL_DONE"); return
    Ytr=Y_of(tr); Yca=Y_of(ca); R["base_rates"]={"TRAIN":dict(zip(CLASSES,Ytr.mean(0).tolist())),"CAL":dict(zip(CLASSES,Yca.mean(0).tolist()))}
    XS={"full":V.FEATS,"state":V.STATE_FEATS}; cand=[]; fits={}
    for kind,fl,fitf in (("A","full",L.fit_mlogit),("B","full",L.fit_mgbm),("C","state",L.fit_mlogit)):
        feats=XS[fl]; Xtr,fill=L.X_of(tr,feats); Xca,_=L.X_of(ca,feats,fill); m=fitf(Xtr,Ytr); Pca=L.predict(m,Xca); cal=L.fit_vector_scaling(Pca,Yca); Pc=L.apply_cal(cal,Pca)
        reg=L.fit_gbm_reg(Xtr,pnl_of(tr)); rs=regstats_of(reg,Xca,pnl_of(ca)); ev=L.pred_gbm_reg(reg,Xca); top=Pc[:,0]>=min(P_GRID)
        cand.append(dict(kind=kind,feats=fl,log_loss=L.log_loss(Pc,Yca),brier=L.brier_mc(Pc,Yca),ece_tp=L.ece_bin(Pc[:,0],Yca[:,0]),top=region_cal(Pc[top],Yca[top]),ev_cal_top=float(pnl_of(ca)[top].mean()) if top.any() else None,rel_tp=L.reliability(Pc[:,0],Yca[:,0]),rel_sl=L.reliability(Pc[:,1],Yca[:,1])))
        fits[kind]=dict(clf=m,cal=cal,reg=reg,regstats=rs,feats=feats,fill=fill.tolist(),Xtr=Xtr,Xca=Xca)
    R["cal_prior_log_loss"]=L.log_loss(np.tile(Ytr.mean(0),(len(ca),1)),Yca); R["candidates"]=cand
    ab=[c for c in cand if c["kind"] in ("A","B")]; best=min(c["log_loss"] for c in ab); s1=[c for c in ab if c["log_loss"]<=best*(1+TOL)]
    bg=min((c["top"]["gap_tp"] if c["top"]["gap_tp"] is not None else 1.0) for c in s1); s2=[c for c in s1 if (c["top"]["gap_tp"] if c["top"]["gap_tp"] is not None else 1.0)<=bg+0.01]
    sel=max(s2,key=lambda c:(c["ev_cal_top"] if c["ev_cal_top"] is not None else -9)) if len(s2)>1 else s2[0]; kind=sel["kind"]; R["selection"]=dict(stage1=[c["kind"] for c in s1],stage2=[c["kind"] for c in s2],selected=kind,tolerance_rel=TOL)
    F=fits[kind]; fl=F["feats"]; drv=fits["A"]["clf"]; art_m=dict(clf=F["clf"],cal=F["cal"],reg=F["reg"],regstats=F["regstats"],drv=dict(W=drv["W"],mu=drv["mu"],sd=drv["sd"]))
    # prag pe CAL (grila fixa): max LCB90 al EV per mint, >= MIN_CAL mint-uri
    sc_ca=score(ca,F["Xca"],art_m,fl); grid=[]
    for p in P_GRID:
        pol=dict(p_tp_min=p); sel_rows=[r for r,s in zip(ca,sc_ca) if decide(s,pol)[0]=="WATCH"]; st=stats(sel_rows); grid.append(dict(policy=pol,cal=st))
    ok=[g for g in grid if g["cal"].get("usable",0)>=MIN_CAL and (g["cal"].get("EV") or -1)>0]
    if ok: pol=max(ok,key=lambda g:g["cal"]["LCB90"])["policy"]; R["policy_feasible_on_cal"]=True
    else: pol=max(grid,key=lambda g:(g["cal"].get("LCB90") if g["cal"].get("usable") else -9))["policy"]; R["policy_feasible_on_cal"]=False; R["policy_note"]="nicio valoare din grila nu are >= %d mint-uri cu EV>0 pe CAL; prag raportat doar diagnostic"%MIN_CAL
    R["policy_grid_cal"]=grid; R["policy_selected"]=pol
    art=dict(label="HISTORICAL_DEV_NOT_SEALED",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),model_kind=kind,features=fl,fill=F["fill"],policy=pol,policy_enabled=False,final_verdict=None,models=art_m,classes=CLASSES,notional=V.N_REF)
    # evaluare VAL / CONF o singura data
    EV={}; sig_rows=[]
    for seg in ("VAL","CONF","VAL+CONF"):
        rr=S["VAL"]+S["CONF"] if seg=="VAL+CONF" else S[seg]; rr=[r for r in rr if r["lab"]["base"].get("status")=="OK"]
        if not rr: EV[seg]=dict(base=dict(signals=0,usable=0)); continue
        X,_=L.X_of(rr,fl,np.array(F["fill"])); sc=score(rr,X,art_m,fl); selr=[(r,s) for r,s in zip(rr,sc) if decide(s,pol)[0]=="WATCH"]
        res={var:stats([r for r,s in selr],var) for var in ("base","land5","cost125")}; us=[(r,s) for r,s in selr if usable(r)]
        if us: res["selected_region_calibration"]=region_cal(np.array([[s["p_tp"],s["p_sl"],s["p_to"]] for r,s in us]),Y_of([r for r,s in us]))
        ra=[r for r in rr if usable(r)]; Xa,_=L.X_of(ra,fl,np.array(F["fill"])); Pa=L.apply_cal(F["cal"],L.predict(F["clf"],Xa)); Ya=Y_of(ra)
        res["all_rows"]=dict(n=len(ra),log_loss=L.log_loss(Pa,Ya),brier=L.brier_mc(Pa,Ya),ece_tp=L.ece_bin(Pa[:,0],Ya[:,0]),base_rates=dict(zip(CLASSES,Ya.mean(0).tolist())),rel_tp=L.reliability(Pa[:,0],Ya[:,0]))
        # baseline C cu aceeasi politica
        FC=fits["C"]; Xc,_=L.X_of(rr,FC["feats"],np.array(FC["fill"])); scc=score(rr,Xc,dict(clf=FC["clf"],cal=FC["cal"],reg=FC["reg"],regstats=FC["regstats"],drv=dict(W=fits["A"]["clf"]["W"],mu=fits["A"]["clf"]["mu"],sd=fits["A"]["clf"]["sd"])) if False else art_m,fl) if False else None
        Pcc=L.apply_cal(FC["cal"],L.predict(FC["clf"],Xc)); evc=L.pred_gbm_reg(FC["reg"],Xc); selc=[r for r,p,e in zip(rr,Pcc[:,0],evc) if p>=pol["p_tp_min"] and e>0]; res["baseline_C_same_policy"]=stats(selc)
        Xa_c,_=L.X_of(ra,FC["feats"],np.array(FC["fill"])); res["baseline_C_all_rows_log_loss"]=L.log_loss(L.apply_cal(FC["cal"],L.predict(FC["clf"],Xa_c)),Ya)
        if seg!="VAL+CONF":
            for r,s in selr: sig_rows.append(dict(mint_id=V.mint_id(r["mint"]),segment=seg,day=r["day"],progress=r["f"]["progress"],**s,state=r["lab"]["base"]["15M"]["state"],pnl=r["lab"]["base"]["15M"]["pnl"],label_kind=r["lab"]["base"]["15M"]["label_kind"],action="WATCH",reason="ELIGIBLE_POLICY_DISABLED"))
        EV[seg]=res
    R["evaluation"]=EV; v,c_,a_=EV["VAL"]["base"],EV["CONF"]["base"],EV["VAL+CONF"]["base"]; A=EV["VAL+CONF"]; G=SPEC["gates"]; g={}
    g["min_mints_val_conf_100"]=a_.get("usable",0)>=100; g["min_mints_conf_30"]=c_.get("usable",0)>=30; g["ev_combined_positive"]=(a_.get("EV") or -1)>0; g["ci95_lower_positive"]=((a_.get("CI95") or (-1,))[0])>0; g["pf_ge_1_30"]=(a_.get("PF") or 0)>=1.30
    g["ev_positive_val_and_conf"]=(v.get("EV") or -1)>0 and (c_.get("EV") or -1)>0; g["ex_best_1pct_positive"]=(a_.get("EX_BEST_1PCT") or -1)>0; g["no_concentration_gt_20pct"]=all((a_.get(k) or 1)<=0.20 for k in ("max_mint_share","max_creator_share","max_hour_share"))
    g["stress_land5_ev_positive"]=(A.get("land5",{}).get("EV") or -1)>0; g["stress_cost125_ev_positive"]=(A.get("cost125",{}).get("EV") or -1)>0; rc=A.get("selected_region_calibration") or {}; g["calibration_region_min_30"]=(rc.get("n") or 0)>=30; g["calibration_gap_le_8pp"]=(rc.get("gap_tp") is not None and rc["gap_tp"]<=0.08)
    bl=A.get("baseline_C_same_policy") or {}; g["beats_state_headroom_baseline"]=(((a_.get("EV") or -1)>(bl.get("EV") or -1)) and (A["all_rows"]["log_loss"]<A["baseline_C_all_rows_log_loss"])) if (bl.get("usable") and a_.get("usable")) else "N/A (baseline sau politica fara semnale)"
    g["hour_diversity_ge_50pct"]=(a_.get("max_signal_share_same_hour") or 1)<=0.5; g["policy_feasible_on_cal"]=R["policy_feasible_on_cal"]
    R["gates"]=g; allpass=all(x is True for x in g.values()); R["FINAL_VERDICT"]="HISTORICAL_PAPER_CANDIDATE_REQUIRES_FRESH_FORWARD" if allpass else "NO_VERIFIED_EDGE"; art["final_verdict"]=R["FINAL_VERDICT"]
    s=json.dumps(art,sort_keys=True,separators=(",",":"),default=float); open(os.path.join(HERE,"model_artifact.json"),"w").write(s); R["model_hash"]=hashlib.sha256(s.encode()).hexdigest(); R["runtime_s"]=round(time.time()-t0,1)
    json.dump(R,open(os.path.join(HERE,"results.json"),"w"),indent=1,default=float); json.dump(sig_rows,open(os.path.join(HERE,"signals_val_conf.json"),"w"),indent=1,default=float)
    print(json.dumps(dict(selected=kind,policy=pol,gates=g,verdict=R["FINAL_VERDICT"],val=v,conf=c_),default=float)[:2500]); print("MODEL_DONE",flush=True)
if __name__=="__main__": main()
