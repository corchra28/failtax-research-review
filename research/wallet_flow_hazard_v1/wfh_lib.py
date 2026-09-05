"""WALLET_FLOW_HAZARD_V1 — HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED. Graf temporal de portofele strict cauzal (doar pozitii maturizate inainte de decizie), blocuri A-E,
etichete first-passage (TP 2x / SL -35 %, V3 lib read-only, limite de ordine conservative), person-period pentru hazarde concurente, exit dinamic. Zero RPC."""
import os,sys,math,json,bisect,collections,statistics
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0,os.path.join(ROOT,"research","curve2x_v3_reclaim")); sys.path.insert(0,os.path.join(ROOT,"research","curve2x_v2"))
import v3_lib as V; L=V.L; import numpy as np
LAMP=L.LAMP; MATURITY_S=960; HOR=900; FEE=L.FEE_CURVE; BIN_S=60; NBINS=15; TP=2.0; SL=0.65; N_REF=0.25
BLOCKS={"WALLET_QUALITY":["wq_share_with_history","wq_prior_matured_med","wq_prior_tp_rate_w","wq_prior_ev_w","wq_wallet_age_med_h","wq_survival_w","wq_repeat_winner_share","wq_sol_share_repeat_winners"],
 "INDEPENDENT_BREADTH":["ib_new_buyers","ib_new_profitable_buyers","ib_common_wallet_reuse","ib_same_slot_max_wallets","ib_buy_entropy","ib_hhi","ib_top1","ib_top3","ib_top10"],
 "SELLER_INVENTORY_HAZARD":["sh_early_inventory_share","sh_early_sold_pct","sh_sell_intensity_decay","sh_sellers_remaining","sh_absorption_after_big_sell","sh_sell_vol_60s","sh_holders_remaining"],
 "CREATOR_HISTORY":["ch_prior_launches","ch_prior_mig_rate","ch_prior_tp_rate","ch_prior_sell_share","ch_prior_ev_mean","ch_inventory_share","ch_sold_flag"],
 "MARKET_STATE":["ms_progress","ms_rs_sol","ms_vs_sol","ms_reserve_accel","ms_slippage_bp","ms_headroom","ms_launch_rate_10m","ms_trades_per_slot_5","ms_age_s","ms_landmark"]}
FEATS=[f for v in BLOCKS.values() for f in v]; STATE_FEATS=BLOCKS["MARKET_STATE"]
# ---------------- graf temporal de portofele (pozitii maturizate) ----------------
def wallet_positions_for_mint(rec):
    """per portofel: prima cumparare, sol_in, tok_in, sol_out, tok_out, marcarea inventarului ramas la ultima stare <= first_buy+900 (executabil, overlay static), TP proxy = pret max in 900 s >= 2,1 x pretul mediu de intrare.
    Returneaza lista de pozitii (wallet, first_buy_ts, maturity_ts, tp, realized_pnl_sol, survived, sol_in)."""
    T=rec["trades"]; W={}
    for t in T:
        w=W.get(t[4])
        if w is None: w=W[t[4]]=dict(fb=None,si=0,ti=0,so=0,to=0,last_i=None)
        if t[7]:
            if w["fb"] is None: w["fb"]=t[0]
            w["si"]+=t[5]; w["ti"]+=t[6]
        else: w["so"]+=t[5]; w["to"]+=t[6]
    out=[]; prices=[(t[0],t[10]/t[11] if t[11]>0 else 0.0) for t in T]
    for u,w in W.items():
        if w["fb"] is None or w["ti"]<=0: continue
        end=w["fb"]+HOR; j=bisect.bisect_right([p[0] for p in prices],end)-1; st=T[j] if j>=0 else None; rem=max(0,w["ti"]-w["to"])
        mark=L.curve_liq(st[10],st[11],st[8],rem,0,FEE) if (st is not None and rem>0) else 0
        pmax=max((p[1] for p in prices if w["fb"]<=p[0]<=end),default=0.0); pin=w["si"]/w["ti"]; tp=1 if (pin>0 and pmax>=2.1*pin) else 0
        pnl=(w["so"]+mark-w["si"])/LAMP; out.append((u,w["fb"],w["fb"]+MATURITY_S,tp,pnl,1 if pnl>-0.35*w["si"]/LAMP else 0,w["si"]/LAMP))
    return out
