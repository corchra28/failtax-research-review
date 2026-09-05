"""CURVE2X V2 — HISTORICAL_REMEDIATION_NOT_SEALED. Etapa MODEL: ablatiuni fixe M0..M5 x {A multinomial logistic L2, B GBM depth-2} (+ C RF-lite ca verificare),
tinta multinomiala TP_FIRST/SL_FIRST/TIMEOUT_OTHER (orizont primar 15M, notional primar 0,25 SOL); calibrare pe CAL (vector scaling); selectie pe CAL
(log loss -> Brier -> calibrare in top -> EV mint-level, cu tolerante fixe); regressor de PnL cross-fitted; grila fixa de politica pe CAL (max LCB90 al EV per mint);
INGHETARE; evaluare VAL si CONF o singura data la nivel de mint. Zero RPC."""
import gzip,json,sys,os,time,collections,math,datetime,hashlib,multiprocessing as mp
import numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/curve2x_v2"; CLASSES=["TP_FIRST","SL_FIRST","TIMEOUT_OTHER"]
SPEC=json.load(open(f"{OUT}/frozen_spec.json")); TOL=SPEC["model_selection"]["tolerance_rel"]
def key(N,var="base"): return f"{N}|{var}"
def usable(r,N,H,var="base"):
    x=r["lab"][key(N,var)]; return x.get("status")=="OK" and x[H]["state"] is not None and not r["gap"]
def Y_of(rows,N,H,var="base"):
    Y=np.zeros((len(rows),3))
    for i,r in enumerate(rows): Y[i,CLASSES.index(r["lab"][key(N,var)][H]["state"])]=1
    return Y
def pnl_of(rows,N,H,var="base"): return np.array([r["lab"][key(N,var)][H]["pnl"] for r in rows],float)
def feats_for(abl): return [f for b in L.ABLATIONS[abl] for f in L.BLOCKS[b]]
def add_composite(rows,pct):
    """organic_acceleration = pct(vel_last10) x pct(uniq_buyers) x (1 - pct(hhi)) x (1 - pct(top3_share)); percentile invatate EXCLUSIV pe TRAIN, per landmark."""
    for r in rows:
        Lm=str(r["landmark"]); f=r["f"]
        def P(k,v):
            q=pct[Lm][k]; return float(np.searchsorted(q,v,side="right")/len(q)) if v is not None else 0.5
        f["organic_acceleration"]=P("vel_last10",f["vel_last10"])*P("uniq_buyers",f["uniq_buyers"])*(1-P("hhi",f["hhi"]))*(1-P("top3_share",f["top3_share"]))
def fit_pct(train):
    pct={}
    for Lm in L.LANDMARKS:
        sub=[r["f"] for r in train if r["landmark"]==Lm]; pct[str(Lm)]={k:np.quantile([f[k] for f in sub],np.linspace(0.01,0.99,99)).tolist() if sub else [0.0] for k in ("vel_last10","uniq_buyers","hhi","top3_share")}
    return pct
def region_cal(P,Y,mask):
    """calibrare in regiunea eligibila pentru semnale: gap = |mean(p_tp) - obs TP| si ECE pe TP_FIRST in regiune."""
    if mask.sum()==0: return dict(n=0,gap_tp=None,ece_tp=None,gap_sl=None)
    p=P[mask,0]; y=Y[mask,0]; ps=P[mask,1]; ys=Y[mask,1]
    return dict(n=int(mask.sum()),gap_tp=float(abs(p.mean()-y.mean())),ece_tp=L.ece_bin(p,y,5),gap_sl=float(abs(ps.mean()-ys.mean())),pred_tp=float(p.mean()),obs_tp=float(y.mean()))
def fit_one(args):
    abl,kind,Xtr,Ytr=args
    m={"A":L.fit_mlogit,"B":L.fit_mgbm,"C":L.fit_mrf}[kind](Xtr,Ytr); return abl,kind,m
GAPW=None
def gap_windows():
    global GAPW
    if GAPW is None:
        man=json.load(open(f"{D}/curve2x_pass_manifest.json")); W=[tuple(w) for w in man["outage_windows"]]
        ct=[json.loads(l)[1] for l in gzip.open(f"{D}/curve2x_stream.jsonl.gz","rt") if l.startswith('["C"')]; GAPW=W+L.gap_windows_from_create_times(ct)
    return GAPW
