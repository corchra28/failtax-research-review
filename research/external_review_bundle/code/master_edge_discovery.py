"""MASTER EDGE — Lane M (transfer de inventar intre cohorte de portofele dupa migrare). Descoperire inghetata conform research/master_selected_lanes_frozen.json.
Etape: A) trasaturi point-in-time (ts < D) + executii exacte (intrare D+2 s, TP+100/SL-30/300 s la stari de final de slot); B) screening structural pe DEV (44 celule);
C) model L2-logistic per orizont (fit in fold-uri) -> PnL la top-20 % pe VAL; D) reguli (o celula per orizont) pe VAL; E) distilare <=1 candidat -> AUDIT o singura data + stres + bankroll;
F) corectie globala Holm + reality check prin permutari pe blocuri. Toate trialurile in research/master_edge_trials.csv. Zero date noi."""
import gzip,json,math,os,sys,csv,time,bisect,hashlib,random,collections,statistics as S
import numpy as np
SCR="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad"; CACHE=f"{SCR}/derived/m_pools.jsonl.gz"
FR=json.load(open("research/master_selected_lanes_frozen.json")); DZ=FR["design"]; REG=json.load(open("research/master_feature_registry.json"))
SOL_USD=100.0; N_USD=25.0; HORIZONS=DZ["decision_times_s"]; PRIO_USD=0.01; OPEN_RQ=67405853768
PRIMARY={"F1_T0_HOLDER_LIQUIDATION":"t0h_sell_share","F2_FRESH_BUYER_ACCUMULATION":"fresh_share","F3_RETURNING_BUYERS":"ret_buy_share","F4_FLOW_PERSISTENCE":"net_quote_flow","F5_TRADE_SIZE_STRUCTURE":"size_top1_share","F6_SAME_SLOT_BURSTS":"burst_event_share","F7_FLOW_PRICE_RESPONSE":"impact_per_sol","F8_DRAWDOWN_RECOVERY":"max_dd_bp","F9_RESERVE_TRAJECTORY":"n_events","F10_CREATOR_ACTIVITY":"creator_t0_share","F11_CURVE_CONTEXT":"curve_duration_s"}
ALLF=["t0h_sell_share","t0h_sold_frac","t0h_sellers_n","fresh_buyers_n","fresh_buy_quote","fresh_share","ret_buy_share","ret_buyers_n","buy_ratio","net_quote_flow","last5_buy_share","sign_runs","size_median_sol","size_top1_share","repeat_size_share","max_wallets_per_slot","burst_event_share","px_ret_bp","impact_per_sol","absorption","max_dd_bp","recovery_bp","rq_change_sol","n_events","events_per_s","creator_t0_share","creator_sold_pre_D","creator_sold_on_curve","curve_duration_s","curve_trades_n","curve_unique_buyers"]
BLACK=REG["blacklist_substrings"]
def guard_feature_names(names):
    bad=[n for n in names if any(b in n.lower() for b in BLACK)]
    if bad: raise ValueError(f"LEAKAGE_GUARD: trasaturi interzise {bad}")
guard_feature_names(ALLF)
# ---------------- executie exacta (semantica validata in evaluarea sigilata) ----------------
def exec_buy(rb,rq,vq,q,lp,pr,cc,s=1.0):
    tot=int(round((lp+pr+cc)*s)); q2=q*10000//(10000+tot); lpf=q2*int(round(lp*s))//10000; return rb*q2//(rq+vq+q2),q2+lpf
def exec_sell(rb,rq,vq,b,lp,pr,cc,s=1.0):
    if rb<=0 or b<=0: return 0
    brut=(rq+vq)*b//(rb+b); u=brut-brut*int(round(lp*s))//10000-brut*int(round((pr+cc)*s))//10000; return min(u,max(0,rq))
def price(rb,rq,vq): return (rq+vq)/rb
def t0_holders(x):
    bal=collections.Counter(); cb=collections.Counter(); cs=collections.Counter(); buyers=set()
    for tr in x["curve"]:
        slot,seq,k,sol,tok,isb,user,rsol,ts,t=tr
        if isb: bal[user]+=tok; cb[user]+=tok; buyers.add(user)
        else: bal[user]-=tok; cs[user]+=tok
    hold={u:b for u,b in bal.items() if b>0}; return hold,sum(hold.values()),cb,cs,len(buyers)
def state_at(x,X):
    """post-starea de dupa toate evenimentele cu ts <= X (evenimentele din secunda X sunt considerate INAINTEA noastra: pesimist)."""
    ev=x["ev"]; i=bisect.bisect_right(x["_ts"],X)-1
    if i<0: e=ev[0]; return e[6],e[7],e[12],e[13],e[14],i
    e=ev[i]; return e[8],e[9],e[12],e[13],e[14],i