class WalletGraph:
    """cauzal: interogarea la timpul t foloseste doar pozitiile cu maturity_ts <= t (si prima aparitie < t)."""
    def __init__(self): self.P=collections.defaultdict(list); self.first_seen={}
    def add(self,positions):
        for u,fb,mt,tp,pnl,surv,si in positions:
            self.P[u].append((mt,tp,pnl,surv,si)); 
            if u not in self.first_seen or fb<self.first_seen[u]: self.first_seen[u]=fb
    def finalize(self):
        for u in self.P: self.P[u].sort()
    def stats(self,u,t):
        lst=self.P.get(u)
        if not lst: return None
        k=bisect.bisect_right(lst,(t,))
        if k==0: return None
        m=lst[:k]; n=len(m); tp=sum(x[1] for x in m)/n; ev=sum(x[2] for x in m)/n; surv=sum(x[3] for x in m)/n; rw=1 if sum(x[1] for x in m)>=2 else 0
        return dict(n=n,tp=tp,ev=ev,surv=surv,rw=rw,age_h=max(0.0,(t-self.first_seen[u])/3600))
def creator_history_for_mint(rec):
    """rezumat maturizat al lansarii (matur la create + 1860 + 960): migrat, TP proxy pentru referinta la 20 % progres, cota vanduta de creator, EV proxy."""
    T=rec["trades"]; ct=rec["create_ts"]; cr=rec["creator"]; mig=1 if rec.get("complete_ts") is not None else 0
    cb=sum(t[6] for t in T if t[7] and t[4]==cr); cs=sum(t[6] for t in T if (not t[7]) and t[4]==cr); sell_share=(cs/cb) if cb>0 else 0.0
    a=next((i for i,t in enumerate(T) if t[8]>=0.2*L.TARGET_RS),None); tp=0; ev=0.0
    if a is not None:
        st=T[a]; h,ds=L.curve_buy(st[10],st[11],int(N_REF*LAMP)); vals=[L.curve_liq(t[10],t[11],t[8],h,ds) for t in T[a+1:] if t[0]<=st[0]+HOR]
        if h>0 and vals: tp=1 if max(vals)>=TP*N_REF*LAMP else 0; ev=(vals[-1]-N_REF*LAMP)/LAMP
    return dict(creator=cr,maturity_ts=ct+1860+MATURITY_S,mig=mig,tp=tp,sell_share=sell_share,ev=ev)
class CreatorGraph:
    def __init__(self): self.H=collections.defaultdict(list)
    def add(self,h): self.H[h["creator"]].append((h["maturity_ts"],h["mig"],h["tp"],h["sell_share"],h["ev"]))
    def finalize(self):
        for c in self.H: self.H[c].sort()
    def stats(self,c,t):
        lst=self.H.get(c) or []; k=bisect.bisect_right(lst,(t,)); m=lst[:k]
        if not m: return dict(n=0,mig=-1.0,tp=-1.0,sell=-1.0,ev=0.0)
        n=len(m); return dict(n=n,mig=sum(x[1] for x in m)/n,tp=sum(x[2] for x in m)/n,sell=sum(x[3] for x in m)/n,ev=sum(x[4] for x in m)/n)
