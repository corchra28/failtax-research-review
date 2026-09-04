"""REGIME-GATED MIGRATION TEST (POST_HOC_HISTORICAL_EXPLORATION). Spec inghetata: research/regime_gate_frozen_spec.json.
Shadow: fiecare migrare BOOST eligibila -> o tranzactie ipotetica $25 (Complete+7 s, conservator, TP $50 / SL $17,50 / timeout 300 s). Regim: blocuri UTC de 15 min;
la inceputul blocului, fereastra = shadow-uri cu intrarea in [B-60 min, B) si rezolvate inainte de B; ON daca N>=30, medie trimata 10 %>0, PF>1,15, mediana>0, ex-best-1>0, EV ambele jumatati>0.
Strategie: in bloc ON, prima migrare eligibila dupa inceputul blocului, max o pozitie activa, max una per bloc. Baseline A-F, stabilitate, bankroll, poarta, verdict. Zero date noi."""
import gzip,json,math,os,sys,csv,time,bisect,hashlib,random,collections,statistics as S,datetime
SCR="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad"; CACHE=f"{SCR}/derived/regime_pools.jsonl.gz"
SPEC=json.load(open("research/regime_gate_frozen_spec.json")); SOL_USD=100.0; N_USD=25.0; PRIO=0.01; OBS=5; LAT=2; TO=300; TP_M=2.0; SL_M=0.70
def exec_buy(rb,rq,vq,q,lp,pr,cc,s=1.0):
    tot=int(round((lp+pr+cc)*s)); q2=q*10000//(10000+tot); lpf=q2*int(round(lp*s))//10000; return rb*q2//(rq+vq+q2),q2+lpf
def exec_sell(rb,rq,vq,b,lp,pr,cc,s=1.0):
    if rb<=0 or b<=0: return 0
    brut=(rq+vq)*b//(rb+b); u=brut-brut*int(round(lp*s))//10000-brut*int(round((pr+cc)*s))//10000; return min(u,max(0,rq))
def state_at(x,X,optimistic=False):
    """conservator: dupa toate evenimentele cu ts<=X; optimist: dupa evenimentele cu ts<X."""
    ev=x["ev"]; i=(bisect.bisect_left(x["_ts"],X) if optimistic else bisect.bisect_right(x["_ts"],X))-1
    if i<0: e=ev[0]; return e[6],e[7],e[12],e[13],e[14],-1
    e=ev[i]; return e[8],e[9],e[12],e[13],e[14],i
def shadow(x,N=N_USD,s=1.0,lat=LAT,optimistic=False):
    vq=x["vq"]; ev=x["ev"]; X=x["complete_ts"]+OBS+lat; rb,rq,lp,pr,cc,i=state_at(x,X,optimistic); q=int(N/SOL_USD*1e9); tok,qn=exec_buy(rb,rq,vq,q,lp,pr,cc,s)
    if tok<=0: return None
    entry_slot=ev[i][2] if i>=0 else ev[0][2]; TP=N*TP_M; SL=N*SL_M; deadline=X+TO; out=None; mfe=-N; mae=N; t_mfe=t_mae=None; first_barrier=None
    def liq(e): rb2=e[8]-tok; rq2=e[9]+qn; return (exec_sell(rb2,rq2,vq,tok,e[12],e[13],e[14],s)/1e9*SOL_USD) if rb2>0 else 0.0
    j=i+1
    while j<len(ev) and ev[j][1]<=deadline:
        if optimistic: k=j
        else:
            sl_=ev[j][2]; k=j
            while k+1<len(ev) and ev[k+1][2]==sl_ and ev[k+1][1]<=deadline: k+=1
        V=liq(ev[k]); rel=ev[k][1]-X
        if V-N>mfe: mfe=V-N; t_mfe=rel
        if V-N<mae: mae=V-N; t_mae=rel
        hitTP=V>=TP; hitSL=V<=SL
        if optimistic and hitTP: out=("TP",V,ev[k][1],ev[k][2]); break
        if hitSL: out=("SL",V,ev[k][1],ev[k][2]); break
        if hitTP: out=("TP",V,ev[k][1],ev[k][2]); break
        j=k+1
    if out is None:
        rb3,rq3,lp3,pr3,cc3,i3=state_at(x,deadline,optimistic); rb2=(rb3 if i3>=0 else rb)-tok; rq2=(rq3 if i3>=0 else rq)+qn
        V=(exec_sell(rb2,rq2,vq,tok,lp3,pr3,cc3,s)/1e9*SOL_USD) if rb2>0 else 0.0; out=("TIMEOUT",V,deadline,None)
        if V-N>mfe: mfe=V-N; t_mfe=TO
        if V-N<mae: mae=V-N; t_mae=TO
    pnl=out[1]-N-2*PRIO
    return dict(entry_ts=X,entry_slot=entry_slot,entry_state_idx=i,tok=tok,q_in_lamports=qn,entry_rb=rb,entry_rq=rq,exit_kind=out[0],exit_value=out[1],exit_ts=out[2],exit_slot=out[3],resolution_ts=out[2],pnl=pnl,ret=pnl/N,hold_s=out[2]-X,mfe=mfe,mae=mae,t_mfe=t_mfe,t_mae=t_mae,notional=N)