def features(x,h,hold,tot,cb,cs,nbuyers):
    D=x["T0_ts"]+h; vq=x["vq"]; ev=x["ev"]; n=bisect.bisect_left(x["_ts"],D); pre=ev[:n]; f={}; creator=x["creator"]
    e0=ev[0]; p_open=price(e0[6],e0[7],vq)
    f["n_events"]=n; f["events_per_s"]=n/h; f["max_ts_used"]=(pre[-1][1] if pre else None)
    f["curve_duration_s"]=x["complete_ts"]-x["create_t"]; f["curve_trades_n"]=len(x["curve"]); f["curve_unique_buyers"]=nbuyers
    f["creator_t0_share"]=(hold.get(creator,0)/tot) if tot>0 else 0.0; f["creator_sold_on_curve"]=(cs.get(creator,0)/cb[creator]) if cb.get(creator,0)>0 else 0.0
    f["creator_sold_pre_D"]=1.0 if any((e[5]==0 and e[15]==creator) for e in pre) else 0.0
    if n==0:
        for k in ("t0h_sell_share","t0h_sold_frac","t0h_sellers_n","fresh_buyers_n","fresh_buy_quote","fresh_share","ret_buy_share","ret_buyers_n","buy_ratio","net_quote_flow","last5_buy_share","sign_runs","size_median_sol","size_top1_share","repeat_size_share","max_wallets_per_slot","burst_event_share","px_ret_bp","impact_per_sol","absorption","max_dd_bp","recovery_bp"): f[k]=None
        f["rq_change_sol"]=0.0; return f
    qb=sum(e[11] for e in pre if e[5]); qs=sum(e[11] for e in pre if not e[5]); qt=qb+qs
    t0_sell_q=sum(e[11] for e in pre if not e[5] and e[15] in hold); t0_sell_tok=sum(e[10] for e in pre if not e[5] and e[15] in hold)
    f["t0h_sell_share"]=t0_sell_q/qt if qt>0 else 0.0; f["t0h_sold_frac"]=min(1.0,t0_sell_tok/tot) if tot>0 else 0.0; f["t0h_sellers_n"]=len({e[15] for e in pre if not e[5] and e[15] in hold})
    fresh={e[15] for e in pre if e[5] and e[15] not in hold}; fq=sum(e[11] for e in pre if e[5] and e[15] not in hold)
    f["fresh_buyers_n"]=len(fresh); f["fresh_buy_quote"]=fq/1e9; f["fresh_share"]=fq/qb if qb>0 else 0.0
    rq_=sum(e[11] for e in pre if e[5] and e[15] in hold); f["ret_buy_share"]=rq_/qb if qb>0 else 0.0; f["ret_buyers_n"]=len({e[15] for e in pre if e[5] and e[15] in hold})
    f["buy_ratio"]=sum(1 for e in pre if e[5])/n; f["net_quote_flow"]=(qb-qs)/1e9; last=pre[-5:]; f["last5_buy_share"]=sum(1 for e in last if e[5])/len(last)
    signs=[1 if e[5] else -1 for e in pre]; f["sign_runs"]=sum(1 for a,b in zip(signs,signs[1:]) if a!=b)
    sizes=[e[11] for e in pre]; f["size_median_sol"]=S.median(sizes)/1e9; f["size_top1_share"]=max(sizes)/qt if qt>0 else 0.0
    cnt=collections.Counter(sizes); f["repeat_size_share"]=sum(c for s_,c in cnt.items() if c>=2)/n
    per_slot=collections.defaultdict(set); [per_slot[e[2]].add(e[15]) for e in pre]; f["max_wallets_per_slot"]=max(len(v) for v in per_slot.values()); bursty={s_ for s_,v in per_slot.items() if len(v)>=3}; f["burst_event_share"]=sum(1 for e in pre if e[2] in bursty)/n
    pxs=[price(e[8],e[9],vq) for e in pre]; pD=pxs[-1]; pmin=min(pxs+[p_open]); f["px_ret_bp"]=(pD/p_open-1)*1e4; f["max_dd_bp"]=(pmin/p_open-1)*1e4; f["recovery_bp"]=(pD/pmin-1)*1e4
    f["impact_per_sol"]=f["px_ret_bp"]/max(0.01,abs(f["net_quote_flow"])); f["absorption"]=(qs/1e9)/max(1.0,-f["max_dd_bp"]); f["rq_change_sol"]=(pre[-1][9]-OPEN_RQ)/1e9
    return f
