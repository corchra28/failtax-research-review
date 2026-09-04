"""S6 MULTIPOOL_BEST_EXECUTION_ROUTER (spec inghetat in cod): pentru token-uri cu >= 2 pool-uri eligibile (populatiile inghetate), la fiecare stare de decizie (slot cu eveniment), compara pool-ul 'selectat implicit'
(pool-ul canonical daca exista, altfel pool-ul cu cea mai mare lichiditate reala la decizie) cu cel mai bun pool executabil si cu impartirea determinista 50/50 pe 2 pool-uri; buy-only, sell-only (base fix = B cumparat), round trip; 0,10/0,25/0,50 SOL;
stari de landing worst-of la +3 si +5; costul instructiunii suplimentare (a doua instructiune de swap intr-o tranzactie: +0 tx, dar +5.000 lamports rezerva pentru CU/prioritate) — economia trebuie sa depaseasca acest cost."""
import sys,gzip,json,collections,statistics as S,time; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"; LAMP=10**9; EXTRA=5000
spec=dict(strategy="S6_MULTIPOOL_BEST_EXECUTION_ROUTER",mechanism="alegerea pool-ului cu pretul executabil mai bun (rezerve/taxe/impact diferite) sau impartirea determinista intre 2 pool-uri reduce costul de executie al unei tranzactii deja decise",who_loses="nimeni: economie de executie fata de pool-ul implicit; contrapartea este LP-ul pool-ului mai ieftin",
  default_pool="canonical daca exista in grup, altfel pool-ul cu rq real maxim la decizie",routes="single best pool; split 50/50 pe cele mai bune 2 pool-uri (sume fixate inainte de trimitere, fara rutare dinamica)",costs="cost suplimentar de instructiune 5.000 lamports per swap suplimentar; taxe pool observate/tier; +3 si +5 sloturi worst-of",requirements=dict(median_saving_gt_extra_cost=True,positive_after_5_slots=True,decisions_min=50,tokens_min=5,ex_best_1pct_gt=0),frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s6_frozen_spec.json",spec)
Pp=json.load(open(A.POPFILE)); meta=A.load_rpc_meta(); E=A.load_pass2(); pop={}
for k in ("PRIMARY_MEME","SECONDARY_ALL_NONCANONICAL"):
    for t,v in Pp[k]["tokens"].items(): pop.setdefault(t,set()).update(v["pools"])
def fee(p,st,ev,i,vq): return A.resolve_fee(meta,p,st[0],st[1],vq,ev_tier=A.event_tier_at(ev,i))
dec=[]
for tok,pools in pop.items():
    ok=[p for p in pools if p in E and E[p] and meta[p]["orientation"]=="STRICT"]
    if len(ok)<2: continue
    slots=sorted({e[2] for p in ok for e in E[p]}); canon=[p for p in ok if meta[p]["canonical"]]
    for s in slots[::5]:   # decizii la fiecare al 5-lea slot cu eveniment (dedup temporal; fara selectie pe outcome)
        states={}
        for p in ok:
            st=A.state_provable(E[p],s)
            if st is None: continue
            vq=A.implied_vq(E[p][:st[2]+1])[0]
            if vq is None: continue
            f=fee(p,st,E[p],st[2],int(vq))
            if f is None: continue
            states[p]=(st,int(vq),f)
        if len(states)<2: continue
        default=canon[0] if canon and canon[0] in states else max(states,key=lambda p:states[p][0][1])
        for N in (0.10,0.25,0.50):
            Q=int(N*LAMP); row=dict(token=tok,day=time.strftime("%Y-%m-%d",time.gmtime(max(E[p][states[p][0][2]][1] for p in states))),slot=s,notional=N,n_pools=len(states))
            for L in (3,5):
                def land(p):
                    outs=[]
                    for ls in (s+L-1,s+L):
                        st=A.state_provable(E[p],ls)
                        if st is None: return None
                        outs.append(st)
                    return outs
                L_states={p:land(p) for p in states}
                if any(v is None for v in L_states.values()): continue
                def buy_tokens(p,q,worst=True):
                    vals=[]
                    for st in L_states[p]:
                        vq=states[p][1]; f=states[p][2]; B=A.max_base_for_budget(st[0],st[1],vq,q,*f); vals.append(B)
                    return min(vals) if worst else max(vals)
                def sell_out(p,B):
                    vals=[]
                    for st in L_states[p]:
                        vq=states[p][1]; f=states[p][2]; vals.append(A.exec_sell(st[0],st[1],vq,B,*f)[0])
                    return min(vals)
                # BUY: tokeni obtinuti pentru Q in pool-ul implicit vs cel mai bun vs split 50/50 (2 instructiuni)
                bt={p:buy_tokens(p,Q) for p in states}; best=max(bt,key=lambda p:bt[p]); top2=sorted(states,key=lambda p:-bt[p])[:2]; split=sum(buy_tokens(p,Q//2) for p in top2)
                pdef=(states[default][0][1]+states[default][1])/states[default][0][0]   # pret de referinta (quote per base) la decizie
                buy_save_best=(bt[best]-bt[default])*pdef/LAMP; buy_save_split=(split-bt[default])*pdef/LAMP-EXTRA/LAMP
                # SELL: acelasi B (cumparat in pool-ul implicit la decizie) vandut in implicit vs best vs split
                B=bt[default]
                so={p:sell_out(p,B) for p in states}; sbest=max(so,key=lambda p:so[p]); s2=sorted(states,key=lambda p:-so[p])[:2]; ssplit=sum(sell_out(p,B//2) for p in s2)
                sell_save_best=(so[sbest]-so[default])/LAMP; sell_save_split=(ssplit-so[default])/LAMP-EXTRA/LAMP
                # round trip: cumpara in best (Q) si vinde in best pentru acel B vs implicit-implicit
                Bb=bt[best]; rt_best=(sell_out(max(states,key=lambda p:sell_out(p,Bb)),Bb)-sell_out(default,B))/LAMP
                row[f"L{L}"]=dict(buy_save_best=buy_save_best,buy_save_split=buy_save_split,sell_save_best=sell_save_best,sell_save_split=sell_save_split,round_trip_save_best=rt_best,best_is_default=(best==default))
            dec.append(row)
res=dict(spec_sha256=C.sha(f"{OUT}/s6_frozen_spec.json"),decisions=len(dec),tokens=len({r["token"] for r in dec}),by_notional={})
for N in (0.10,0.25,0.50):
    rs=[r for r in dec if r["notional"]==N and "L3" in r and "L5" in r]; d={}
    for key in ("buy_save_best","buy_save_split","sell_save_best","sell_save_split","round_trip_save_best"):
        v3=[r["L3"][key] for r in rs]; v5=[r["L5"][key] for r in rs]
        if v3: srt=sorted(v3,reverse=True); n=len(v3); d[key]=dict(N=n,median_L3=S.median(v3),mean_L3=S.mean(v3),median_L5=S.median(v5),mean_L5=S.mean(v5),ex_best_1pct_L3=sum(srt[max(1,n//100):])/max(1,n-max(1,n//100)),share_positive_L3=sum(1 for x in v3 if x>0)/n)
    d["best_is_default_share"]=(sum(1 for r in rs if r["L3"]["best_is_default"])/len(rs)) if rs else None; res["by_notional"][str(N)]=d
d=res["by_notional"]["0.1"]; rt=d.get("round_trip_save_best"); g=dict(decisions50=len(dec)//3>=50,tokens5=res["tokens"]>=5,median_saving_gt_extra=(rt or {}).get("median_L3",-1)>EXTRA/LAMP,positive_after_5=(rt or {}).get("median_L5",-1)>0,exb1pct=(rt or {}).get("ex_best_1pct_L3",-1)>0) if rt else None
res["gate"]=g; res["verdict"]=("EXECUTION_COST_REDUCTION_CONFIRMED" if (g and all(g.values())) else ("INSUFFICIENT_CLEAN_SAMPLE" if not g or not (g["decisions50"] and g["tokens5"]) else "EXECUTION_COST_REDUCTION_NOT_CONFIRMED"))
C.write("s6_results.json",res); print("S6",res["verdict"],"decisions",len(dec),"tokens",res["tokens"],json.dumps(d,default=str)[:600]); print("S6_DONE")
