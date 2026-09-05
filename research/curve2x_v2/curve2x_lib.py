"""CURVE2X V2 — HISTORICAL_REMEDIATION_NOT_SEALED. Biblioteca comuna (batch + automatizare paper-only; zero RPC/WSS, zero tranzactii).
Componente: matematica exacta a curbei pump.fun (intregi), motorul de decizie streaming (landmark-uri de progres, trasaturi pe blocuri),
etichete first-passage (TP_FIRST / SL_FIRST / TIMEOUT_OTHER) cu continuare in pool-ul canonic PumpSwap (rezerve efective = raw + virtual),
modele numpy (multinomial logistic L2, GBM depth-2 multiclass, RF-lite), calibrare pe CAL, regressor de PnL cross-fitted, politica inghetata."""
import math,json,bisect,collections,hashlib,statistics
import numpy as np
LAMP=10**9; FEE_CURVE=125; NET_COST=210000; TARGET_RS=85*LAMP; POOL_SUPPLY=10**15
LANDMARKS=[10,20,30,40,50,60,70,80]; ENTRY_MIN=20; ENTRY_MAX=70; DEC_WINDOW=1860
HORIZONS={"5M":300,"15M":900,"30M":1800}; PRIMARY_H="15M"; NOTS=[0.25,0.5,1.0]; PRIMARY_N=0.25
LAND=3; LAND_STRESS=5; COST_STRESS=1.25; REGIME_MIN=10; YOUNG=3600; WALLET_WINDOW=3600
# ---------------- curba pump.fun (intregi) ----------------
def curve_buy(vs,vt,gross,fee=FEE_CURVE):
    """cumparare exact-input: gross lamports -> (tokens, sol_net_in_curba)."""
    if vs<=0 or vt<=0 or gross<=0: return 0,0
    net=gross*10000//(10000+fee); k=vs*vt; tok=vt-k//(vs+net); return (tok,net) if tok>0 else (0,0)
def curve_sell_raw(vs,vt,rs,h,fee=FEE_CURVE):
    """vanzarea a h tokens in starea (vs,vt) cu rezerva reala rs; plafon la rezerva reala; net de taxa."""
    if h<=0 or vs<=0 or vt<=0: return 0
    g=vs-(vs*vt)//(vt+h)-1; g=max(0,min(g,rs)); return g*(10000-fee)//10000
def curve_liq(vs,vt,rs,h,ds,fee=FEE_CURVE):
    """lichidare cu overlay static al propriei pozitii: starea observata (fara noi) devine (vs+ds, vt-h), rezerva reala rs+ds."""
    vt2=vt-h
    if vt2<=0: return 0
    return curve_sell_raw(vs+ds,vt2,rs+ds,h,fee)
def curve_headroom(vs,vt,rs,gross,fee=FEE_CURVE):
    """plafonul mecanic curve-only: cumparam gross acum, restul curbei este umplut de altii pana la completare (rs -> 85 SOL); valoarea neta a lichidarii
    noastre in starea de completare / gross. Nu include aprecierea post-migrare (mecanism diferit, nemarginit din starea curenta)."""
    tok,ds=curve_buy(vs,vt,gross,fee)
    if tok<=0: return 0.0,tok,ds
    vs1=vs+ds; vt1=vt-tok; rs1=rs+ds; R=max(0,TARGET_RS-rs1); k=vs1*vt1; vsf=vs1+R; vtf=k//vsf if vsf>0 else 0; rsf=rs1+R
    return curve_sell_raw(vsf,vtf,rsf,tok,fee)/gross,tok,ds
def pool_liq(rb,rq,vq,h,fee_bp):
    """vanzare in pool PumpSwap cu overlay static (baza pool-ului = rb - h, quote neschimbat), rezerve efective quote = rq + vq, plafon la quote-ul real rq."""
    if h<=0 or rb<=0: return 0
    rb_eff=rb-h
    if rb_eff<=0: return 0
    out=(rq+vq)*h//(rb_eff+h); out=max(0,min(out,rq)); return out*(10000-fee_bp)//10000
