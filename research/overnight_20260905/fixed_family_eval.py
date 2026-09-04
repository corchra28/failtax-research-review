"""Stage 3-4: executia regulii primare (decizie T0+60 s, intrare la prima stare ancorata >= decizie, 0,25 SOL, iesire +60 s, 120 s descriptiv), semnalele H1-H3 (praguri DEV distributionale),
statistici (Bonferroni x3, bootstrap 10.000 stratificat pe zi cu reesantionarea mint-urilor, baseline matched/complement/neconditionat), poarta si verdictele; apoi revizuirea adversariala.
Ordine obligatorie: outcomes -> (privire DEV) -> freeze praguri -> evaluare VAL+CONF. Fara cautare de parametri."""
import gzip,json,hashlib,collections,statistics as S,math,time,sys,os,copy,random,bisect
sys.path.insert(0,'research'); sys.path.insert(0,'research/overnight_20260905'); import atomic_same_mint_arb as A; import cohort_panel as CP
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/overnight_20260905"; LAMP=10**9; Q=int(0.25*LAMP); NET=210000; DEC=60; HOLD=60
DAYS=dict(DEV="2026-09-02",VAL="2026-09-03",CONF="2026-09-04")
def fee_at(ev,i):
    e=ev[i]
    if e[12]>0: return (e[12],e[13],e[14])
    return A.event_tier_at(ev,i)   # taxa 0 (eveniment special) => tierul demonstrat de evenimentele vecine, altfel None
def execute(x,Dts,hold=HOLD,lat=0.0,fee_mult=1.0):
    """intrare exact-B (max sub bugetul Q) la starea ancorata de dupa toate evenimentele cu ts <= D+lat; iesire vanzare exact B la starea ancorata de dupa ts <= intrare+hold, cu overlay-ul pozitiei; PnL in SOL dupa taxe si retea."""
    ev=x["ev"]; X=Dts+lat
    if X<x["T0_ts"]: return dict(status="ENTRY_BEFORE_POOL_CREATION")
    ts=[e[1] for e in ev]; i=bisect.bisect_right(ts,X)-1
    if i<0: return dict(status="NO_STATE_AT_ENTRY")
    if not A.anchored(ev,i): return dict(status="ENTRY_STATE_UNANCHORED")
    vq=x["vq"]; fa=fee_at(ev,i)
    if fa is None: return dict(status="FEE_UNRESOLVED_ENTRY")
    fa=tuple(int(math.ceil(v*fee_mult)) for v in fa); rb,rq=ev[i][8],ev[i][9]; B=A.max_base_for_budget(rb,rq,vq,Q,*fa)
    if B<=0: return dict(status="NO_FILL")
    bo=A.buy_exact_out(rb,rq,vq,B,*fa); spent=bo[0]; q_pool=bo[1]+bo[2]
    Xe=X+hold; j=bisect.bisect_right(ts,Xe)-1
    if j<=i: return dict(status="NO_EXIT_STATE")
    if not A.anchored(ev,j): return dict(status="EXIT_STATE_UNANCHORED")
    br=A.chain_breaks(ev)
    if not A.chain_ok_between(br,i,j): return dict(status="CHAIN_BREAK_IN_HOLD")
    fb=fee_at(ev,j)
    if fb is None: return dict(status="FEE_UNRESOLVED_EXIT")
    fb=tuple(int(math.ceil(v*fee_mult)) for v in fb); rb2=ev[j][8]-B; rq2=ev[j][9]+q_pool
    if rb2<=0: return dict(status="OVERLAY_INVALID")
    out,brut,_,_,_=A.exec_sell(rb2,rq2,vq,B,*fb); pnl=(out-spent-NET)/LAMP
    return dict(status="OK",entry_ts=X,entry_slot=ev[i][2],exit_ts=Xe,exit_slot=ev[j][2],B=B,quote_spent=spent,sell_out=out,pnl_sol=pnl,ret=pnl/(spent/LAMP),entry_fee_bps=sum(fa),exit_fee_bps=sum(fb))
def load_panel():
    P=[]
    for l in gzip.open(f"{D}/cohort_panel.jsonl.gz","rt"): P.append(json.loads(l))
    return P
def load_pools():
    X={}
    for l in gzip.open(f"{D}/m_pools.jsonl.gz","rt"): x=json.loads(l); X[x["mint"]]=x
    return X