def score_rows(rows,X,clf,cal,reg,regstats,N):
    W=gap_windows(); P=L.apply_cal(cal,L.predict(clf,X)); ev=L.pred_gbm_reg(reg,X); out=[]
    for i,r in enumerate(rows):
        dec=int(np.searchsorted(regstats["edges"],ev[i],side="right")); dec=min(max(dec,0),len(regstats["sd"])-1); n=max(1,regstats["n"][dec]); sd=regstats["sd"][dec]
        lcb=ev[i]-1.2816*sd/math.sqrt(n); p=P[i,0]; plcb=max(0.0,p-1.2816*math.sqrt(p*(1-p)/n))
        out.append(dict(mint=r["mint"],creator=r["creator"],landmark=r["landmark"],ts=r["ts"],hour=r["hour"],day=r["day"],f=r["f"],p_tp=float(p),p_sl=float(P[i,1]),p_to=float(P[i,2]),p_tp_lcb=float(plcb),ev=float(ev[i]),ev_lcb=float(lcb),n_similar=int(n),gap_known=L.known_gap(r["ts"],W)))
    return out
def policy_eval(scored,rows_by_idx,pol,N,H,var="base"):
    """o decizie per mint; PnL exact al randului ales (varianta de executie ceruta); statistici la nivel de mint + CI clusterizat pe ora."""
    by=collections.defaultdict(list)
    for sr,idx in zip(scored,rows_by_idx): by[sr["mint"]].append((sr,idx))
    chosen=[]
    for m,lst in by.items():
        d=L.decide_mint([x[0] for x in lst],pol,N)
        if d is None: continue
        idx=next(i for s,i in lst if s is d); chosen.append((d,idx))
    return chosen
def stats_of(chosen,rows,N,H,var="base"):
    ok=[(d,rows[i]) for d,i in chosen if usable(rows[i],N,H,var)]; unav=len(chosen)-len(ok)
    if not ok: return dict(signals=len(chosen),usable=0,unavailable=unav)
    v=np.array([r["lab"][key(N,var)][H]["pnl"] for d,r in ok]); states=collections.Counter(r["lab"][key(N,var)][H]["state"] for d,r in ok)
    st=L.evstats(v,[r["mint"] for d,r in ok]); ci=L.cluster_ci(v,[r["hour"] for d,r in ok])
    cre=L.evstats(v,[r["creator"] for d,r in ok])["max_group_share"]; hr=L.evstats(v,[r["hour"] for d,r in ok])["max_group_share"]
    return dict(signals=len(chosen),usable=len(ok),unavailable=unav,TP_FIRST_rate=states["TP_FIRST"]/len(ok),SL_FIRST_rate=states["SL_FIRST"]/len(ok),timeout_rate=states["TIMEOUT_OTHER"]/len(ok),**{k:st[k] for k in ("EV","median","PF","win_rate","EX_BEST_1PCT")},max_mint_share=st["max_group_share"],max_creator_share=cre,max_hour_share=hr,CI95=ci["CI95"],LCB90=ci["LCB90"],clusters=ci["clusters"],by_landmark=dict(collections.Counter(d["landmark"] for d,r in ok)))