def stats(rows,key="pnl",N=N_USD):
    v=[r for r in rows if r.get(key) is not None]
    if not v: return None
    pn=sorted([r[key] for r in v],reverse=True); n=len(pn); w=[a for a in pn if a>0]; l=[a for a in pn if a<=0]; gp=sum(w) or 1e-9; asc=sorted(pn); k=n//10; trim=asc[k:n-k] if n-2*k>0 else asc
    q=lambda p: asc[min(n-1,int(n*p))]
    st=dict(N=n,EV=sum(pn)/n,EV_pct=100*sum(pn)/n/N,trimmed_EV=sum(trim)/len(trim),median=S.median(pn),PF=(sum(w)/abs(sum(l))) if l and sum(l)<0 else None,P_gt0=len(w)/n,avg_win=(sum(w)/len(w)) if w else None,avg_loss=(sum(l)/len(l)) if l else None,P10=q(.1),P25=q(.25),P75=q(.75),P90=q(.9),
        EX_BEST_1=sum(pn[1:])/max(1,n-1),EX_BEST_3=sum(pn[3:])/max(1,n-3),EX_BEST_1PCT=sum(pn[max(1,n//100):])/max(1,n-max(1,n//100)),top1pct_contrib=sum(pn[:max(1,n//100)])/gp,TP=sum(1 for r in v if r.get("exit_kind")=="TP"),SL=sum(1 for r in v if r.get("exit_kind")=="SL"),TIMEOUT=sum(1 for r in v if r.get("exit_kind")=="TIMEOUT"))
    hrs=collections.defaultdict(list); [hrs[r["hour"]].append(r[key]) for r in v]; st["hours_pos"]=sum(1 for a in hrs.values() if sum(a)>0); st["hours_n"]=len(hrs)
    days=collections.defaultdict(list); [days[r["day"]].append(r[key]) for r in v]; st["days_EV"]={d:sum(a)/len(a) for d,a in sorted(days.items())}; st["days_pos"]=sum(1 for a in days.values() if sum(a)>0); st["days_n"]=len(days)
    seq=sorted(v,key=lambda r:r["entry_ts"]); eq=pk=dd=0.0; cl=mcl=0
    for r in seq:
        eq+=r[key]; pk=max(pk,eq); dd=min(dd,eq-pk); cl=cl+1 if r[key]<0 else 0; mcl=max(mcl,cl)
    st["MAX_DD"]=dd; st["max_consec_losses"]=mcl; st["capital_hours"]=sum(r.get("hold_s",0) for r in v)/3600; st["profit_per_capital_hour"]=(sum(pn)/st["capital_hours"]) if st["capital_hours"]>0 else None
    st["chrono_quartile_EV"]=[(sum(r[key] for r in seq[i*n//4:(i+1)*n//4])/max(1,len(seq[i*n//4:(i+1)*n//4]))) for i in range(4)]; st["halves_EV"]=[sum(r[key] for r in seq[:n//2])/max(1,n//2),sum(r[key] for r in seq[n//2:])/max(1,n-n//2)]
    rng=random.Random(11); groups=list(hrs.values()); bs=[]
    for _ in range(1000):
        flat=[a for g in [rng.choice(groups) for _ in groups] for a in g]; bs.append(sum(flat)/len(flat))
    bs.sort(); st["EV_CI95_cluster_hour"]=(bs[25],bs[974]); st["p_boot_EV_le_0"]=sum(1 for b in bs if b<=0)/len(bs); st["max_hour_share"]=max((sum(a) for a in hrs.values()),default=0)/gp; st["max_day_share"]=max((sum(a) for a in days.values()),default=0)/gp
    return st
def trimmed(v):
    a=sorted(v); n=len(a); k=n//10; t=a[k:n-k] if n-2*k>0 else a; return sum(t)/len(t)
def gate_inputs(win,B):
    pn=[r["pnl"] for r in win]; n=len(pn)
    if n==0: return dict(N=0)
    w=[a for a in pn if a>0]; l=[a for a in pn if a<=0]; first=[r["pnl"] for r in win if r["entry_ts"]<B-1800]; second=[r["pnl"] for r in win if r["entry_ts"]>=B-1800]
    g=dict(N=n,trimmed_mean=trimmed(pn),PF=(sum(w)/abs(sum(l))) if l and sum(l)<0 else (float("inf") if w else 0.0),median=S.median(pn),ex_best_1_EV=(sum(sorted(pn)[:-1])/(n-1)) if n>1 else pn[0],EV_first30=(sum(first)/len(first)) if first else None,EV_second30=(sum(second)/len(second)) if second else None)
    g["ON"]=bool(n>=30 and g["trimmed_mean"]>0 and g["PF"]>1.15 and g["median"]>0 and g["ex_best_1_EV"]>0 and (g["EV_first30"] or 0)>0 and (g["EV_second30"] or 0)>0)
    return g
def run_strategy(blocks,state_of,pools_by_block,trade_fn,label):
    """o pozitie activa, max una per bloc; trade_fn(pool)->dict|None. Returneaza tranzactii si skip-uri."""
    trades=[]; skips=collections.Counter(); active_until=-1
    for b in blocks:
        B=b["B"]
        if not state_of(b): continue
        cands=[p for p in pools_by_block.get(B,[]) if p["_elig"]>=max(B,active_until)]
        if not cands:
            skips["NO_ELIGIBLE_MIGRATION" if not pools_by_block.get(B) else "POSITION_ALREADY_ACTIVE"]+=1; continue
        p=cands[0]; t=trade_fn(p)
        if not t: skips["NOT_EXECUTABLE"]+=1; continue
        t=dict(t,mint=p["mint"],block=B,day=p["day"],hour=p["hour"],label=label); trades.append(t); active_until=t["exit_ts"]
        skips["SIGNALS_SKIPPED_WHILE_ACTIVE"]+=sum(1 for c in cands[1:] if c["_elig"]<t["exit_ts"])
    return trades,dict(skips)
def main():
    t0=time.time(); pools=[]
    with gzip.open(CACHE,"rt") as f:
        for line in f:
            x=json.loads(line); x["_ts"]=[e[1] for e in x["ev"]]; x["hour"]=int(x["complete_ts"]//3600); x["_elig"]=x["complete_ts"]+OBS+LAT; pools.append(x)
    man=json.load(open(f"{SCR}/derived/regime_cache_manifest.json"))
    for x in pools:
        x["sh"]=shadow(x); x["sh_opt"]=shadow(x,optimistic=True); x["sh_c125"]=shadow(x,s=1.25); x["sh_c150"]=shadow(x,s=1.5); x["sh_lat5"]=shadow(x,lat=LAT+5)
    elig=[x for x in pools if x["sh"]]; print("shadow calculate",len(elig),"din",len(pools),round(time.time()-t0,1),"s",flush=True)
    SH=[dict(x["sh"],mint=x["mint"],day=x["day"],hour=x["hour"],source=x["source"]) for x in elig]
    # blocuri UTC 15 min
    tmin=min(x["_elig"] for x in elig); tmax=max(x["sh"]["exit_ts"] for x in elig); B0=int(tmin//900*900); blocks=[]; by_entry=sorted(SH,key=lambda r:r["entry_ts"]); ET=[r["entry_ts"] for r in by_entry]
    pools_by_block=collections.defaultdict(list)
    for x in sorted(elig,key=lambda x:(x["_elig"],x["complete_slot"],x["complete_sig"])): pools_by_block[int(x["_elig"]//900*900)].append(x)
    B=B0
    while B<=tmax:
        lo=bisect.bisect_left(ET,B-3600); hi=bisect.bisect_left(ET,B); win=[r for r in by_entry[lo:hi] if r["resolution_ts"]<B]; unresolved=(hi-lo)-len(win)
        g=gate_inputs(win,B); blocks.append(dict(B=B,B_utc=datetime.datetime.utcfromtimestamp(B).strftime("%Y-%m-%d %H:%M"),day=datetime.datetime.utcfromtimestamp(B).strftime("%Y-%m-%d"),n_window_entries=hi-lo,n_unresolved=unresolved,gate=g,ON=g.get("ON",False),n_migrations_in_block=len(pools_by_block.get(B,[])))); B+=900
    nb=len(blocks); on=[b for b in blocks if b["ON"]]; print("blocuri",nb,"ON",len(on),flush=True)
    for i,b in enumerate(blocks): b["ON_prev"]=blocks[i-1]["ON"] if i>0 else False; b["ON_next"]=blocks[i+1]["ON"] if i+1<nb else False
    # rulaje ON
    runs=[]; cur=0
    for b in blocks:
        if b["ON"]: cur+=1
        elif cur: runs.append(cur); cur=0
    if cur: runs.append(cur)
    tf=lambda p: p["sh"]
    ON_tr,ON_sk=run_strategy(blocks,lambda b:b["ON"],pools_by_block,tf,"ON"); OFF_tr,OFF_sk=run_strategy(blocks,lambda b:not b["ON"],pools_by_block,tf,"OFF_A"); EVERY_tr,EVERY_sk=run_strategy(blocks,lambda b:True,pools_by_block,tf,"EVERY_B")
    D_tr,_=run_strategy(blocks,lambda b:b["ON_prev"],pools_by_block,tf,"SHIFT_FWD_D"); E_tr,_=run_strategy(blocks,lambda b:b["ON_next"],pools_by_block,tf,"SHIFT_BWD_E_INVALID")
    for b in blocks:
        t=next((t for t in ON_tr if t["block"]==b["B"]),None); b["selected_mint"]=t["mint"] if t else None; b["strategy_pnl"]=t["pnl"] if t else None; b["strategy_exit_kind"]=t["exit_kind"] if t else None
        if b["ON"] and not t: b["skip_reason"]="NO_ELIGIBLE_MIGRATION" if not pools_by_block.get(b["B"]) else "POSITION_ALREADY_ACTIVE_OR_NOT_EXECUTABLE"
        else: b["skip_reason"]=None
    # C: permutari ale rulajelor ON (500)
    rng=random.Random(2026); onEV=(S.mean([t["pnl"] for t in ON_tr]) if ON_tr else None); permEV=[]
    for _ in range(500):
        lab=[False]*nb; pos=0; gaps=nb-sum(runs)
        if runs and gaps>=0:
            cuts=sorted(rng.sample(range(gaps+1),len(runs))) if len(runs)<=gaps+1 else [0]*len(runs); order=runs[:]; rng.shuffle(order); p=0
            for c,r in zip(cuts,order):
                start=c+p; 
                for k in range(start,min(nb,start+r)): lab[k]=True
                p+=r
        st_map={b["B"]:lab[i] for i,b in enumerate(blocks)}; tr,_=run_strategy(blocks,lambda b:st_map[b["B"]],pools_by_block,tf,"C")
        permEV.append(S.mean([t["pnl"] for t in tr]) if tr else 0.0)
    p_perm=(sum(1 for v in permEV if v>=onEV)/len(permEV)) if onEV is not None else None
    R=dict(label=SPEC["label"],N_pools_cache=len(pools),N_eligible=len(elig),by_day=dict(collections.Counter(x["day"] for x in elig)),by_source=dict(collections.Counter(x["source"] for x in elig)),cache_manifest=man,N_blocks=nb,N_ON_blocks=len(on),activation_rate=len(on)/nb,ON_runs=runs,max_consecutive_ON=max(runs) if runs else 0,days_with_ON=sorted({b["day"] for b in on}),
        migrations_in_ON_blocks=sum(b["n_migrations_in_block"] for b in on),migrations_in_OFF_blocks=sum(b["n_migrations_in_block"] for b in blocks if not b["ON"]),
        ON=dict(trades=len(ON_tr),skips=ON_sk,stats=stats(ON_tr),by_day={d:stats([t for t in ON_tr if t["day"]==d]) for d in sorted({t["day"] for t in ON_tr})}),
        OFF_A=dict(trades=len(OFF_tr),skips=OFF_sk,stats=stats(OFF_tr),by_day={d:stats([t for t in OFF_tr if t["day"]==d]) for d in sorted({t["day"] for t in OFF_tr})}),
        EVERY_B=dict(trades=len(EVERY_tr),skips=EVERY_sk,stats=stats(EVERY_tr)),RANDOM_C=dict(n_perm=500,perm_EV_mean=(S.mean(permEV) if permEV else None),perm_EV_p95=(sorted(permEV)[int(0.95*len(permEV))] if permEV else None),p_perm=p_perm),
        SHIFT_FWD_D=dict(trades=len(D_tr),stats=stats(D_tr)),SHIFT_BWD_E_INVALID=dict(trades=len(E_tr),stats=stats(E_tr),note="DIAGNOSTIC DE SCURGERE — NEEXECUTABIL"),
        UNCOND_F=dict(stats=stats(SH),by_day={d:stats([r for r in SH if r["day"]==d]) for d in sorted({r["day"] for r in SH})}))
    # stabilitate pe ON
    def alt(key):
        out=[]
        for t in ON_tr:
            x=next(p for p in elig if p["mint"]==t["mint"]); a=x.get(key)
            if a: out.append(dict(a,mint=t["mint"],day=t["day"],hour=t["hour"]))
        return stats(out)
    if ON_tr:
        best_block=max(ON_tr,key=lambda t:t["pnl"])["block"]; best_day=max(R["ON"]["stats"]["days_EV"].items(),key=lambda kv:kv[1]*sum(1 for t in ON_tr if t["day"]==kv[0]))[0]; pn=sorted([t["pnl"] for t in ON_tr],reverse=True); cut=pn[max(0,len(pn)//100-1)] if len(pn)>=100 else pn[0]
        R["stability"]=dict(leave_one_day_out={d:stats([t for t in ON_tr if t["day"]!=d]) for d in sorted({t["day"] for t in ON_tr})},leave_one_hour_out_min_EV=min((stats([t for t in ON_tr if t["hour"]!=h]) or {"EV":0})["EV"] for h in {t["hour"] for t in ON_tr}),chrono_quartiles=R["ON"]["stats"]["chrono_quartile_EV"],halves=R["ON"]["stats"]["halves_EV"],
            excl_best_block=stats([t for t in ON_tr if t["block"]!=best_block]),excl_best_day=stats([t for t in ON_tr if t["day"]!=best_day]),excl_top1pct=stats([t for t in ON_tr if t["pnl"]<cut]),cost_125=alt("sh_c125"),cost_150=alt("sh_c150"),latency_plus5=alt("sh_lat5"),optimistic=alt("sh_opt"))
    # bankroll
    def bankroll(B0):
        Bk=B0; pk=B0; dd=0.0; trades=[]; skips=collections.Counter(); active_until=-1; cl=mcl=0
        for b in blocks:
            if not b["ON"]: continue
            cands=[p for p in pools_by_block.get(b["B"],[]) if p["_elig"]>=max(b["B"],active_until)]
            if not cands: skips["NO_ELIGIBLE_MIGRATION" if not pools_by_block.get(b["B"]) else "POSITION_ALREADY_ACTIVE"]+=1; continue
            N=min(25.0,Bk,0.01*Bk/0.30)
            if N<0.5: skips["INSUFFICIENT_CAPITAL"]+=1; continue
            p=cands[0]; t=shadow(p,N=N)
            if not t: skips["NOT_EXECUTABLE"]+=1; continue
            before=Bk; Bk+=t["pnl"]; pk=max(pk,Bk); dd=min(dd,(Bk-pk)/pk); cl=cl+1 if t["pnl"]<0 else 0; mcl=max(mcl,cl); active_until=t["exit_ts"]
            trades.append(dict(block=b["B"],mint=p["mint"],notional=N,pnl=t["pnl"],exit_kind=t["exit_kind"],entry_ts=t["entry_ts"],exit_ts=t["exit_ts"],bankroll_before=before,bankroll_after=Bk,drawdown=dd))
        rng=random.Random(3); rets=[t["pnl"]/t["notional"] for t in trades]; ends=[]
        for _ in range(500):
            b=B0; blks=[rets[i:i+10] for i in range(0,len(rets),10)] or [[0.0]]
            for blk in [rng.choice(blks) for _ in blks]:
                for r in blk: n_=min(25.0,b,0.01*b/0.30); b+=r*n_
            ends.append(b)
        ends.sort(); return dict(start=B0,trades=len(trades),skips=dict(skips),end=Bk,max_drawdown_frac=dd,max_consec_losses=mcl,boot_p5=ends[25],boot_p50=ends[250],boot_p95=ends[475],risk_of_ruin_50pct=sum(1 for e in ends if e<0.5*B0)/len(ends),ledger=trades)
    R["bankroll"]={B:bankroll(B) for B in (100,500,2000)}
    # poarta
    A=R["ON"]["stats"]; O=R["OFF_A"]["stats"]; EB=R["EVERY_B"]["stats"]; g=None
    if A:
        st=R["stability"]; days_on=len(R["days_with_ON"])
        g=dict(ON_blocks15=len(on)>=15,ON_trades50=len(ON_tr)>=50,days3=days_on>=3,EV=A["EV"]>0,PF=(A["PF"] or 0)>=1.25,median=A["median"]>=0,trimmed=A["trimmed_EV"]>0,CI_low=A["EV_CI95_cluster_hour"][0]>0,exb1pct=A["EX_BEST_1PCT"]>0,top1=A["top1pct_contrib"]<=0.4,vs_OFF=(O is not None and A["EV"]>O["EV"]+0.1),vs_EVERY=(EB is not None and A["EV"]>EB["EV"]+0.1),perm=(p_perm is not None and p_perm<0.05),cost25=((st["cost_125"] or {}).get("EV",-1))>0,conservative=A["EV"]>0,lat5=((st["latency_plus5"] or {}).get("EV",-1))>0,chrono3=sum(1 for v in A["chrono_quartile_EV"] if v>0)>=3,no_dominant=(A["max_day_share"]<=0.5 and A["max_hour_share"]<=0.5),dd15=all(abs(R["bankroll"][B]["max_drawdown_frac"])<=0.15 for B in (100,500,2000)),ruin100=R["bankroll"][100]["risk_of_ruin_50pct"]<0.05,leakage=True)
    R["gate"]=g
    if not on: v="REGIME_GATE_NEVER_ACTIVATES"
    elif not g or not (g["ON_blocks15"] and g["ON_trades50"] and g["days3"]): v="REGIME_GATE_INSUFFICIENT_SAMPLE"
    elif all(g.values()): v="REGIME_GATE_HISTORICAL_PAPER_CANDIDATE"
    elif not (g["vs_OFF"] and g["vs_EVERY"] and g["perm"]): v="REGIME_GATE_NO_PERSISTENCE"
    elif not (g["EV"] and g["PF"] and g["median"] and g["trimmed"] and g["CI_low"]): v="REGIME_GATE_NO_ECONOMIC_EDGE"
    elif not (g["exb1pct"] and g["top1"]): v="REGIME_GATE_TAIL_DEPENDENT"
    elif not (g["chrono3"] and g["no_dominant"]): v="REGIME_GATE_REGIME_DEPENDENT"
    else: v="REGIME_GATE_COST_OR_LATENCY_ERASED"
    R["FINAL_VERDICT"]=v; R["runtime_s"]=round(time.time()-t0,1)
    json.dump(R,open("research/regime_gate_results.json","w"),indent=1,default=str)
    # export derivate pentru pachetul extern
    with gzip.open(f"{SCR}/derived/regime_shadow.jsonl.gz","wt") as f:
        for x in elig: f.write(json.dumps(dict(mint=x["mint"],pool=x["pool"],day=x["day"],source=x["source"],fee_mode=x["fee_mode"],ordering=x["ordering"],complete_ts=x["complete_ts"],complete_slot=x["complete_slot"],complete_sig=x["complete_sig"],T0_ts=x["T0_ts"],T0_slot=x["T0_slot"],vq=x["vq"],n_events=len(x["ev"]),sh=x["sh"],sh_opt=x["sh_opt"],sh_c125=x["sh_c125"],sh_c150=x["sh_c150"],sh_lat5=x["sh_lat5"]))+"\n")
    json.dump(blocks,open(f"{SCR}/derived/regime_blocks.json","w"),default=str); json.dump(dict(ON=ON_tr,OFF_A=OFF_tr,EVERY_B=EVERY_tr,D=D_tr,E=E_tr),open(f"{SCR}/derived/regime_trades.json","w"),default=str)
    print("VERDICT",v,"gate",g); print("REGIME_DONE",flush=True)
if __name__=="__main__": main()