# ---------------- trasaturi la decizie (strict din trecut) ----------------
def features(rec,i,ts,landmark,G,CG,launch_rate_10m):
    T=rec["trades"][:i+1]; last=T[-1]; f={}; buys=[t for t in T if t[7]]; sells=[t for t in T if not t[7]]
    bu=collections.Counter(); [bu.__setitem__(t[4],bu[t[4]]+t[5]) for t in buys]; tot=sum(bu.values()) or 1
    # A. WALLET_QUALITY (pozitii maturizate inainte de ts; ponderare cu SOL)
    st={u:G.stats(u,ts) for u in bu}; known={u:s for u,s in st.items() if s}; wk=sum(bu[u] for u in known) or 1
    f["wq_share_with_history"]=len(known)/len(bu) if bu else 0.0; f["wq_prior_matured_med"]=statistics.median([s["n"] for s in known.values()]) if known else 0.0
    f["wq_prior_tp_rate_w"]=sum(bu[u]*s["tp"] for u,s in known.items())/wk if known else -1.0; f["wq_prior_ev_w"]=sum(bu[u]*s["ev"] for u,s in known.items())/wk if known else 0.0
    f["wq_wallet_age_med_h"]=statistics.median([s["age_h"] for s in known.values()]) if known else 0.0; f["wq_survival_w"]=sum(bu[u]*s["surv"] for u,s in known.items())/wk if known else -1.0
    f["wq_repeat_winner_share"]=(sum(1 for s in known.values() if s["rw"])/len(bu)) if bu else 0.0; f["wq_sol_share_repeat_winners"]=sum(bu[u] for u,s in known.items() if s["rw"])/tot
    # B. INDEPENDENT_BREADTH
    half=T[max(0,len(T)-max(10,len(T)//4)):]; seen=set(t[4] for t in T[:len(T)-len(half)] if t[7]); newb={t[4] for t in half if t[7]}-seen
    f["ib_new_buyers"]=len(newb); f["ib_new_profitable_buyers"]=sum(1 for u in newb if known.get(u) and known[u]["ev"]>0); f["ib_common_wallet_reuse"]=len(known)/len(bu) if bu else 0.0
    ps=collections.defaultdict(set); [ps[t[1]].add(t[4]) for t in buys]; f["ib_same_slot_max_wallets"]=max((len(v) for v in ps.values()),default=0)
    sizes=[t[5] for t in buys]; f["ib_buy_entropy"]=(-sum((s/sum(sizes))*math.log(s/sum(sizes)) for s in sizes if s>0)/math.log(len(sizes))) if len(sizes)>1 else 0.0
    sv=sorted(bu.values(),reverse=True); f["ib_hhi"]=sum((x/tot)**2 for x in sv); f["ib_top1"]=sv[0]/tot if sv else 0.0; f["ib_top3"]=sum(sv[:3])/tot; f["ib_top10"]=sum(sv[:10])/tot
    # C. SELLER_INVENTORY_HAZARD (cohorta timpurie = cumparatorii pana la 20 % din trade-uri)
    bought=collections.Counter(); sold=collections.Counter()
    for t in T: (bought if t[7] else sold)[t[4]]+=t[6]
    early={t[4] for t in T[:max(1,len(T)//5)] if t[7]}; eb=sum(bought[u] for u in early) or 1; es=sum(min(sold[u],bought[u]) for u in early); net=sum(bought.values())-sum(sold.values()) or 1
    f["sh_early_inventory_share"]=max(0,eb-es)/net; f["sh_early_sold_pct"]=es/eb
    s60=sum(t[5] for t in sells if t[0]>=ts-60); s120=sum(t[5] for t in sells if ts-120<=t[0]<ts-60); f["sh_sell_intensity_decay"]=(s60/(s120+1e-9)) if (s60 or s120) else 0.0; f["sh_sell_vol_60s"]=s60/LAMP
    f["sh_sellers_remaining"]=sum(1 for u in sold if bought[u]-sold[u]>0); f["sh_holders_remaining"]=sum(1 for u in bought if bought[u]-sold[u]>0)
    big=max(sells,key=lambda t:t[5],default=None); f["sh_absorption_after_big_sell"]=((last[8]-big[8])/max(1,big[5])) if big else 0.0
    # D. CREATOR_HISTORY
    ch=CG.stats(rec["creator"],ts); f["ch_prior_launches"]=ch["n"]; f["ch_prior_mig_rate"]=ch["mig"]; f["ch_prior_tp_rate"]=ch["tp"]; f["ch_prior_sell_share"]=ch["sell"]; f["ch_prior_ev_mean"]=ch["ev"]
    cr=rec["creator"]; f["ch_inventory_share"]=max(0,bought[cr]-sold[cr])/net; f["ch_sold_flag"]=1.0 if sold[cr]>0 else 0.0
    # E. MARKET_STATE
    rs,vs,vt=last[8],last[10],last[11]; f["ms_progress"]=rs/L.TARGET_RS; f["ms_rs_sol"]=rs/LAMP; f["ms_vs_sol"]=vs/LAMP
    def rs_at(tt): j=bisect.bisect_right([x[0] for x in T],tt)-1; return T[j][8] if j>=0 else 0
    f["ms_reserve_accel"]=((rs-rs_at(ts-10))-(rs_at(ts-10)-rs_at(ts-20)))/LAMP; hr,tok,ds=L.curve_headroom(vs,vt,rs,int(N_REF*LAMP)); f["ms_headroom"]=hr; f["ms_slippage_bp"]=((ds/tok)/(vs/vt)-1)*1e4 if (tok>0 and vs>0) else 1e5
    f["ms_launch_rate_10m"]=launch_rate_10m; sl=collections.Counter(t[1] for t in T); f["ms_trades_per_slot_5"]=sum(sl[s] for s in sorted(sl)[-5:])/5; f["ms_age_s"]=ts-rec["create_ts"]; f["ms_landmark"]=float(landmark)
    return f
# ---------------- person-period (hazarde concurente) si exit dinamic ----------------
def path_bins(rec,i_trig,dec_ts,pool=None):
    """traiectoria valorii executabile (intrare dupa toate trade-urile din slotul +3) impartita in bin-uri de 60 s: pentru fiecare bin: value_ratio la sfarsit, min/max in bin, net flow, sell vol, eveniment (TP/SL/none) in bin."""
    T=rec["trades"]; trig=T[i_trig]; land=trig[1]+3; gross=int(N_REF*LAMP); comp_key=(rec["complete_slot"],rec["complete_seq"],10**9) if (rec.get("complete_ts") is not None and rec["complete_ts"]<=dec_ts+HOR) else None; j=i_trig
    for q in range(i_trig+1,len(T)):
        if T[q][1]<=land: j=q
        else: break
    if comp_key is not None and (L.order_key(T[j])>=comp_key or rec["complete_slot"]<=land): return None
    st=T[j]; h,ds=L.curve_buy(st[10],st[11],gross)
    if h<=0: return None
    path=[]
    for t in T[j+1:]:
        if comp_key is not None and L.order_key(t)>=comp_key: break
        if t[0]>dec_ts+HOR: break
        path.append((t[0],t[1],L.curve_liq(t[10],t[11],t[8],h,ds),t[5]*(1 if t[7] else -1),t[5] if not t[7] else 0,"curve"))
    if comp_key is not None:
        if pool is None: return dict(unavailable=True)
        for s in pool["states"]:
            if s[0]>dec_ts+HOR: break
            path.append((s[0],s[1],L.pool_liq(s[4],s[5],pool["vq"],h,s[6]),0,0,"pool"))
    path.sort(key=lambda p:(p[1],p[0])); bins=[]; v_last=L.curve_liq(st[10],st[11],st[8],h,ds)/gross; entry_ratio=v_last; ev_done=None
    for b in range(NBINS):
        lo,hi=dec_ts+b*BIN_S,dec_ts+(b+1)*BIN_S; inb=[p for p in path if lo<p[0]<=hi]; vals=[p[2]/gross for p in inb] or [v_last]; event=None
        for p in inb:
            nv=(p[2]-L.NET_COST)/gross
            if nv<=SL: event="SL"; break
            if nv>=TP: event="TP"; break
        v_last=vals[-1]; bins.append(dict(b=b,value_ratio=v_last,vmin=min(vals),vmax=max(vals),net_flow=sum(p[3] for p in inb)/LAMP,sell_vol=sum(p[4] for p in inb)/LAMP,n=len(inb),event=event,exit_state=(inb[-1] if inb else None)))
        if event: break
    return dict(entry_i=j,h=h,ds=ds,gross=gross,bins=bins,path=path,entry_ratio=entry_ratio)
def dynamic_exit_pnl(rec,pb,exit_bin,path_state_slot):
    """PnL conservativ al iesirii dinamice la sfarsitul bin-ului: pozitiile plauzibile = ultima stare strict inainte de exit_slot (= slot_final_bin + 3) si starile din exit_slot; se ia minimul."""
    gross=pb["gross"]; path=pb["path"]; ex_slot=path_state_slot+3; before=[p for p in path if p[1]<ex_slot and p[1]>=path_state_slot]; inx=[p for p in path if p[1]==ex_slot]; vals=([before[-1][2]] if before else [])+[p[2] for p in inx]
    if not vals: return None
    return (min(vals)-L.NET_COST-gross)/LAMP