def main():
    t0=time.time(); rows=[json.loads(l) for l in gzip.open(f"{D}/curve2x_rows.jsonl.gz","rt")]; H=L.PRIMARY_H; N=L.PRIMARY_N
    S={s:[r for r in rows if r["split"]==s] for s in ("TRAIN","CAL","VAL","CONF")}; pct=fit_pct(S["TRAIN"]); add_composite(rows,pct)
    R=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",split_counts={s:dict(rows=len(v),mints=len({r["mint"] for r in v})) for s,v in S.items()},primary=dict(H=H,N=N),classes=CLASSES)
    tr=[r for r in S["TRAIN"] if usable(r,N,H)]; ca=[r for r in S["CAL"] if usable(r,N,H)]
    R["usable"]={"TRAIN":len(tr),"CAL":len(ca)}; R["base_rates"]={s:dict(zip(CLASSES,Y_of(v,N,H).mean(0).tolist())) for s,v in (("TRAIN",tr),("CAL",ca))}
    Ytr=Y_of(tr,N,H); Yca=Y_of(ca,N,H); fits={}; cand=[]
    XS={}
    for abl in L.ABLATIONS:
        fl=feats_for(abl)+(["organic_acceleration"] if "ORGANIC_ACCELERATION" in L.ABLATIONS[abl] else []); Xtr,fill=L.X_of(tr,fl); Xca,_=L.X_of(ca,fl,fill); XS[abl]=(fl,fill,Xtr,Xca)
    jobs=[(abl,kind,XS[abl][2],Ytr) for abl in L.ABLATIONS for kind in ("A","B")]+[("M5","C",XS["M5"][2],Ytr)]
    with mp.Pool(4) as P:
        for abl,kind,m in P.imap_unordered(fit_one,jobs): fits[(abl,kind)]=m; print("fit",abl,kind,round(time.time()-t0),"s",flush=True)
    for (abl,kind),m in fits.items():
        fl,fill,Xtr,Xca=XS[abl]; Pca=L.predict(m,Xca); cal=L.fit_vector_scaling(Pca,Yca); Pc=L.apply_cal(cal,Pca)
        top=Pc[:,0]>=min(L.POLICY_GRID["p_tp_min"]); rc=region_cal(Pc,Yca,top)
        cand.append(dict(abl=abl,kind=kind,log_loss=L.log_loss(Pc,Yca),brier=L.brier_mc(Pc,Yca),log_loss_raw=L.log_loss(Pca,Yca),top_gap=rc["gap_tp"] if rc["gap_tp"] is not None else 1.0,top_n=rc["n"],cal=cal,rel_tp=L.reliability(Pc[:,0],Yca[:,0]),rel_sl=L.reliability(Pc[:,1],Yca[:,1]),ece_tp=L.ece_bin(Pc[:,0],Yca[:,0]),ece_sl=L.ece_bin(Pc[:,1],Yca[:,1])))
    base_ll=L.log_loss(np.tile(Ytr.mean(0),(len(ca),1)),Yca); R["cal_baseline_log_loss_train_prior"]=base_ll
    # selectie lexicografica cu tolerante fixe (A/B doar; C = verificare)
    ab=[c for c in cand if c["kind"] in ("A","B")]; best_ll=min(c["log_loss"] for c in ab); s1=[c for c in ab if c["log_loss"]<=best_ll*(1+TOL)]
    best_br=min(c["brier"] for c in s1); s2=[c for c in s1 if c["brier"]<=best_br*(1+TOL)]; best_gap=min(c["top_gap"] for c in s2); s3=[c for c in s2 if c["top_gap"]<=best_gap+0.01]
    # EV mint-level pe CAL (politica de referinta: banda 20-70, p_tp>=0.30, p_sl<=0.40) doar pentru departajare finala
    def ev_cal(c):
        fl,fill,Xtr,Xca=XS[c["abl"]]; m=fits[(c["abl"],c["kind"])]; reg=L.fit_gbm_reg(Xtr,pnl_of(tr,N,H)); rs=regstats_of(reg,Xca,pnl_of(ca,N,H))
        sc=score_rows(ca,Xca,m,c["cal"],reg,rs,N); ch=policy_eval(sc,list(range(len(ca))),dict(band=(20,70),p_tp_min=0.30,p_sl_max=0.40),N,H); st=stats_of(ch,ca,N,H); return st.get("EV") or -1.0
    if len(s3)>1:
        for c in s3: c["ev_cal_ref"]=ev_cal(c)
        sel=max(s3,key=lambda c:c["ev_cal_ref"])
    else: sel=s3[0]
    R["candidates"]=[{k:v for k,v in c.items() if k not in ("cal",)} for c in sorted(cand,key=lambda c:c["log_loss"])]; R["selection"]=dict(stage1=[(c["abl"],c["kind"]) for c in s1],stage2=[(c["abl"],c["kind"]) for c in s2],stage3=[(c["abl"],c["kind"]) for c in s3],selected=(sel["abl"],sel["kind"]),tolerance_rel=TOL)
    abl,kind=sel["abl"],sel["kind"]; fl,fill,Xtr,Xca=XS[abl]; clf=fits[(abl,kind)]; cal=sel["cal"]
    # baseline STATE_HEADROOM (M0, acelasi tip de model) pentru poarta "depaseste baseline"
    base_key=("M0",kind); R["baseline_M0"]={k:v for k,v in next(c for c in cand if c["abl"]=="M0" and c["kind"]==kind).items() if k!="cal"}
    # ---- regressor de PnL cross-fitted (5 fold-uri pe mint, TRAIN) per notional; stats reziduale pe CAL ----
    models={}; 
    for Nn in L.NOTS:
        trn=[r for r in S["TRAIN"] if usable(r,Nn,H)]; can=[r for r in S["CAL"] if usable(r,Nn,H)]; Xn,_=L.X_of(trn,fl,fill); Xc,_=L.X_of(can,fl,fill)
        clf_n=clf if Nn==N else {"A":L.fit_mlogit,"B":L.fit_mgbm}[kind](Xn,Y_of(trn,Nn,H)); cal_n=cal if Nn==N else L.fit_vector_scaling(L.predict(clf_n,Xc),Y_of(can,Nn,H))
        y=pnl_of(trn,Nn,H); mints=np.array([r["mint"] for r in trn]); um=np.unique(mints); rng=np.random.default_rng(5); fold={m:int(rng.integers(0,5)) for m in um}; fo=np.array([fold[m] for m in mints]); oof=np.zeros(len(y))
        for f_ in range(5):
            mr=L.fit_gbm_reg(Xn[fo!=f_],y[fo!=f_]); oof[fo==f_]=L.pred_gbm_reg(mr,Xn[fo==f_])
        reg=L.fit_gbm_reg(Xn,y); rs=regstats_of(reg,Xc,pnl_of(can,Nn,H)); rs["oof_train_r2"]=float(1-((oof-y)**2).mean()/y.var()) if y.var()>0 else None
        models[str(Nn)]=dict(clf=clf_n,cal=cal_n,reg=reg,regstats=rs)
    # ---- grila fixa de politica pe CAL (notional primar); alegere = max LCB90 al EV per mint, cu >= 100 mint-uri ----
    sc_ca=score_rows(ca,Xca,clf,cal,models[str(N)]["reg"],models[str(N)]["regstats"],N); grid=[]
    for band in L.POLICY_GRID["band"]:
        for pm in L.POLICY_GRID["p_tp_min"]:
            for sm in L.POLICY_GRID["p_sl_max"]:
                pol=dict(band=band,p_tp_min=pm,p_sl_max=sm); ch=policy_eval(sc_ca,list(range(len(ca))),pol,N,H); st=stats_of(ch,ca,N,H); grid.append(dict(policy=pol,cal=st))
    ok=[g for g in grid if g["cal"].get("usable",0)>=SPEC["policy"]["min_mints_cal"] and g["cal"].get("EV",-1)>0]
    if ok: best=max(ok,key=lambda g:g["cal"]["LCB90"]); pol=best["policy"]; R["policy_selected"]=pol; R["policy_selected_cal"]=best["cal"]
    else: best=max(grid,key=lambda g:(g["cal"].get("LCB90") or -9)); pol=best["policy"]; R["policy_selected"]=pol; R["policy_selected_cal"]=best["cal"]; R["policy_note"]="NICIO combinatie nu indeplineste >=100 mint-uri pe CAL cu EV>0; se raporteaza cea mai buna dupa LCB90 doar pentru diagnostic; semnalele raman WATCH/REJECT"
    R["policy_grid_cal"]=grid; R["policy_grid_feasible"]=len(ok)
    # ---- INGHETARE model + calibrator + politica ----
    art=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),H=H,N_primary=N,ablation=abl,model_kind=kind,features=fl,fill=fill.tolist(),pct=pct,policy=pol,models=models,classes=CLASSES,grid_feasible=len(ok))
    s=json.dumps(art,sort_keys=True,separators=(",",":"),default=float); mh=hashlib.sha256(s.encode()).hexdigest(); open(f"{OUT}/model_artifact.json","w").write(s); R["model_hash"]=mh; print("FROZEN model_hash",mh,"policy",pol,flush=True)
    # ---- evaluare VAL si CONF o singura data (nivel de mint), per notional, cu stres +5 sloturi si cost +25 %; orizonturi secundare pentru notional primar ----
    EV={}
    for seg in ("VAL","CONF","VAL+CONF"):
        segrows=S["VAL"]+S["CONF"] if seg=="VAL+CONF" else S[seg]; EV[seg]={}
        for Nn in L.NOTS:
            mdl=models[str(Nn)]; rr=[r for r in segrows if r["lab"][key(Nn)].get("status")=="OK"]; X,_=L.X_of(rr,fl,fill); sc=score_rows(rr,X,mdl["clf"],mdl["cal"],mdl["reg"],mdl["regstats"],Nn); ch=policy_eval(sc,list(range(len(rr))),pol,Nn,H)
            res=dict(base=stats_of(ch,rr,Nn,H,"base"),stress_land5=stats_of(ch,rr,Nn,H,"land5"),stress_cost125=stats_of(ch,rr,Nn,H,"cost125"))
            us=[i for d,i in ch if usable(rr[i],Nn,H)]
            if us:
                Pm=np.array([[sc[i]["p_tp"],sc[i]["p_sl"],sc[i]["p_to"]] for i in us]); Ym=Y_of([rr[i] for i in us],Nn,H); res["traded_region_calibration"]=region_cal(Pm,Ym,np.ones(len(us),bool)); res["pred_ev_mean"]=float(np.mean([sc[i]["ev"] for i in us]))
            if Nn==N:
                for Hs in ("5M","30M"):
                    res[f"horizon_{Hs}"]=stats_of(ch,rr,Nn,Hs,"base")
                rr_all=[r for r in rr if usable(r,Nn,H)]; Xa,_=L.X_of(rr_all,fl,fill); Pa=L.apply_cal(mdl["cal"],L.predict(mdl["clf"],Xa)); Ya=Y_of(rr_all,Nn,H)
                res["all_rows_metrics"]=dict(n=len(rr_all),log_loss=L.log_loss(Pa,Ya),brier=L.brier_mc(Pa,Ya),ece_tp=L.ece_bin(Pa[:,0],Ya[:,0]),ece_sl=L.ece_bin(Pa[:,1],Ya[:,1]),rel_tp=L.reliability(Pa[:,0],Ya[:,0]),rel_sl=L.reliability(Pa[:,1],Ya[:,1]),base_rates=dict(zip(CLASSES,Ya.mean(0).tolist())))
                # baseline M0 cu aceeasi politica
                flb=feats_for("M0"); Xb_tr,fillb=L.X_of(tr,flb); Xb,_=L.X_of(rr,flb,fillb); cb=next(c for c in cand if c["abl"]=="M0" and c["kind"]==kind); regb=L.fit_gbm_reg(Xb_tr,pnl_of(tr,N,H)); rsb=regstats_of(regb,L.X_of(ca,flb,fillb)[0],pnl_of(ca,N,H))
                scb=score_rows(rr,Xb,fits[("M0",kind)],cb["cal"],regb,rsb,N); chb=policy_eval(scb,list(range(len(rr))),pol,N,H); res["baseline_M0_same_policy"]=stats_of(chb,rr,N,H)
                res["signals_detail"]=[dict(mint_id=hashlib.sha256(("external-review-v1:"+rr[i]["mint"]).encode()).hexdigest()[:16],landmark=sc[i]["landmark"],day=rr[i]["day"],p_tp=sc[i]["p_tp"],p_sl=sc[i]["p_sl"],p_to=sc[i]["p_to"],p_tp_lcb=sc[i]["p_tp_lcb"],ev=sc[i]["ev"],ev_lcb=sc[i]["ev_lcb"],n_similar=sc[i]["n_similar"],state=rr[i]["lab"][key(Nn)][H]["state"],pnl=rr[i]["lab"][key(Nn)][H]["pnl"],venue=rr[i]["lab"][key(Nn)][H]["venue"],label_kind=rr[i]["lab"][key(Nn)][H]["label_kind"]) for d,i in ch]
            EV[seg][str(Nn)]=res
    R["evaluation"]=EV
    # ---- ablatiuni raportate pe VAL+CONF (log loss cu calibratorul din CAL), doar pentru raport ----
    abl_rep={}
    vc=[r for r in S["VAL"]+S["CONF"] if usable(r,N,H)]; Yv=Y_of(vc,N,H)
    for (a,k),m in fits.items():
        flx,fillx,_,_=XS[a]; Xv,_=L.X_of(vc,flx,fillx); c=next(c for c in cand if c["abl"]==a and c["kind"]==k); Pv=L.apply_cal(c["cal"],L.predict(m,Xv)); abl_rep[f"{a}/{k}"]=dict(log_loss=L.log_loss(Pv,Yv),brier=L.brier_mc(Pv,Yv),ece_tp=L.ece_bin(Pv[:,0],Yv[:,0]))
    R["ablations_val_conf"]=abl_rep; R["ablations_val_conf_prior"]=L.log_loss(np.tile(Ytr.mean(0),(len(vc),1)),Yv)
    # ---- poarta PAPER_CANDIDATE (regula 28) ----
    P25=EV; g={}
    def seg(sn,Nn=str(N)): return P25[sn][Nn]["base"]
    v,c_,a_=seg("VAL"),seg("CONF"),seg("VAL+CONF"); G=SPEC["gates"]
    g["min_mints_total_100"]=a_.get("usable",0)>=100; g["min_mints_val_30"]=v.get("usable",0)>=30; g["min_mints_conf_30"]=c_.get("usable",0)>=30
    g["ev_positive_val"]=(v.get("EV") or -1)>0; g["ev_positive_conf"]=(c_.get("EV") or -1)>0; g["ci95_lower_positive"]=((a_.get("CI95") or (-1,0))[0])>0; g["pf_ge_1_5"]=(a_.get("PF") or 0)>=1.5
    g["ex_best_1pct_positive"]=(a_.get("EX_BEST_1PCT") or -1)>0; g["no_concentration_gt_20pct"]=all((a_.get(k) or 1)<=0.20 for k in ("max_mint_share","max_creator_share","max_hour_share"))
    g["stress_land5_ev_positive"]=(P25["VAL+CONF"][str(N)]["stress_land5"].get("EV") or -1)>0; g["stress_cost125_ev_positive"]=(P25["VAL+CONF"][str(N)]["stress_cost125"].get("EV") or -1)>0
    trc=P25["VAL+CONF"][str(N)].get("traded_region_calibration") or {}; g["calibration_gap_le_5pp"]=(trc.get("gap_tp") is not None and trc["gap_tp"]<=0.05)
    bl=P25["VAL+CONF"][str(N)].get("baseline_M0_same_policy") or {}; g["beats_state_headroom_baseline"]=((a_.get("EV") or -1)>(bl.get("EV") or -1)) if bl.get("usable") else ((a_.get("EV") or -1)>0)
    g["positive_after_mint_dedup"]=g["ev_positive_val"] and g["ev_positive_conf"]   # evaluarea este deja la nivel de mint (o decizie per mint)
    g["policy_feasible_on_cal"]=len(ok)>0
    R["gates"]=g; R["FINAL_VERDICT"]="PAPER_CANDIDATE" if all(g.values()) else "NO_VERIFIED_EDGE"; R["runtime_s"]=round(time.time()-t0,1)
    json.dump(R,open(f"{OUT}/results.json","w"),indent=1,default=float); print(json.dumps(dict(selected=R["selection"]["selected"],policy=pol,gates=g,verdict=R["FINAL_VERDICT"],val=v,conf=c_),default=float)[:3000]); print("MODEL_DONE",flush=True)
def regstats_of(reg,Xc,yc):
    p=L.pred_gbm_reg(reg,Xc); edges=np.quantile(p,np.linspace(0,1,11)[1:-1]).tolist(); dec=np.clip(np.searchsorted(edges,p,side="right"),0,9); sd=[]; n=[]
    for d in range(10):
        m=dec==d; n.append(int(m.sum())); sd.append(float((p[m]-yc[m]).std()) if m.sum()>=5 else float((p-yc).std()))
    return dict(edges=edges,sd=sd,n=n,resid_sd_all=float((p-yc).std()),cal_r2=float(1-((p-yc)**2).mean()/yc.var()) if yc.var()>0 else None)
if __name__=="__main__": main()