def simulate(x,h,delay=2.0,N=N_USD,s=1.0,policy=("TPSL",1.0,0.30,300),entry_time=None):
    vq=x["vq"]; ev=x["ev"]; X=(x["T0_ts"]+h+delay) if entry_time is None else entry_time
    rb,rq,lp,pr,cc,i=state_at(x,X); q=int(N/SOL_USD*1e9); tok,qn=exec_buy(rb,rq,vq,q,lp,pr,cc,s)
    if tok<=0: return None
    def liq(e): rb2=e[8]-tok; rq2=e[9]+qn; return (exec_sell(rb2,rq2,vq,tok,lp if e is None else e[12],e[13],e[14],s)/1e9*SOL_USD) if rb2>0 else 0.0
    kind,a,b,TO=policy; deadline=X+TO; out=None
    if kind=="TPSL":
        TP=N*(1+a); SL=N*(1-b); j=i+1
        while j<len(ev) and ev[j][1]<=deadline:
            sl_=ev[j][2]; k=j
            while k+1<len(ev) and ev[k+1][2]==sl_ and ev[k+1][1]<=deadline: k+=1
            V=liq(ev[k])
            if V<=SL: out=("SL",V,ev[k][1]); break
            if V>=TP: out=("TP",V,ev[k][1]); break
            j=k+1
    if out is None:
        rb3,rq3,lp3,pr3,cc3,i3=state_at(x,deadline); rb2=rb3-tok
        if i3<0: rb2=rb-tok; rq2=rq+qn
        else: rq2=rq3+qn
        V=(exec_sell(rb2,rq2,vq,tok,lp3,pr3,cc3,s)/1e9*SOL_USD) if rb2>0 else 0.0; out=("TIMEOUT",V,deadline)
    pnl=out[1]-N-2*PRIO_USD; return dict(pnl=pnl,ret=pnl/N,exit_kind=out[0],entry_ts=X,exit_ts=out[2],hold_s=out[2]-X,tp=1 if out[0]=="TP" else 0)