def stage_outcomes():
    P=load_panel(); X=load_pools(); rows=[]; st=collections.Counter()
    for f in P:
        x=X[f["mint"]]; o=execute(x,f["D"]); o2=execute(x,f["D"],hold=120); oc=execute(x,f["D"],fee_mult=1.25); ol=execute(x,f["D"],lat=2.0); st[o["status"]]+=1
        rows.append(dict(mint=f["mint"],day=f["day"],D=f["D"],primary=o,secondary_120=o2,cost_x125=oc,latency_plus2=ol))
    h=hashlib.sha256()
    with gzip.open(f"{D}/outcomes_panel.jsonl.gz","wt") as fo:
        for r in rows: s=json.dumps(r,separators=(",",":"))+"\n"; fo.write(s); h.update(s.encode())
    json.dump(dict(rows=len(rows),status_counts=dict(st),content_sha256=h.hexdigest(),built=time.strftime("%Y-%m-%d %H:%M:%S")),open(f"{OUT}/outcomes_manifest.json","w"),indent=1); print("outcomes",dict(st)); print("OUTCOMES_DONE")
def pct_rank(sorted_dev,v):
    return bisect.bisect_right(sorted_dev,v)/len(sorted_dev) if sorted_dev else None
def build_signals(P,O):
    """praguri EXCLUSIV din distributia DEV; semnale evaluate pe VAL+CONF."""
    dev=[f for f in P if f["day"]==DAYS["DEV"]]
    # H1
    prior_all=[b[0] for f in dev for b in f["buyers_prior"]]; sel_thr=S.median(prior_all) if prior_all else 0
    def h1_feat(f):
        if f["n_post_only_buyers"]<5 or f["n_post_swaps"]<10 or f["buy_quote"]<=0: return None
        selq=sum(b[2] for b in f["buyers_prior"] if b[0]<=sel_thr); return (selq/f["buy_quote"])*f["n_post_only_buyers"]/(1+f["incumbent_sell_share"]+(f["hhi_buy"] or 0))
    d1=sorted(v for v in (h1_feat(f) for f in dev) if v is not None); q3_1=d1[int(0.75*len(d1))] if d1 else None
    # H2
    def h2_ok(f): return f["decay_ratio"] is not None
    d2=sorted(f["decay_ratio"] for f in dev if h2_ok(f)); q1_2=d2[int(0.25*len(d2))] if d2 else None; med_rem=S.median([f["remaining_inventory_proxy"] for f in dev if h2_ok(f)]) if d2 else None
    # H3
    e3=[f for f in dev if f["n_post_only_buyers"]>=5 and f["median_prior_mints"] is not None and f["top1_buy_share"] is not None]
    s_b=sorted(f["n_post_only_buyers"] for f in e3); s_p=sorted(f["median_prior_mints"] for f in e3); s_c=sorted(f["top1_buy_share"] for f in e3)
    def h3_feat(f):
        if not (f["n_post_only_buyers"]>=5 and f["median_prior_mints"] is not None and f["top1_buy_share"] is not None) or not e3: return None
        return (pct_rank(s_b,f["n_post_only_buyers"])+(1-pct_rank(s_p,f["median_prior_mints"]))+(1-pct_rank(s_c,f["top1_buy_share"])))/3
    d3=sorted(v for v in (h3_feat(f) for f in dev) if v is not None); q3_3=d3[int(0.75*len(d3))] if d3 else None
    thr=dict(H1=dict(selectivity_threshold_prior_mints=sel_thr,q3_rotation_score=q3_1,n_dev_eligible=len(d1)),H2=dict(q1_decay_ratio=q1_2,median_remaining_inventory=med_rem,n_dev_eligible=len(d2)),H3=dict(q3_quality=q3_3,n_dev_eligible=len(d3)))
    sig={}
    for f in P:
        v1=h1_feat(f); v3=h3_feat(f)
        sig[f["mint"]]=dict(H1=(v1 is not None and q3_1 is not None and v1>=q3_1),H1_elig=(v1 is not None),H1_v=v1,H2=(h2_ok(f) and q1_2 is not None and f["decay_ratio"]<=q1_2 and f["remaining_inventory_proxy"]<med_rem),H2_elig=h2_ok(f),H2_v=f["decay_ratio"],H3=(v3 is not None and q3_3 is not None and v3>=q3_3),H3_elig=(v3 is not None),H3_v=v3)
    return thr,sig