def implied_vq(ev):
    """VQ implicit din primele <=80 evenimente (>=5 obs, mediana >=0, IQR <= max(0,02 SOL, 2 %)); altfel None. ev: [ts,slot,seq,k,is_buy,rb,rq,rb_post,rq_post,amt,cp_q,lpbp,prbp,cce]"""
    v=[]
    for a in ev[:80]:
        if a[9]<=0 or a[10]<=0: continue
        if a[4]==1: v.append(a[5]*a[10]/a[9]-a[6]-a[10])
        else: v.append(a[10]*(a[5]+a[9])/a[9]-a[6])
    if len(v)<5: return None,len(v)
    v.sort(); med=v[len(v)//2]; q1=v[len(v)//4]; q3=v[3*len(v)//4]
    if med<0 or (q3-q1)>max(0.02e9,0.02*abs(med)): return None,len(v)
    return int(med),len(v)
# ---------------- blocuri de trasaturi ----------------
BLOCKS={
 "STATE_HEADROOM":["progress","rs_sol","vs_sol","log_vt","dist_to_migration_sol","landmark","jump_pp","headroom_025","headroom_050","headroom_100","slippage_bp_025","slippage_bp_050","slippage_bp_100"],
 "ORGANIC_ACCELERATION":["sec_to_prog","trades_to_prog","sec_prev10","trades_prev10","vel_last10","vel_prev","vel_change","vel_residual"],
 "BREADTH":["uniq_buyers","new_buyers_seg","breadth_growth_per10","buy_size_entropy","median_buy_sol","buy_count"],
 "SELL_EXHAUSTION_ABSORPTION":["sellers_n","sold_inventory_share","sell_vol_sol","seller_inventory_decline","sell_vol_over_drawdown","recovery","net_quote_flow_seg"],
 "COORDINATION_RISK":["top1_share","top3_share","top5_share","top10_share","hhi","repeated_size_share","max_wallets_slot","max_trades_slot","same_tx_multi_share","wallet_reuse_share","reuse_mints_med","creator_inventory_share","creator_sold_flag","creator_sell_share"],
 "REGIME":["launches_per_min","trades_per_min","buyvol_per_min","sellvol_per_min","completions_60m","hour_sin","hour_cos","mode_unknown","quote_sol","fee_mode_std"]}
FEATS=[f for v in BLOCKS.values() for f in v]
ABLATIONS={"M0":["STATE_HEADROOM"],"M1":["STATE_HEADROOM","ORGANIC_ACCELERATION"],"M2":["STATE_HEADROOM","ORGANIC_ACCELERATION","BREADTH"],"M3":["STATE_HEADROOM","ORGANIC_ACCELERATION","BREADTH","SELL_EXHAUSTION_ABSORPTION"],"M4":["STATE_HEADROOM","ORGANIC_ACCELERATION","BREADTH","SELL_EXHAUSTION_ABSORPTION","COORDINATION_RISK"],"M5":list(BLOCKS)}
class Engine:
    """motor de decizie streaming: consuma evenimente de curba in ordinea benzii si emite un rand (trasaturi) la prima atingere a fiecarui landmark de progres.
    Trasaturile folosesc EXCLUSIV starea de pana la (inclusiv) trade-ul declansator; contextul de regim/portofele foloseste exclusiv evenimente anterioare."""
    def __init__(self):
        self.M={}; self.bins=collections.defaultdict(lambda:[0,0,0,0,0]); self.wal={}; self.velh={L:collections.deque() for L in LANDMARKS}; self.rows=[]; self.last_prune=0; self.n_events=0; self.last_ts=0
    def on_event(self,e):
        typ=e[0]; self.n_events+=1
        if typ=="C": self.on_create(*e[1:])
        elif typ=="T": self.on_trade(*e[1:])
        elif typ=="X": self.on_complete(*e[1:])
    def on_create(self,ts,slot,seq,mint,creator):
        if mint in self.M: return
        self.M[mint]=dict(_mint=mint,creator=creator,create_ts=ts,create_slot=slot,T=[],next=0,complete=False,lm={},max_rs=0,min_since_max=0,first_buy={})
        self.bins[ts//60][0]+=1; self.last_ts=max(self.last_ts,ts)
        if ts-self.last_prune>600: self.prune(ts)
    def on_complete(self,ts,slot,seq,mint):
        v=self.M.get(mint)
        if v is None: return
        v["complete"]=True; self.bins[ts//60][4]+=1
    def on_trade(self,ts,slot,seq,k,mint,user,sol,tok,is_buy,rs,rt,vs,vt):
        v=self.M.get(mint)
        if v is None or ts>v["create_ts"]+YOUNG: return
        b=self.bins[ts//60]; b[1]+=1; b[2 if is_buy else 3]+=sol; self.last_ts=max(self.last_ts,ts)
        if is_buy:
            v["first_buy"].setdefault(user,len(v["T"])); w=self.wal.get(user)
            if w is None: w=self.wal[user]=[]
            if not w or w[-1][1]!=mint: w.append((ts,mint))
        v["T"].append((ts,slot,seq,k,user,sol,tok,is_buy,rs,rt,vs,vt))
        if rs>v["max_rs"]: v["max_rs"]=rs; v["min_since_max"]=rs
        elif rs<v["min_since_max"]: v["min_since_max"]=rs
        if v["complete"]: return
        prog=rs/TARGET_RS
        while v["next"]<len(LANDMARKS) and prog>=LANDMARKS[v["next"]]/100:
            L=LANDMARKS[v["next"]]; v["next"]+=1
            if ts-v["create_ts"]>DEC_WINDOW: continue
            i=len(v["T"])-1; f=self.features(v,L,i,ts,slot); v["lm"][L]=(ts,i,f["uniq_buyers"])
            self.rows.append(dict(mint=mint,creator=v["creator"],create_ts=v["create_ts"],landmark=L,ts=ts,slot=slot,seq=seq,k=k,i=i,f=f))
            self.velh[L].append((ts,math.log(f["vel_last10"])))
    def prune(self,ts):
        self.last_prune=ts
        for m in [m for m,v in self.M.items() if ts-v["create_ts"]>YOUNG+120]: del self.M[m]
        for u in [u for u,w in self.wal.items() if w[-1][0]<ts-WALLET_WINDOW]: del self.wal[u]
        for L in LANDMARKS:
            d=self.velh[L]
            while d and d[0][0]<ts-3600: d.popleft()
        for mn in [mn for mn in self.bins if mn<ts//60-70]: del self.bins[mn]
    def features(self,v,L,i,ts,slot):
        T=v["T"][:i+1]; last=T[-1]; rs,rt,vs,vt=last[8],last[9],last[10],last[11]; f={}
        # STATE_HEADROOM
        f["progress"]=rs/TARGET_RS; f["rs_sol"]=rs/LAMP; f["vs_sol"]=vs/LAMP; f["log_vt"]=math.log(max(1,vt)); f["dist_to_migration_sol"]=(TARGET_RS-rs)/LAMP; f["landmark"]=float(L)
        prev_rs=T[-2][8] if len(T)>1 else 0; f["jump_pp"]=(rs-prev_rs)/TARGET_RS*100
        for N,tag in ((0.25,"025"),(0.5,"050"),(1.0,"100")):
            gross=int(N*LAMP); hr,tok,ds=curve_headroom(vs,vt,rs,gross); f[f"headroom_{tag}"]=hr
            f[f"slippage_bp_{tag}"]=((ds/tok)/(vs/vt)-1)*1e4 if (tok>0 and vs>0) else 1e5
        # ORGANIC_ACCELERATION
        c_ts=v["create_ts"]; f["sec_to_prog"]=ts-c_ts; f["trades_to_prog"]=len(T)
        pL=v["lm"].get(L-10); p_ts,p_i,p_ub=(pL if pL else (c_ts,-1,0)); f["sec_prev10"]=max(0.4,ts-p_ts); f["trades_prev10"]=i-p_i
        f["vel_last10"]=10/f["sec_prev10"]; pp=v["lm"].get(L-20); pp_ts=(pp[0] if pp else (c_ts if L>=20 else None))
        f["vel_prev"]=(10/max(0.4,p_ts-pp_ts)) if (pp_ts is not None and pL) else f["vel_last10"]; f["vel_change"]=f["vel_last10"]-f["vel_prev"]
        hist=[x[1] for x in self.velh[L] if x[0]<ts and x[0]>=ts-3600]; f["vel_residual"]=(math.log(f["vel_last10"])-statistics.median(hist)) if len(hist)>=5 else None
        # BREADTH
        buys=[t for t in T if t[7]]; sells=[t for t in T if not t[7]]; bu=collections.Counter(); [bu.__setitem__(t[4],bu[t[4]]+t[5]) for t in buys]
        f["uniq_buyers"]=len(bu); seg=T[p_i+1:]; seen=set(t[4] for t in T[:p_i+1] if t[7]); f["new_buyers_seg"]=len({t[4] for t in seg if t[7]}-seen); f["breadth_growth_per10"]=len(bu)-p_ub
        sizes=[t[5] for t in buys]; f["buy_count"]=len(buys); f["median_buy_sol"]=(statistics.median(sizes)/LAMP) if sizes else 0.0
        if len(sizes)>1:
            tot=sum(sizes); f["buy_size_entropy"]=-sum((s/tot)*math.log(s/tot) for s in sizes if s>0)/math.log(len(sizes))
        else: f["buy_size_entropy"]=0.0
        # SELL_EXHAUSTION_ABSORPTION
        bought=collections.Counter(); sold=collections.Counter()
        for t in T: (bought if t[7] else sold)[t[4]]+=t[6]
        tb=sum(bought.values()) or 1; f["sellers_n"]=len(sold); f["sold_inventory_share"]=sum(sold.values())/tb; f["sell_vol_sol"]=sum(t[5] for t in sells)/LAMP
        sb=sum(bought[u] for u in sold) ; f["seller_inventory_decline"]=(min(1.0,sum(sold.values())/sb)) if sb>0 else 0.0
        dd=(v["max_rs"]-v["min_since_max"])/LAMP; f["sell_vol_over_drawdown"]=f["sell_vol_sol"]/max(0.01,dd); f["recovery"]=((rs-v["min_since_max"])/(v["max_rs"]-v["min_since_max"])) if v["max_rs"]>v["min_since_max"] else 1.0
        f["net_quote_flow_seg"]=sum((t[5] if t[7] else -t[5]) for t in seg)/LAMP
        # COORDINATION_RISK
        sv=sorted(bu.values(),reverse=True); tot=sum(sv) or 1; f["top1_share"]=sv[0]/tot if sv else 0.0; f["top3_share"]=sum(sv[:3])/tot; f["top5_share"]=sum(sv[:5])/tot; f["top10_share"]=sum(sv[:10])/tot; f["hhi"]=sum((x/tot)**2 for x in sv)
        sc=collections.Counter(sizes); f["repeated_size_share"]=(sum(c for c in sc.values() if c>=3)/len(sizes)) if sizes else 0.0
        ps=collections.Counter(t[1] for t in T); pw=collections.defaultdict(set); [pw[t[1]].add(t[4]) for t in T]; f["max_trades_slot"]=max(ps.values()); f["max_wallets_slot"]=max(len(x) for x in pw.values())
        tx=collections.Counter(t[2] for t in T); f["same_tx_multi_share"]=sum(c for c in tx.values() if c>=2)/len(T)
        reuse=[]; 
        for u in bu:
            w=self.wal.get(u) or []; n=len({m for (t_,m) in w if t_<ts and t_>=ts-WALLET_WINDOW and m!=v_mint(v,T)})
            reuse.append(n)
        f["wallet_reuse_share"]=(sum(1 for n in reuse if n>=1)/len(reuse)) if reuse else 0.0; f["reuse_mints_med"]=(statistics.median(reuse) if reuse else 0.0)
        cr=v["creator"]; net_supply=sum(bought.values())-sum(sold.values()) or 1; f["creator_inventory_share"]=max(0,bought[cr]-sold[cr])/net_supply; f["creator_sold_flag"]=1.0 if sold[cr]>0 else 0.0; f["creator_sell_share"]=(sold[cr]/bought[cr]) if bought[cr]>0 else 0.0
        # REGIME (minute complete anterioare)
        mn=ts//60; B=[self.bins[m] for m in range(mn-REGIME_MIN,mn) if m in self.bins]; n=REGIME_MIN
        f["launches_per_min"]=sum(b[0] for b in B)/n; f["trades_per_min"]=sum(b[1] for b in B)/n; f["buyvol_per_min"]=sum(b[2] for b in B)/n/LAMP; f["sellvol_per_min"]=sum(b[3] for b in B)/n/LAMP
        f["completions_60m"]=sum(self.bins[m][4] for m in range(mn-60,mn) if m in self.bins); h=(ts%86400)/3600; f["hour_sin"]=math.sin(2*math.pi*h/24); f["hour_cos"]=math.cos(2*math.pi*h/24)
        f["mode_unknown"]=1.0; f["quote_sol"]=1.0; f["fee_mode_std"]=1.0
        return f
def v_mint(v,T): return v.get("_mint") or ""
# ---------------- etichete first-passage (batch) ----------------
def order_key(t): return (t[1],t[2],t[3])
def pool_prepare(pool):
    """pregateste splice-ul: canonic, quote WSOL, VQ implicit, stari post-trade ordonate. Returneaza None daca splice-ul nu este demonstrabil exact."""
    if not pool or not pool.get("canonical") or not pool.get("quote_wsol"): return None
    ev=sorted(pool["events"],key=lambda a:(a[1],a[2],a[3]))
    if not ev: return None
    vq,nv=implied_vq(ev)
    if vq is None: return None
    if not (abs((ev[0][6]+vq)-pool["pool_quote"])<=max(0.05e9,0.05*pool["pool_quote"])): return None   # consistenta VQ + quote real initial vs quote la creare
    states=[(pool["cp_ts"],pool["cp_slot"],pool["cp_seq"],0,pool["pool_base"],pool["pool_quote"]-vq if pool["pool_quote"]>vq else ev[0][6],ev[0][11]+ev[0][12]+ev[0][13])]
    for a in ev: states.append((a[0],a[1],a[2],a[3],a[7],a[8],a[11]+a[12]+a[13]))
    return dict(vq=vq,states=states,n_vq=nv)
def simulate(rec,i_trig,dec_ts,N,land=LAND,cost_mult=1.0,pool=None):
    """pozitie proprie: intrare pe curba la ultima stare cu slot <= slot_declansator+land; apoi first-passage pe valoarea neta a lichidarii (TP 2x / SL 0,5x),
    cu continuare in pool dupa migrare (daca pool!=None). Returneaza per orizont: stare, pnl (SOL), venue, t_exit, si flag-uri."""
    T=rec["trades"]; trig=T[i_trig]; land_slot=trig[1]+land; gross=int(N*LAMP); fee=int(round(FEE_CURVE*cost_mult)); net_cost=int(NET_COST*cost_mult)
    comp_slot=rec.get("complete_slot"); comp_key=(rec["complete_slot"],rec["complete_seq"],10**9) if rec.get("complete_ts") is not None else None
    j=i_trig
    for q in range(i_trig+1,len(T)):
        if T[q][1]<=land_slot: j=q
        else: break
    if comp_key is not None and order_key(T[j])>=comp_key: return dict(status="NO_FILL_MIGRATED")
    if comp_slot is not None and comp_slot<=land_slot: return dict(status="NO_FILL_MIGRATED")
    st=T[j]; vs,vt,rs=st[10],st[11],st[8]; h,ds=curve_buy(vs,vt,gross,fee)
    if h<=0: return dict(status="NO_FILL")
    entry_ts=st[0]; out=dict(status="OK",entry_i=j,entry_ts=entry_ts,tokens=h,ds=ds)
    # traiectoria valorii nete: (ts, slot, seq, k, value_net, venue)
    path=[(entry_ts,st[1],st[2],st[3],curve_liq(vs,vt,rs,h,ds,fee),"curve")]; migrated=False; splice_ok=None
    hmax=dec_ts+max(HORIZONS.values())
    for t in T[j+1:]:
        if comp_key is not None and order_key(t)>=comp_key: break
        if t[0]>hmax: break
        path.append((t[0],t[1],t[2],t[3],curve_liq(t[10],t[11],t[8],h,ds,fee),"curve"))
    if comp_key is not None:
        migrated=True
        if pool is not None:
            splice_ok=True
            for s in pool["states"]:
                if s[0]>hmax: break
                path.append((s[0],s[1],s[2],s[3],pool_liq(s[4],s[5],pool["vq"],h,int(round(s[6]*cost_mult))),"pool"))
        else: splice_ok=False
    path.sort(key=lambda p:(p[1],p[2],p[3]))
    for hname,H in HORIZONS.items():
        res=dict(state="TIMEOUT_OTHER",venue="curve",t_exit=None,pnl=None,label_kind="CROSS_MIGRATION" if migrated and splice_ok else ("CURVE_ONLY" if not migrated else "CROSS_MIGRATION_LABEL_UNAVAILABLE"))
        end_ts=dec_ts+H; trigger=None; lastv=path[0]
        for p in path:
            if p[0]>end_ts: break
            lastv=p; nv=p[4]-net_cost
            if nv<=0.5*gross: trigger=("SL_FIRST",p); break
            if nv>=2*gross: 
                # acelasi slot cu un SL? (regula 10: SL castiga) -> verificam restul starilor din acelasi slot
                same=[q for q in path if q[1]==p[1] and q[0]<=end_ts]
                if any(q[4]-net_cost<=0.5*gross for q in same): trigger=("SL_FIRST",p)
                else: trigger=("TP_FIRST",p)
                break
        if migrated and trigger is not None and (trigger[1][1],trigger[1][2],trigger[1][3])<comp_key: res["label_kind"]="CURVE_RESOLVED_BEFORE_MIGRATION"
        if migrated and not splice_ok and (trigger is None or (trigger[1][1],trigger[1][2],trigger[1][3])>=comp_key):
            res.update(state=None,pnl=None,unavailable=True); out[hname]=res; continue
        if trigger is None:
            res["pnl"]=(lastv[4]-net_cost-gross)/LAMP; res["venue"]=lastv[5]; res["t_exit"]=min(end_ts,lastv[0])-dec_ts; res["exit_value_ratio"]=lastv[4]/gross
        else:
            kind,p=trigger; exit_slot=p[1]+land; ex=p
            for q in path:
                if q[1]>exit_slot: break
                if (q[1],q[2],q[3])>=(p[1],p[2],p[3]): ex=q
            res["state"]=kind; res["pnl"]=(ex[4]-net_cost-gross)/LAMP; res["venue"]=ex[5]; res["t_exit"]=p[0]-dec_ts; res["exit_value_ratio"]=ex[4]/gross; res["trigger_value_ratio"]=p[4]/gross
        out[hname]=res
    out["migrated_in_window"]=migrated; out["splice_ok"]=splice_ok; return out
# ---------------- modele numpy ----------------
def X_of(rows,feats,fill=None):
    X=np.array([[(r["f"].get(k) if r["f"].get(k) is not None else np.nan) for k in feats] for r in rows],dtype=float)
    if fill is None: fill=np.nanmedian(X,axis=0); fill=np.where(np.isnan(fill),0,fill)
    X=np.where(np.isnan(X),fill,X); return np.sign(X)*np.log1p(np.abs(X)),fill
def softmax(Z): Z=Z-Z.max(1,keepdims=True); E=np.exp(Z); return E/E.sum(1,keepdims=True)
def fit_mlogit(X,Y,l2=1.0,it=1500,lr=0.1):
    mu,sd=X.mean(0),X.std(0)+1e-9; Xs=(X-mu)/sd; n,d=Xs.shape; K=Y.shape[1]; W=np.zeros((d,K)); b=np.log(np.clip(Y.mean(0),1e-4,1)); b=b-b.mean()
    for _ in range(it): P=softmax(Xs@W+b); G=Xs.T@(P-Y)/n+l2*W/n; W-=lr*G; b-=lr*(P-Y).mean(0)
    return dict(kind="mlogit",W=W.tolist(),b=b.tolist(),mu=mu.tolist(),sd=sd.tolist())
def pred_mlogit(m,X): return softmax(((X-np.array(m["mu"]))/np.array(m["sd"]))@np.array(m["W"])+np.array(m["b"]))
def binize(X,edges): return np.stack([np.searchsorted(edges[j],X[:,j],side="right") for j in range(X.shape[1])],1).astype(np.int64)
def make_edges(X,nb=16): return [np.unique(np.quantile(X[:,j],np.linspace(0,1,nb+1)[1:-1])).tolist() for j in range(X.shape[1])]
def tree_fit(B,g,h,depth,min_leaf=50,lam=1.0):
    def best_split(idx):
        G=g[idx].sum(); H=h[idx].sum(); base=G*G/(H+lam); best=None
        for j in range(B.shape[1]):
            bj=B[idx,j]; nb=int(bj.max())+1 if len(bj) else 0
            if nb<2: continue
            Gb=np.bincount(bj,weights=g[idx],minlength=nb); Hb=np.bincount(bj,weights=h[idx],minlength=nb); Cb=np.bincount(bj,minlength=nb)
            GL=np.cumsum(Gb)[:-1]; HL=np.cumsum(Hb)[:-1]; CL=np.cumsum(Cb)[:-1]; GR=G-GL; HR=H-HL; CR=len(idx)-CL
            gain=GL*GL/(HL+lam)+GR*GR/(HR+lam)-base; gain[(CL<min_leaf)|(CR<min_leaf)]=-1; kk=int(np.argmax(gain))
            if gain[kk]>0 and (best is None or gain[kk]>best[0]): best=(float(gain[kk]),j,kk)
        return best
    def build(idx,d):
        leaf=float(-g[idx].sum()/(h[idx].sum()+lam))
        if d>=depth or len(idx)<2*min_leaf: return dict(leaf=leaf)
        s=best_split(idx)
        if s is None: return dict(leaf=leaf)
        _,j,kk=s; L=idx[B[idx,j]<=kk]; R=idx[B[idx,j]>kk]; return dict(j=j,k=kk,L=build(L,d+1),R=build(R,d+1))
    return build(np.arange(len(g)),0)
def tree_pred(t,B):
    out=np.zeros(len(B))
    def rec(node,idx):
        if not len(idx): return
        if "leaf" in node: out[idx]=node["leaf"]; return
        m=B[idx,node["j"]]<=node["k"]; rec(node["L"],idx[m]); rec(node["R"],idx[~m])
    rec(t,np.arange(len(B))); return out
def fit_mgbm(X,Y,rounds=120,lr=0.1,depth=2):
    edges=make_edges(X); B=binize(X,edges); K=Y.shape[1]; F=np.tile(np.log(np.clip(Y.mean(0),1e-4,1)),(len(Y),1)); f0=F[0].tolist(); trees=[]
    for _ in range(rounds):
        P=softmax(F); rt=[]
        for c in range(K):
            g=P[:,c]-Y[:,c]; h=P[:,c]*(1-P[:,c])+1e-6; t=tree_fit(B,g,h,depth); rt.append(t); F[:,c]+=lr*tree_pred(t,B)
        trees.append(rt)
    return dict(kind="mgbm",edges=edges,trees=trees,lr=lr,f0=f0)
def pred_mgbm(m,X):
    B=binize(X,[np.array(e) for e in m["edges"]]); F=np.tile(np.array(m["f0"]),(len(X),1))
    for rt in m["trees"]:
        for c,t in enumerate(rt): F[:,c]+=m["lr"]*tree_pred(t,B)
    return softmax(F)
def fit_mrf(X,Y,n_trees=30,depth=3,seed=11):
    rng=np.random.default_rng(seed); edges=make_edges(X); B=binize(X,edges); K=Y.shape[1]; trees=[]
    for _ in range(n_trees):
        idx=rng.integers(0,len(Y),len(Y)); feats=rng.choice(X.shape[1],max(3,X.shape[1]//3),replace=False).tolist(); Bs=B[idx][:,feats]; Ys=Y[idx]; p0=Ys.mean(0); rt=[]
        for c in range(K):
            g=p0[c]-Ys[:,c]; h=np.full(len(Ys),p0[c]*(1-p0[c])+1e-6); rt.append(tree_fit(Bs,g,h,depth,min_leaf=30))
        trees.append((feats,rt,p0.tolist()))
    return dict(kind="mrf",edges=edges,trees=trees)
def pred_mrf(m,X):
    B=binize(X,[np.array(e) for e in m["edges"]]); ps=[]
    for feats,rt,p0 in m["trees"]:
        P=np.stack([np.clip(p0[c]+tree_pred(t,B[:,feats]),1e-4,1) for c,t in enumerate(rt)],1); ps.append(P/P.sum(1,keepdims=True))
    return np.mean(ps,0)
def predict(m,X): return {"mlogit":pred_mlogit,"mgbm":pred_mgbm,"mrf":pred_mrf}[m["kind"]](m,X)
def fit_gbm_reg(X,y,rounds=100,lr=0.1,depth=2):
    edges=make_edges(X); B=binize(X,edges); f0=float(y.mean()); F=np.full(len(y),f0); trees=[]
    for _ in range(rounds):
        g=F-y; h=np.ones(len(y)); t=tree_fit(B,g,h,depth,min_leaf=80); trees.append(t); F+=lr*tree_pred(t,B)
    return dict(kind="gbm_reg",edges=edges,trees=trees,lr=lr,f0=f0)
def pred_gbm_reg(m,X):
    B=binize(X,[np.array(e) for e in m["edges"]]); F=np.full(len(X),m["f0"])
    for t in m["trees"]: F+=m["lr"]*tree_pred(t,B)
    return F
# ---------------- calibrare (CAL) si metrici ----------------
def fit_vector_scaling(P,Y,it=3000,lr=0.05):
    """calibrare multiclass: softmax(a_k * log p_k + b_k), potrivita pe CAL prin gradient pe log loss; probabilitatile raman normalizate."""
    Z=np.log(np.clip(P,1e-6,1)); K=P.shape[1]; a=np.ones(K); b=np.zeros(K); n=len(P)
    for _ in range(it):
        Q=softmax(Z*a+b); G=(Q-Y); a-=lr*(G*Z).mean(0); b-=lr*G.mean(0)
    return dict(a=a.tolist(),b=b.tolist())
def apply_cal(c,P): return softmax(np.log(np.clip(P,1e-6,1))*np.array(c["a"])+np.array(c["b"]))
def log_loss(P,Y): return float(-(Y*np.log(np.clip(P,1e-9,1))).sum(1).mean())
def brier_mc(P,Y): return float(((P-Y)**2).sum(1).mean())
def ece_bin(p,y,nb=10):
    e=0.0; bins=np.linspace(0,1,nb+1)
    for a,b in zip(bins,bins[1:]):
        m=(p>=a)&(p<b)
        if m.any(): e+=m.mean()*abs(p[m].mean()-y[m].mean())
    return float(e)
def reliability(p,y,nb=10):
    bins=np.linspace(0,1,nb+1); out=[]
    for a,b in zip(bins,bins[1:]):
        m=(p>=a)&(p<b)
        if m.any(): out.append(dict(bin=f"{a:.1f}-{b:.1f}",n=int(m.sum()),pred=float(p[m].mean()),obs=float(y[m].mean())))
    return out
def evstats(v,groups=None):
    v=np.asarray(v,float)
    if len(v)==0: return None
    w=v[v>0]; l=v[v<=0]; srt=np.sort(v)[::-1]; n=len(v); out=dict(N=n,EV=float(v.mean()),median=float(np.median(v)),PF=float(w.sum()/abs(l.sum())) if len(l) and l.sum()<0 else (float("inf") if len(w) else 0.0),win_rate=float((v>0).mean()),EX_BEST_1PCT=float(srt[max(1,int(math.ceil(n*0.01))):].mean()) if n>1 else float(v.mean()))
    if groups is not None:
        pos=collections.defaultdict(float)
        for g,x in zip(groups,v): pos[g]+=max(0.0,x)
        gp=sum(pos.values()) or 1e-12; out["max_group_share"]=float(max(pos.values())/gp) if pos else 0.0
    return out
def cluster_ci(v,clusters,B=4000,seed=20260905):
    """bootstrap pe clustere (ore de decizie): CI95 si LCB90 ale mediei."""
    v=np.asarray(v,float); cl=np.asarray(clusters); u=np.unique(cl)
    if len(v)==0: return None
    if len(u)<2: return dict(CI95=(float(v.mean()),float(v.mean())),LCB90=float(v.mean()),clusters=int(len(u)))
    rng=np.random.default_rng(seed); groups=[v[cl==c] for c in u]; means=[]
    for _ in range(B):
        pick=rng.integers(0,len(u),len(u)); s=np.concatenate([groups[i] for i in pick]); means.append(s.mean())
    means=np.sort(means); return dict(CI95=(float(means[int(0.025*B)]),float(means[int(0.975*B)-1])),LCB90=float(means[int(0.10*B)]),clusters=int(len(u)))
def sha256_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()
def sha256_obj(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":")).encode()).hexdigest()
# ---------------- politica inghetata (grila fixa; evaluata exclusiv pe CAL) ----------------
POLICY_GRID=dict(band=[(20,60),(20,70),(30,70),(30,80)],p_tp_min=[0.30,0.35,0.40,0.45],p_sl_max=[0.20,0.30,0.40])
def notional_tag(N): return {0.25:"025",0.5:"050",1.0:"100"}[N]
def eligible(sr,pol,N):
    """sr: rand punctat {landmark, f, p_tp, p_sl, ev, ev_lcb, gap_known}. Conditii universale: banda ∩ [ENTRY_MIN, ENTRY_MAX], headroom curve-only >= 2 pentru notional,
    P_TP_FIRST >= min, P_SL_FIRST <= max, EV prezis > 0, EV LCB90 > 0. Returneaza (bool, motiv)."""
    lo,hi=pol["band"]; lo=max(lo,ENTRY_MIN); hi=min(hi,ENTRY_MAX); Lm=sr["landmark"]
    if not (lo<=Lm<=hi): return False,"OUT_OF_BAND"
    if sr["f"].get(f"headroom_{notional_tag(N)}",0.0)<2.0: return False,"HEADROOM_FAIL"
    if sr.get("gap_known"): return False,"DATA_GAP"
    if sr["p_tp"]<pol["p_tp_min"]: return False,"P_TP_BELOW_MIN"
    if sr["p_sl"]>pol["p_sl_max"]: return False,"P_SL_ABOVE_MAX"
    if not (sr["ev"]>0): return False,"EV_NOT_POSITIVE"
    if not (sr["ev_lcb"]>0): return False,"EV_LCB90_NOT_POSITIVE"
    return True,"ELIGIBLE"
def decide_mint(scored_rows,pol,N):
    """exact o decizie per mint: primul landmark eligibil (in ordinea landmark-urilor)."""
    for sr in sorted(scored_rows,key=lambda r:r["landmark"]):
        ok,why=eligible(sr,pol,N)
        if ok: return sr
    return None
# ---------------- garda de gap (identica in batch si replay) ----------------
GAP_JUMP_S=120; GAP_LOOKBACK_S=600
def gap_windows_from_create_times(times,jump=GAP_JUMP_S):
    """ferestre de discontinuitate din seria timpilor de sosire ai CreateEvent-urilor (salt > jump secunde)."""
    W=[]; prev=None
    for t in times:
        if prev is not None and t-prev>jump: W.append((prev,t))
        prev=t
    return W
def known_gap(ts,windows,lookback=GAP_LOOKBACK_S):
    """True daca o fereastra de gap (deconectare din jurnal sau discontinuitate) s-a terminat in ultimele `lookback` s sau este in curs la ts: contextul de regim este incomplet."""
    for s,e in windows:
        if s<=ts and e>=ts-lookback: return True
    return False