# ---------------- statistici ----------------
def stats(rows,key="pnl",N=N_USD):
    v=[r for r in rows if r.get(key) is not None]
    if not v: return None
    pn=sorted([r[key] for r in v],reverse=True); n=len(pn); w=[a for a in pn if a>0]; l=[a for a in pn if a<=0]; gp=sum(w) or 1e-9
    st=dict(N=n,EV=sum(pn)/n,EV_pct=100*sum(pn)/n/N,median=S.median(pn),PF=(sum(w)/abs(sum(l))) if l and sum(l)<0 else None,P_gt0=len(w)/n,avg_win=(sum(w)/len(w)) if w else None,avg_loss=(sum(l)/len(l)) if l else None,
        EX_BEST_1=sum(pn[1:])/max(1,n-1),EX_BEST_3=sum(pn[3:])/max(1,n-3),EX_BEST_1PCT=sum(pn[max(1,n//100):])/max(1,n-max(1,n//100)),top1pct_contrib=sum(pn[:max(1,n//100)])/gp,tp_rate=(sum(r.get("tp",0) for r in v)/n))
    hrs=collections.defaultdict(list); [hrs[r["hour"]].append(r[key]) for r in v]; st["hours_pos"]=sum(1 for a in hrs.values() if sum(a)>0); st["hours_n"]=len(hrs)
    days=collections.defaultdict(list); [days[r["day"]].append(r[key]) for r in v]; st["days_EV"]={d:sum(a)/len(a) for d,a in days.items()}; st["days_pos"]=sum(1 for a in days.values() if sum(a)>0)
    seq=sorted(v,key=lambda r:r["T0"]); eq=pk=dd=0.0
    for r in seq: eq+=r[key]; pk=max(pk,eq); dd=min(dd,eq-pk)
    st["MAX_DD"]=dd; st["chrono_quartile_EV"]=[(sum(r[key] for r in seq[i*n//4:(i+1)*n//4])/max(1,len(seq[i*n//4:(i+1)*n//4]))) for i in range(4)]
    rng=random.Random(11); groups=list(hrs.values()); bs=[]
    for _ in range(1000):
        flat=[a for g in [rng.choice(groups) for _ in groups] for a in g]; bs.append(sum(flat)/len(flat))
    bs.sort(); st["EV_CI95_cluster_hour"]=(bs[25],bs[974]); st["p_boot_EV_le_0"]=sum(1 for b in bs if b<=0)/len(bs); st["hour_dep"]=max((sum(a) for a in hrs.values()),default=0)/gp if gp>0 else None
    return st
def diff_p(a,b,rng_seed=5):
    """p bilateral bootstrap (cluster ora) pentru EV(a)-EV(b)."""
    if not a or not b: return None,None
    d=S.mean([r["pnl"] for r in a])-S.mean([r["pnl"] for r in b]); rng=random.Random(rng_seed)
    ha=collections.defaultdict(list); [ha[r["hour"]].append(r["pnl"]) for r in a]; hb=collections.defaultdict(list); [hb[r["hour"]].append(r["pnl"]) for r in b]
    ga,gb=list(ha.values()),list(hb.values()); ds=[]
    for _ in range(600):
        fa=[v for g in [rng.choice(ga) for _ in ga] for v in g]; fb=[v for g in [rng.choice(gb) for _ in gb] for v in g]; ds.append(S.mean(fa)-S.mean(fb))
    sd=S.pstdev(ds) or 1e-9; z=d/sd; p=2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2)))); return d,p
# ---------------- model L2 (fit doar pe antrenare) ----------------
def X_of(rows,names,fill):
    X=np.array([[ (r["f"][k] if r["f"].get(k) is not None else fill[k]) for k in names] for r in rows],dtype=float); return np.sign(X)*np.log1p(np.abs(X))
def fit(X,y,l2=1.0,it=2000,lr=0.05):
    mu,sd=X.mean(0),X.std(0)+1e-9; Xs=(X-mu)/sd; w=np.zeros(Xs.shape[1]); p0=min(max(y.mean(),1e-4),1-1e-4); b=math.log(p0/(1-p0)); n=len(y)
    for _ in range(it):
        p=1/(1+np.exp(-(Xs@w+b))); g=Xs.T@(p-y)/n+l2*w/n; w-=lr*g; b-=lr*(p-y).mean()
    return (w,b,mu,sd)
def predict(m,X): w,b,mu,sd=m; return 1/(1+np.exp(-(((X-mu)/sd)@w+b)))
def pr_auc(y,s):
    if y.sum()==0: return 0.0
    o=np.argsort(-s); y=y[o]; tp=np.cumsum(y); fp=np.cumsum(1-y); prec=tp/(tp+fp); rec=tp/y.sum(); return float(np.trapezoid(prec,rec))
def holm(ps):
    idx=sorted(range(len(ps)),key=lambda i:(ps[i] if ps[i] is not None else 1.0)); m=len(ps); adj=[None]*m; cur=0.0
    for rank,i in enumerate(idx):
        p=ps[i] if ps[i] is not None else 1.0; cur=max(cur,min(1.0,(m-rank)*p)); adj[i]=cur
    return adj
TRIALS=[]
def trial(**kw):
    kw.setdefault("ts",time.strftime("%H:%M:%S")); TRIALS.append(kw); return kw
# ================= MAIN =================
def main():
    man=json.load(open(f"{SCR}/derived/m_cache_manifest.json")); assert man["matches_sealed_population"], "populatia nu corespunde manifestului sigilat"
    pools=[]; rows={h:[] for h in HORIZONS}; t_start=time.time()
    with gzip.open(CACHE,"rt") as f:
        for line in f:
            x=json.loads(line); x["_ts"]=[e[1] for e in x["ev"]]; hold,tot,cb,cs,nb=t0_holders(x)
            base=dict(mint=x["mint"],day=x["day"],T0=x["T0"],hour=int((x["T0"]-1788220800)//3600),n_ev_total=len(x["ev"]))
            for h in HORIZONS:
                fx=features(x,h,hold,tot,cb,cs,nb); r=dict(base); r["h"]=h; r["f"]=fx; r["D"]=x["T0_ts"]+h
                prim=simulate(x,h); r["prim"]=prim
                r["sec"]={"TP50_SL20":simulate(x,h,policy=("TPSL",0.5,0.2,300)),"FIX60":simulate(x,h,policy=("FIX",0,0,60)),"FIX180":simulate(x,h,policy=("FIX",0,0,180))}
                r["lat"]={d:simulate(x,h,delay=d) for d in (0.8,1.2,5.0)}; r["cost"]={s:simulate(x,h,s=s) for s in (1.25,1.5)}; r["notional"]={n:simulate(x,h,N=n) for n in (10,50)}
                rng=random.Random(int(hashlib.sha256(x["mint"].encode()).hexdigest()[:8],16)); r["placebo"]=simulate(x,h,entry_time=x["T0_ts"]+h+2+rng.uniform(5,120))
                rows[h].append(r)
            pools.append(x["mint"])
    n=len(pools); order=sorted(range(n),key=lambda i:rows[HORIZONS[0]][i]["T0"]); part={}
    for rank,i in enumerate(order): part[pools[i]]="DEV" if rank<int(0.4*n) else ("VAL" if rank<int(0.7*n) else "AUDIT")
    for h in HORIZONS:
        for r in rows[h]: r["part"]=part[r["mint"]]; r["pnl"]=r["prim"]["pnl"] if r["prim"] else None; r["tp"]=r["prim"]["tp"] if r["prim"] else 0
    # tabelul de trasaturi/outcome-uri (pentru testele de scurgere)
    with gzip.open(f"{SCR}/derived/m_features.jsonl.gz","wt") as f:
        for h in HORIZONS:
            for r in rows[h]: f.write(json.dumps(dict(mint=r["mint"],h=h,part=r["part"],day=r["day"],T0=r["T0"],hour=r["hour"],D=r["D"],f=r["f"],prim=r["prim"],pnl=r["pnl"],tp=r["tp"]))+"\n")
    R=dict(N_pools=n,partitions=dict(collections.Counter(part.values())),runtime_features_s=round(time.time()-t_start,1))
    R["baseline_unconditional"]={h:{p:stats([r for r in rows[h] if r["part"]==p and r["prim"]]) for p in ("DEV","VAL","AUDIT")} for h in HORIZONS}
    # ---------- B) screening pe DEV (44 celule) ----------
    screen=[]; pvals=[]; labels=[]
    for h in HORIZONS:
        dev=[r for r in rows[h] if r["part"]=="DEV" and r["prim"]]; allev=S.mean([r["pnl"] for r in dev])
        for fam,fname in PRIMARY.items():
            d=[r for r in dev if r["f"].get(fname) is not None]; und=[r for r in dev if r["f"].get(fname) is None]
            if len(d)<30: screen.append(dict(h=h,family=fam,feature=fname,N=len(d),note="insuficient")); pvals.append(None); labels.append((h,fam)); continue
            vals=sorted(r["f"][fname] for r in d); q1,q2=vals[len(vals)//3],vals[2*len(vals)//3]
            lo=[r for r in d if r["f"][fname]<=q1]; hi=[r for r in d if r["f"][fname]>q2]; mid=[r for r in d if q1<r["f"][fname]<=q2]
            if len(lo)<5 or len(hi)<5: screen.append(dict(h=h,family=fam,feature=fname,N=len(d),N_undefined=len(und),q1=q1,q2=q2,note="tercile degenerate (trasatura aproape constanta)")); pvals.append(None); labels.append((h,fam)); continue
            dif,p=diff_p(hi,lo); cell=dict(h=h,family=fam,feature=fname,N=len(d),N_undefined=len(und),q1=q1,q2=q2,EV_lo=S.mean([r["pnl"] for r in lo]),EV_mid=(S.mean([r["pnl"] for r in mid]) if mid else None),EV_hi=S.mean([r["pnl"] for r in hi]),EV_undefined=(S.mean([r["pnl"] for r in und]) if und else None),EV_all=allev,diff_hi_lo=dif,p_raw=p,N_lo=len(lo),N_hi=len(hi))
            best_side="hi" if cell["EV_hi"]>=cell["EV_lo"] else "lo"; cell["best_side"]=best_side; cell["best_EV"]=max(cell["EV_hi"],cell["EV_lo"]); cell["best_minus_all"]=cell["best_EV"]-allev
            screen.append(cell); pvals.append(p); labels.append((h,fam))
        trial(stage="S1_screen",lane="M",horizon=h,config=f"tercile screen x11 familii",partition="DEV",N=len(dev),EV=None,PF=None,note="descriptiv; 11 celule")
    R["screening"]=screen
    # ---------- C) model L2 per orizont ----------
    models={}
    for h in HORIZONS:
        dev=[r for r in rows[h] if r["part"]=="DEV" and r["prim"]]; val=[r for r in rows[h] if r["part"]=="VAL" and r["prim"]]
        fill={k:(S.median([r["f"][k] for r in dev if r["f"].get(k) is not None]) if any(r["f"].get(k) is not None for r in dev) else 0.0) for k in ALLF}
        Xd=X_of(dev,ALLF,fill); yd=np.array([float(r["tp"]) for r in dev]); dev_sorted=sorted(range(len(dev)),key=lambda i:dev[i]["T0"]); K=5; cv_s=np.zeros(len(dev))
        for k in range(K):
            te=set(dev_sorted[k*len(dev)//K:(k+1)*len(dev)//K]); tr=[i for i in range(len(dev)) if i not in te]; te=sorted(te)
            if yd[tr].sum()==0: cv_s[te]=yd[tr].mean(); continue
            m=fit(Xd[tr],yd[tr]); cv_s[te]=predict(m,Xd[te])
        cv=dict(pr_auc=pr_auc(yd,cv_s),pr_auc_random=float(yd.mean()),brier=float(np.mean((cv_s-yd)**2)),brier_base=float(yd.mean()*(1-yd.mean())))
        thr=float(np.quantile(cv_s,0.8)); top=[dev[i] for i in range(len(dev)) if cv_s[i]>=thr]; cv["EV_top20_cv"]=S.mean([r["pnl"] for r in top]) if top else None; cv["lift_top20_cv"]=(np.mean([r["tp"] for r in top])/max(1e-9,yd.mean())) if top else None
        m=fit(Xd,yd); sd_=predict(m,Xd); thr=float(np.quantile(sd_,0.8)); Xv=X_of(val,ALLF,fill); sv=predict(m,Xv); sel=[val[i] for i in range(len(val)) if sv[i]>=thr]; comp=[val[i] for i in range(len(val)) if sv[i]<thr]
        stv=stats(sel); d_,p=diff_p(sel,comp); yv=np.array([float(r["tp"]) for r in val])
        imp={}; 
        for j,k in enumerate(ALLF):
            Xp=Xv.copy(); rng=np.random.default_rng(1); Xp[:,j]=rng.permutation(Xp[:,j]); imp[k]=float(pr_auc(yv,sv)-pr_auc(yv,predict(m,Xp)))
        models[h]=dict(cv=cv,VAL=dict(N_selected=len(sel),stats=stv,complement=stats(comp),diff_p=p,pr_auc=pr_auc(yv,sv),pr_auc_random=float(yv.mean()),brier=float(np.mean((sv-yv)**2)),calibration=[(float(sv[(sv>=a)&(sv<b)].mean()) if ((sv>=a)&(sv<b)).any() else None,float(yv[(sv>=a)&(sv<b)].mean()) if ((sv>=a)&(sv<b)).any() else None,int(((sv>=a)&(sv<b)).sum())) for a,b in ((0,.02),(.02,.05),(.05,.1),(.1,.2),(.2,1.01))]),threshold=thr,perm_importance_top=sorted(imp.items(),key=lambda kv:-abs(kv[1]))[:6],weights=dict(zip(ALLF,[float(w) for w in m[0]])))
        pvals.append(p); labels.append((h,"MODEL"))
        trial(stage="S2_model",lane="M",horizon=h,config="L2-logistic 31 trasaturi, prag top-20 % DEV",partition="VAL",N=len(sel),EV=(stv or {}).get("EV"),PF=(stv or {}).get("PF"),median=(stv or {}).get("median"),p_raw=p,note=f"CV PR-AUC {cv['pr_auc']:.3f} vs {cv['pr_auc_random']:.3f}")
    R["models"]=models
    # ---------- D) reguli pe VAL: celula cea mai buna per orizont (fixata pe DEV) ----------
    rules={}
    for h in HORIZONS:
        cells=[c for c in screen if c["h"]==h and "best_EV" in c]
        if not cells: continue
        best=max(cells,key=lambda c:c["best_minus_all"]); fname=best["feature"]; side=best["best_side"]
        def sel_rule(r,best=best,fname=fname,side=side):
            v=r["f"].get(fname)
            if v is None: return False
            return v>best["q2"] if side=="hi" else v<=best["q1"]
        val=[r for r in rows[h] if r["part"]=="VAL" and r["prim"]]; sel=[r for r in val if sel_rule(r)]; comp=[r for r in val if not sel_rule(r)]
        st=stats(sel); d_,p=diff_p(sel,comp); dev_sel=[r for r in rows[h] if r["part"]=="DEV" and r["prim"] and sel_rule(r)]
        rules[h]=dict(feature=fname,side=side,q1=best["q1"],q2=best["q2"],family=best["family"],DEV=stats(dev_sel),VAL=st,VAL_complement=stats(comp),diff_p=p,rule_text=f"h={h}s: {fname} {'>' if side=='hi' else '<='} {best['q2'] if side=='hi' else best['q1']:.4g} (tercila {side} fixata pe DEV)")
        pvals.append(p); labels.append((h,"RULE"))
        trial(stage="S3_rule",lane="M",horizon=h,config=rules[h]["rule_text"],partition="VAL",N=len(sel),EV=(st or {}).get("EV"),PF=(st or {}).get("PF"),median=(st or {}).get("median"),p_raw=p,note=f"DEV EV {rules[h]['DEV']['EV'] if rules[h]['DEV'] else None}")
    R["rules"]=rules
    # ---------- F) corectie globala ----------
    adj=holm(pvals); R["multiple_testing"]=dict(TOTAL_TRIALS=len(TRIALS),EFFECTIVE_TRIALS=len(pvals),items=[dict(label=f"{l[0]}s/{l[1]}",p_raw=p,p_holm=a) for l,p,a in zip(labels,pvals,adj)],method="Holm pe toate celulele de screening + modele + reguli (o singura familie de testare pentru intregul program)")
    # reality check: permutari pe blocuri (blocuri de 50 pool-uri DEV cronologice) ale maximului |z| pe cele 44 de celule
    def zcells(rows_by_h,perm=None):
        zs=[]
        for h in HORIZONS:
            dev=[r for r in rows_by_h[h] if r["part"]=="DEV" and r["prim"]]; dev=sorted(dev,key=lambda r:r["T0"]); pn=[r["pnl"] for r in dev]
            if perm is not None:
                pn=list(pn)
                for b0 in range(0,len(pn),50): blk=pn[b0:b0+50]; perm.shuffle(blk); pn[b0:b0+50]=blk
            for fam,fname in PRIMARY.items():
                idx=[i for i,r in enumerate(dev) if r["f"].get(fname) is not None]
                if len(idx)<30: continue
                vals=sorted(dev[i]["f"][fname] for i in idx); q1,q2=vals[len(vals)//3],vals[2*len(vals)//3]
                lo=[pn[i] for i in idx if dev[i]["f"][fname]<=q1]; hi=[pn[i] for i in idx if dev[i]["f"][fname]>q2]
                if len(lo)<5 or len(hi)<5: continue
                se=math.sqrt(np.var(lo)/len(lo)+np.var(hi)/len(hi)) or 1e-9; zs.append(abs(S.mean(hi)-S.mean(lo))/se)
        return max(zs) if zs else 0.0
    zobs=zcells(rows); rng=random.Random(2026); zperm=[zcells(rows,rng) for _ in range(300)]; R["reality_check"]=dict(max_abs_z_observed=zobs,p_block_permutation=sum(1 for z in zperm if z>=zobs)/len(zperm),n_perm=300,block=50)
    # ---------- E) distilare: candidat <= 1 ----------
    cands=[(h,ru) for h,ru in rules.items() if ru["DEV"] and ru["VAL"] and ru["DEV"]["EV"]>0 and ru["VAL"]["EV"]>0 and ru["VAL"]["N"]>=30 and (ru["VAL"]["PF"] or 0)>1]
    R["candidate_exists"]=bool(cands)
    if cands: h,ru=max(cands,key=lambda t:t[1]["VAL"]["EV"]); R["candidate_basis"]="regula cu EV>0 pe DEV si VAL (cel mai mare EV VAL)"
    else:
        h,ru=max(rules.items(),key=lambda t:(t[1]["VAL"]["EV"] if t[1]["VAL"] else -1e9)); R["candidate_basis"]="NICIUN candidat; regula cu cel mai mare EV VAL evaluata pe AUDIT doar ca DIAGNOSTIC"
    fname,side,q1,q2=ru["feature"],ru["side"],ru["q1"],ru["q2"]
    def sel_c(r): v=r["f"].get(fname); return v is not None and (v>q2 if side=="hi" else v<=q1)
    ood=[r for r in rows[h] if r["part"]!="DEV" and r["prim"]]; aud=[r for r in rows[h] if r["part"]=="AUDIT" and r["prim"]]
    sel_ood=[r for r in ood if sel_c(r)]; sel_aud=[r for r in aud if sel_c(r)]; comp_ood=[r for r in ood if not sel_c(r)]
    C=dict(horizon=h,rule=ru["rule_text"],family=ru["family"],clauses=[f"orizont {h} s",f"{fname} {'>' if side=='hi' else '<='} {(q2 if side=='hi' else q1):.4g}","intrare D+2 s $25","TP+100/SL-30/300 s"],AUDIT=stats(sel_aud),AUDIT_complement=stats([r for r in aud if not sel_c(r)]),OOD_VAL_AUDIT=stats(sel_ood),OOD_complement=stats(comp_ood),OOD_diff_p=diff_p(sel_ood,comp_ood)[1])
    trial(stage="S4_candidate_AUDIT",lane="M",horizon=h,config=ru["rule_text"],partition="AUDIT",N=len(sel_aud),EV=(C["AUDIT"] or {}).get("EV"),PF=(C["AUDIT"] or {}).get("PF"),median=(C["AUDIT"] or {}).get("median"),p_raw=C["OOD_diff_p"],note=R["candidate_basis"])
    # stres pe OOD (VAL+AUDIT)
    def st_of(key_fn): return stats([dict(r,pnl=key_fn(r)["pnl"],tp=key_fn(r)["tp"]) for r in sel_ood if key_fn(r)])
    C["stress"]=dict(latency={"+0.8s":st_of(lambda r:r["lat"][0.8]),"+1.2s":st_of(lambda r:r["lat"][1.2]),"+2s":C["OOD_VAL_AUDIT"],"+5s":st_of(lambda r:r["lat"][5.0])},cost={"x1.0":C["OOD_VAL_AUDIT"],"x1.25":st_of(lambda r:r["cost"][1.25]),"x1.5":st_of(lambda r:r["cost"][1.5])},notional={"$10":stats([dict(r,pnl=r["notional"][10]["pnl"],tp=r["notional"][10]["tp"]) for r in sel_ood if r["notional"][10]],N=10),"$25":C["OOD_VAL_AUDIT"],"$50":stats([dict(r,pnl=r["notional"][50]["pnl"],tp=r["notional"][50]["tp"]) for r in sel_ood if r["notional"][50]],N=50)},
        placebo_random_entry=stats([dict(r,pnl=r["placebo"]["pnl"],tp=r["placebo"]["tp"]) for r in sel_ood if r["placebo"]]),no_suspicious=stats([r for r in sel_ood if (r["f"].get("burst_event_share") or 0)<0.5]),
        leave_one_day_out={d:stats([r for r in sel_ood if r["day"]!=d]) for d in sorted({r["day"] for r in sel_ood})},leave_one_hour_out_min_EV=(min((stats([r for r in sel_ood if r["hour"]!=hh]) or {"EV":0})["EV"] for hh in {r["hour"] for r in sel_ood}) if sel_ood else None))
    for name,pol in (("TP50_SL20","TP50_SL20"),("FIX60","FIX60"),("FIX180","FIX180")):
        stp=stats([dict(r,pnl=r["sec"][pol]["pnl"],tp=r["sec"][pol]["tp"]) for r in sel_ood if r["sec"][pol]]); C.setdefault("secondary_policies",{})[name]=stp
        trial(stage="S5_secondary_policy",lane="M",horizon=h,config=f"{ru['rule_text']} | {name}",partition="VAL+AUDIT",N=(stp or {}).get("N"),EV=(stp or {}).get("EV"),PF=(stp or {}).get("PF"),median=(stp or {}).get("median"))
    # ablatiune leave-one-family-out pe modelul orizontului candidat (VAL)
    # bankroll
    def bankroll(sel,B0):
        seq=sorted(sel,key=lambda r:r["T0"]); B=B0; open_until=-1; n_exec=n_skip=0; pk=B; dd=0; losses=0; maxl=0; pnls=[]
        for r in seq:
            if r["prim"]["entry_ts"]<open_until: n_skip+=1; continue
            notional=min(25.0,B/15.0)
            if notional<1.0: n_skip+=1; continue
            pnl=r["prim"]["pnl"]*(notional/25.0); B+=pnl; pnls.append(pnl); n_exec+=1; open_until=r["prim"]["exit_ts"]; pk=max(pk,B); dd=min(dd,B-pk); losses=losses+1 if pnl<0 else 0; maxl=max(maxl,losses)
        rng=random.Random(3); ends=[]
        for _ in range(500):
            b=B0; blocks=[pnls[i:i+20] for i in range(0,len(pnls),20)] or [[0.0]]
            for blk in [rng.choice(blocks) for _ in blocks]:
                for p in blk: b+=p*(min(25.0,b/15.0)/min(25.0,B0/15.0)) if b>0 else 0
            ends.append(b)
        ends.sort(); return dict(start=B0,trades=n_exec,skipped_overlap=n_skip,end=B,max_dd=dd,max_consec_losses=maxl,boot_p5=ends[25],boot_p50=ends[250],boot_p95=ends[475],risk_of_ruin_50pct=sum(1 for e in ends if e<0.5*B0)/len(ends),median_capital_hours=(S.median([r["prim"]["hold_s"] for r in seq])/3600 if seq else None),opps_per_day=len(seq)/max(1e-9,(max(r["T0"] for r in seq)-min(r["T0"] for r in seq))/86400) if len(seq)>1 else None)
    C["bankroll"]={B:bankroll(sel_ood,B) for B in (100,500,2000)}
    R["candidate"]=C
    # ---------- poarta ----------
    A=C["OOD_VAL_AUDIT"]; ru_p=next((it["p_holm"] for it in R["multiple_testing"]["items"] if it["label"]==f"{h}s/RULE"),None)
    g=None
    if A:
        g=dict(N100=A["N"]>=100,EV=A["EV"]>0,PF=(A["PF"] or 0)>=1.25,median=A["median"]>=0,CI_low=A["EV_CI95_cluster_hour"][0]>0,p_adj=(ru_p is not None and ru_p<0.05),blocks3=(A["days_pos"]>=3 if A["days_pos"] is not None else False),no_single_day=(max(A["days_EV"].values())*1<A["EV"]*A["N"] if A["days_EV"] else False),hour_dep=(A["hour_dep"] or 1)<=0.5,exb1pct=A["EX_BEST_1PCT"]>0,top1=A["top1pct_contrib"]<=0.4,lat2=A["EV"]>0,cost25=((C["stress"]["cost"]["x1.25"] or {}).get("EV",-1))>0,pessimistic=A["EV"]>0,placebo=((C["stress"]["placebo_random_entry"] or {}).get("EV",1e9))<A["EV"]-0.1,complement=((C["OOD_complement"] or {}).get("EV",1e9))<A["EV"]-0.1,dev_pos=(ru["DEV"] or {}).get("EV",-1)>0,val_pos=(ru["VAL"] or {}).get("EV",-1)>0,audit_pos=((C["AUDIT"] or {}).get("EV",-1))>0)
    R["gate"]=g; R["candidate_exists"]=bool(cands)
    if not cands: lane="NO_PREDICTIVE_STRUCTURE" if not any(c.get("p_raw") is not None and c["p_raw"]<0.05 and c["best_minus_all"]>0 for c in screen if "p_raw" in c) else "STATISTICAL_BUT_NOT_ECONOMIC"
    elif g and all(g.values()): lane="LANE_HISTORICAL_CANDIDATE"
    elif not g["p_adj"]: lane="STATISTICAL_BUT_NOT_ECONOMIC" if R["reality_check"]["p_block_permutation"]<0.05 else "NO_PREDICTIVE_STRUCTURE"   # fara semnal statistic dupa corectia globala + reality check => nu exista structura predictiva demonstrata
    elif not g["exb1pct"] or not g["top1"]: lane="TAIL_DEPENDENT"
    elif not g["cost25"]: lane="COST_ERASED"
    elif not g["blocks3"] or not g["hour_dep"]: lane="SHORT_WINDOW_RESEARCH_SIGNAL"
    else: lane="SHORT_WINDOW_RESEARCH_SIGNAL"
    R["lane_verdict_M"]=lane
    json.dump(R,open("research/master_edge_results.json","w"),indent=1,default=str)
    with open("research/master_edge_trials.csv","w",newline="") as f:
        cols=["ts","stage","lane","horizon","config","partition","N","EV","PF","median","p_raw","note"]; w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader(); [w.writerow(t) for t in TRIALS]
    print("LANE_VERDICT_M",lane,"candidate_exists",bool(cands),"gate",g); print("DISCOVERY_DONE",flush=True)
if __name__=="__main__": main()