def stats(rows,key="pnl"):
    rows=[r for r in rows if r.get(key) is not None]; v=[r[key] for r in rows]   # stresurile neexecutabile (None) sunt excluse din statistica respectiva
    if not v: return None
    w=[a for a in v if a>0]; l=[a for a in v if a<=0]; srt=sorted(v,reverse=True); n=len(v)
    pos_by_mint=collections.defaultdict(float); [pos_by_mint.__setitem__(r["mint"],pos_by_mint[r["mint"]]+max(0,r[key])) for r in rows]; gp=sum(pos_by_mint.values()) or 1e-12
    days=collections.defaultdict(list); [days[r["day"]].append(r[key]) for r in rows]
    return dict(N=n,mints=len({r["mint"] for r in rows}),EV=sum(v)/n,median=S.median(v),PF=((sum(w)/abs(sum(l))) if l and sum(l)<0 else (float("inf") if w else 0.0)),win_rate=len(w)/n,EX_BEST_1PCT=sum(srt[max(1,n//100):])/max(1,n-max(1,n//100)),EX_BEST_3=(sum(srt[3:])/(n-3)) if n>3 else None,max_mint_share=max(pos_by_mint.values())/gp,by_day={d:sum(a)/len(a) for d,a in days.items()},by_day_N={d:len(a) for d,a in days.items()})
def bootstrap(rows,key="pnl",reps=10000,seed=20260905,alpha=0.05/3):
    """stratificat pe zi UTC; in fiecare zi reesantionare cu inlocuire a mint-urilor (clustere = mint); determinist."""
    rng=random.Random(seed); days=collections.defaultdict(list); [days[r["day"]].append(r[key]) for r in rows]; g=list(days.values()); n=sum(len(a) for a in g); bs=[]
    for _ in range(reps):
        tot=0.0
        for a in g:
            for _k in range(len(a)): tot+=a[rng.randrange(len(a))]
        bs.append(tot/n)
    bs.sort(); lo=bs[int(alpha/2*reps)]; hi=bs[int((1-alpha/2)*reps)-1]; p=sum(1 for b in bs if b<=0)/reps
    return dict(CI95_corrected=(lo,hi),CI95_raw=(bs[int(0.025*reps)],bs[int(0.975*reps)-1]),p_raw_one_sided=p,p_bonferroni=min(1.0,3*p),reps=reps)
def matched_baseline(sig_rows,pool_rows,feat):
    """pentru fiecare semnal: cel mai apropiat pool ne-semnal din aceeasi zi pe (lichiditate, randament anterior, nr. tranzactii, intensitatea fluxului de cumparare) standardizate."""
    keys=("liquidity_sol","ret_bp","n_post_swaps","buy_flow_sol_per_s"); allv={k:[feat[r["mint"]][k] for r in pool_rows if feat[r["mint"]].get(k) is not None] for k in keys}; mu={k:S.mean(allv[k]) for k in keys}; sd={k:(S.pstdev(allv[k]) or 1) for k in keys}
    out=[]; used=set()
    for r in sig_rows:
        fr=feat[r["mint"]]; best=None
        for c in pool_rows:
            if c["mint"] in used or c["day"]!=r["day"] or c["mint"]==r["mint"] or c.get("_sig"): continue
            fc=feat[c["mint"]]; d=sum(((fr[k] or 0)-(fc[k] or 0))**2/sd[k]**2 for k in keys)
            if best is None or d<best[0]: best=(d,c)
        if best: used.add(best[1]["mint"]); out.append(best[1])
    return out
def evaluate(rows_by_h,feat,sig,thr):
    R={}
    for h in ("H1","H2","H3"):
        elig=[r for r in rows_by_h if sig[r["mint"]][f"{h}_elig"] and r["day"]!=DAYS["DEV"]]; s=[r for r in elig if sig[r["mint"]][h]]; comp=[r for r in elig if not sig[r["mint"]][h]]
        for r in elig: r["_sig"]=sig[r["mint"]][h]
        st=stats(s); m=matched_baseline(s,elig,feat) if s else []; mst=stats(m); cst=stats(comp); ust=stats(elig)
        for r in elig: r.pop("_sig",None)
        bs=bootstrap(s) if s else None; c125=stats(s,"pnl_c125") if s else None; l2=stats(s,"pnl_l2") if s else None
        gate=None; verdict="INSUFFICIENT_CLEAN_SAMPLE"
        if st and st["N"]>=50 and st["mints"]>=20:
            gate=dict(N50=True,mints20=True,EV=st["EV"]>0,PF=st["PF"]>=1.5,CI_low=bs["CI95_corrected"][0]>0,p=bs["p_bonferroni"]<0.05,both_days=all(st["by_day"].get(d,-1)>0 for d in (DAYS["VAL"],DAYS["CONF"])),vs_matched=(mst is not None and st["EV"]>mst["EV"]),vs_complement=(cst is not None and st["EV"]>cst["EV"]),exb1pct=st["EX_BEST_1PCT"]>0,mint_share=st["max_mint_share"]<=0.20,cost125=(c125 or {}).get("EV",-1)>0,lat2=(l2 or {}).get("EV",-1)>0,no_violations=True)
            verdict="HISTORICAL_PAPER_CANDIDATE_REQUIRING_FRESH_FORWARD_VALIDATION" if all(gate.values()) else "FAIL"
        dev_s=[r for r in rows_by_h if r["day"]==DAYS["DEV"] and sig[r["mint"]][f"{h}_elig"] and sig[r["mint"]][h]]
        R[h]=dict(thresholds=thr[h],n_eligible_val_conf=len(elig),signals=st,DEV_signals_descriptive=stats(dev_s),bootstrap=bs,matched=mst,complement=cst,unconditional_eligible=ust,cost_x125=c125,latency_plus2=l2,secondary_120_descriptive=(stats(s,"pnl_120") if s else None),gate=gate,verdict=verdict,label="POST_HOC_HISTORICAL_RESEARCH")
    return R
def stage_evaluate():
    P=load_panel(); feat={f["mint"]:f for f in P}; O={}
    for l in gzip.open(f"{D}/outcomes_panel.jsonl.gz","rt"): r=json.loads(l); O[r["mint"]]=r
    rows=[]
    for f in P:
        o=O[f["mint"]]
        if o["primary"]["status"]!="OK": continue
        rows.append(dict(mint=f["mint"],day=f["day"],pnl=o["primary"]["pnl_sol"],pnl_120=(o["secondary_120"]["pnl_sol"] if o["secondary_120"]["status"]=="OK" else None),pnl_c125=(o["cost_x125"]["pnl_sol"] if o["cost_x125"]["status"]=="OK" else None),pnl_l2=(o["latency_plus2"]["pnl_sol"] if o["latency_plus2"]["status"]=="OK" else None)))
    thr,sig=build_signals(P,O)
    json.dump(dict(thresholds=thr,frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"),note="praguri distributionale din DEV (2026-09-02), inghetate inainte de evaluarea VAL/CONF"),open(f"{OUT}/thresholds_frozen.json","w"),indent=1)
    R=evaluate(rows,feat,sig,thr); R["_meta"]=dict(executable_rows=len(rows),by_day=dict(collections.Counter(r["day"] for r in rows)),panel_rows=len(P),unconditional_all=stats(rows),unconditional_by_day={d:stats([r for r in rows if r["day"]==d]) for d in sorted({r["day"] for r in rows})})
    for h,name in (("H1","h1_cohort_rotation"),("H2","h2_seller_overhang"),("H3","h3_selective_buyer")): json.dump(R[h],open(f"{OUT}/{name}_results.json","w"),indent=1,default=str)
    json.dump(R["_meta"],open(f"{OUT}/unconditional_results.json","w"),indent=1,default=str)
    with gzip.open(f"{D}/signals.jsonl.gz","wt") as f:
        for r in rows: f.write(json.dumps(dict(r,**{k:v for k,v in sig[r["mint"]].items()}))+"\n")
    mt=dict(family_size=3,correction="Bonferroni x3 (p si CI la alpha/3)",tests={h:dict(p_raw=(R[h]["bootstrap"] or {}).get("p_raw_one_sided"),p_bonferroni=(R[h]["bootstrap"] or {}).get("p_bonferroni"),CI95_corrected=(R[h]["bootstrap"] or {}).get("CI95_corrected"),N=(R[h]["signals"] or {}).get("N"),mints=(R[h]["signals"] or {}).get("mints"),verdict=R[h]["verdict"]) for h in ("H1","H2","H3")},best_candidate=None)
    json.dump(mt,open(f"{OUT}/multiple_testing_summary.json","w"),indent=1,default=str)
    for h in ("H1","H2","H3"): print(h,R[h]["verdict"],"N",(R[h]["signals"] or {}).get("N"),"mints",(R[h]["signals"] or {}).get("mints"),"EV",(R[h]["signals"] or {}).get("EV"),"PF",(R[h]["signals"] or {}).get("PF"),"CI",(R[h]["bootstrap"] or {}).get("CI95_corrected"))
    print("EVAL_DONE")
if __name__=="__main__": {"outcomes":stage_outcomes,"evaluate":stage_evaluate}[sys.argv[1]]()
