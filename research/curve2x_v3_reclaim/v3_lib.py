"""CURVE2X V3 RECLAIM — HISTORICAL_DEV_NOT_SEALED. Definitii inghetate (anchor / pullback / trough / reclaim), trasaturi din trecutul deciziei (implementarea BATCH, per mint),
eticheta first-passage TP +100 % / SL -35 % / TIMEOUT (15 min) cu splice PumpSwap, modele reutilizate din V2 (import read-only). Zero RPC."""
import os,sys,math,json,bisect,collections,statistics,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(os.path.dirname(HERE),"curve2x_v2")); import curve2x_lib as L   # V2 read-only
LAMP=L.LAMP; N_REF=0.25; ANCHOR_PROG=0.40; PB_DROP=0.10; RECLAIM_FRAC=0.75; RECLAIM_MAX_S=120; DEC_WINDOW=1860; TP_MULT=2.0; SL_MULT=0.65; H_PRIMARY=900
HORIZONS={"15M":900}; YOUNG_WINDOW=3720; LAND=3; LAND_STRESS=5; COST_STRESS=1.25; WALLET_WINDOW=3600
FEATS=["pullback_depth","pullback_duration_s","pullback_slots","pullback_trades","reclaim_duration_s","reclaim_slots","reclaim_trades","recovery_fraction","recovery_speed","time_since_anchor_s","anchor_progress",
 "buy_vol_pre","sell_vol_pre","buy_vol_post","sell_vol_post","sell_intensity_change","sell_intensity_ratio","uniq_sellers_window","seller_inventory_decline","uniq_buyers","new_buyers_post","buyer_retention",
 "imbalance_window","net_quote_flow_window","top1_share","top3_share","top10_share","hhi","wallet_reuse_share","same_slot_max_wallets","same_slot_share","creator_inventory_share","creator_sold_flag","creator_sell_share",
 "progress","dist_to_migration_sol","rs_sol","vs_sol","headroom_025","slippage_bp_025","n_trades_total"]
STATE_FEATS=["progress","dist_to_migration_sol","rs_sol","vs_sol","headroom_025","slippage_bp_025","anchor_progress","time_since_anchor_s"]
def ref_value(st,h,ds): return L.curve_liq(st[10],st[11],st[8],h,ds)
def detect(trades,create_ts,complete_key=None):
    """masina de stari pe lista de trade-uri (ordinea benzii). trades: [ts,slot,seq,k,user,sol,tok,is_buy,rs,rt,vs,vt]. Returneaza dict cu indicii anchor/pb/trough/dec sau None.
    Se opreste la prima decizie valida (o decizie per mint)."""
    a=None; h=ds=None; runmax=None; state="TRACK"; pb=None; trough=None; maxpb=None
    for i,t in enumerate(trades):
        if complete_key is not None and (t[1],t[2],t[3])>=complete_key: return None
        if t[0]>create_ts+DEC_WINDOW: return None
        if a is None:
            if t[8]>=ANCHOR_PROG*L.TARGET_RS:
                h,ds=L.curve_buy(t[10],t[11],int(N_REF*LAMP))
                if h<=0: return None
                a=i; runmax=ref_value(t,h,ds)
            continue
        v=ref_value(t,h,ds)
        if state=="TRACK":
            if v>runmax: runmax=v
            elif runmax>0 and v<=(1-PB_DROP)*runmax: state="PB"; pb=i; maxpb=runmax; trough=(i,v)
        else:
            if v<trough[1]: trough=(i,v)
            if t[0]-trades[pb][0]>RECLAIM_MAX_S: state="TRACK"; runmax=v; pb=None; trough=None; maxpb=None; continue
            if maxpb>trough[1] and v>=trough[1]+RECLAIM_FRAC*(maxpb-trough[1]) and trough[0]<i: return dict(anchor=a,pb=pb,trough=trough[0],dec=i,h_ref=h,ds_ref=ds,maxpb=maxpb,trough_v=trough[1],v_dec=v)
    return None
def features(trades,create_ts,creator,d,wallet_reuse_share):
    """trasaturi EXCLUSIV din trade-urile <= decizie (indicele d['dec']); wallet_reuse_share este calculat separat (context cross-mint, doar trecut)."""
    T=trades[:d["dec"]+1]; ta,tp,tt,td=T[d["anchor"]],T[d["pb"]],T[d["trough"]],T[-1]; f={}
    f["pullback_depth"]=1-d["trough_v"]/d["maxpb"] if d["maxpb"]>0 else 0.0; f["pullback_duration_s"]=tt[0]-tp[0]; f["pullback_slots"]=tt[1]-tp[1]; f["pullback_trades"]=d["trough"]-d["pb"]
    f["reclaim_duration_s"]=td[0]-tt[0]; f["reclaim_slots"]=td[1]-tt[1]; f["reclaim_trades"]=d["dec"]-d["trough"]; f["recovery_fraction"]=(d["v_dec"]-d["trough_v"])/(d["maxpb"]-d["trough_v"]) if d["maxpb"]>d["trough_v"] else 0.0
    f["recovery_speed"]=f["recovery_fraction"]/max(0.4,f["reclaim_duration_s"]); f["time_since_anchor_s"]=td[0]-ta[0]; f["anchor_progress"]=ta[8]/L.TARGET_RS
    pre=T[d["pb"]:d["trough"]+1]; post=T[d["trough"]+1:]; win=T[d["pb"]:]
    f["buy_vol_pre"]=sum(t[5] for t in pre if t[7])/LAMP; f["sell_vol_pre"]=sum(t[5] for t in pre if not t[7])/LAMP; f["buy_vol_post"]=sum(t[5] for t in post if t[7])/LAMP; f["sell_vol_post"]=sum(t[5] for t in post if not t[7])/LAMP
    dpre=max(0.4,f["pullback_duration_s"]); dpost=max(0.4,f["reclaim_duration_s"]); ipre=f["sell_vol_pre"]/dpre; ipost=f["sell_vol_post"]/dpost; f["sell_intensity_change"]=ipost-ipre; f["sell_intensity_ratio"]=ipost/(ipre+1e-6)
    f["uniq_sellers_window"]=len({t[4] for t in win if not t[7]})
    bought=collections.Counter(); sold=collections.Counter()
    for t in T: (bought if t[7] else sold)[t[4]]+=t[6]
    sb=sum(bought[u] for u in sold); f["seller_inventory_decline"]=min(1.0,sum(sold.values())/sb) if sb>0 else 0.0
    bu=collections.Counter()
    for t in T:
        if t[7]: bu[t[4]]+=t[5]
    f["uniq_buyers"]=len(bu); seen=set(t[4] for t in T[:d["trough"]+1] if t[7]); f["new_buyers_post"]=len({t[4] for t in post if t[7]}-seen)
    prebuyers={t[4] for t in T[:d["pb"]] if t[7]}; f["buyer_retention"]=(sum(1 for u in prebuyers if sold[u]==0)/len(prebuyers)) if prebuyers else 0.0
    bw=sum(t[5] for t in win if t[7]); sw=sum(t[5] for t in win if not t[7]); f["imbalance_window"]=(bw-sw)/(bw+sw) if (bw+sw)>0 else 0.0; f["net_quote_flow_window"]=(bw-sw)/LAMP
    sv=sorted(bu.values(),reverse=True); tot=sum(sv) or 1; f["top1_share"]=sv[0]/tot if sv else 0.0; f["top3_share"]=sum(sv[:3])/tot; f["top10_share"]=sum(sv[:10])/tot; f["hhi"]=sum((x/tot)**2 for x in sv)
    f["wallet_reuse_share"]=wallet_reuse_share
    ps=collections.defaultdict(set); pc=collections.Counter()
    for t in post:
        if t[7]: ps[t[1]].add(t[4]); pc[t[1]]+=1
    f["same_slot_max_wallets"]=max((len(v) for v in ps.values()),default=0); f["same_slot_share"]=(max(pc.values())/sum(pc.values())) if pc else 0.0
    net_supply=sum(bought.values())-sum(sold.values()) or 1; f["creator_inventory_share"]=max(0,bought[creator]-sold[creator])/net_supply; f["creator_sold_flag"]=1.0 if sold[creator]>0 else 0.0; f["creator_sell_share"]=(sold[creator]/bought[creator]) if bought[creator]>0 else 0.0
    rs,vs,vt=td[8],td[10],td[11]; f["progress"]=rs/L.TARGET_RS; f["dist_to_migration_sol"]=(L.TARGET_RS-rs)/LAMP; f["rs_sol"]=rs/LAMP; f["vs_sol"]=vs/LAMP
    hr,tok,dsn=L.curve_headroom(vs,vt,rs,int(N_REF*LAMP)); f["headroom_025"]=hr; f["slippage_bp_025"]=((dsn/tok)/(vs/vt)-1)*1e4 if (tok>0 and vs>0) else 1e5; f["n_trades_total"]=len(T)
    return f
def simulate_v3(rec,i_trig,dec_ts,N=N_REF,land=LAND,cost_mult=1.0,pool=None):
    """first-passage propriu: TP la valoare neta >= TP_MULT x gross, SL la <= SL_MULT x gross; SL castiga in acelasi slot; orizont 15 min; +land sloturi la intrare si iesire."""
    T=rec["trades"]; trig=T[i_trig]; land_slot=trig[1]+land; gross=int(N*LAMP); fee=int(round(L.FEE_CURVE*cost_mult)); net_cost=int(L.NET_COST*cost_mult)
    comp_key=(rec["complete_slot"],rec["complete_seq"],10**9) if (rec.get("complete_ts") is not None and rec["complete_ts"]<=dec_ts+H_PRIMARY) else None   # migrare relevanta doar in orizont; altfel eticheta este CURVE_ONLY
    j=i_trig
    for q in range(i_trig+1,len(T)):
        if T[q][1]<=land_slot: j=q
        else: break
    if comp_key is not None and (L.order_key(T[j])>=comp_key or rec["complete_slot"]<=land_slot): return dict(status="NO_FILL_MIGRATED")
    st=T[j]; h,ds=L.curve_buy(st[10],st[11],gross,fee)
    if h<=0: return dict(status="NO_FILL")
    path=[(st[0],st[1],st[2],st[3],L.curve_liq(st[10],st[11],st[8],h,ds,fee),"curve")]; migrated=False; splice_ok=None; hmax=dec_ts+H_PRIMARY
    for t in T[j+1:]:
        if comp_key is not None and L.order_key(t)>=comp_key: break
        if t[0]>hmax: break
        path.append((t[0],t[1],t[2],t[3],L.curve_liq(t[10],t[11],t[8],h,ds,fee),"curve"))
    if comp_key is not None:
        migrated=True
        if pool is not None:
            splice_ok=True
            for s in pool["states"]:
                if s[0]>hmax: break
                path.append((s[0],s[1],s[2],s[3],L.pool_liq(s[4],s[5],pool["vq"],h,int(round(s[6]*cost_mult))),"pool"))
        else: splice_ok=False
    path.sort(key=lambda p:(p[1],p[2],p[3])); res=dict(state="TIMEOUT_OTHER",venue="curve",t_exit=None,pnl=None,label_kind="CROSS_MIGRATION" if migrated and splice_ok else ("CURVE_ONLY" if not migrated else "CROSS_MIGRATION_LABEL_UNAVAILABLE"))
    trigger=None; lastv=path[0]
    for p in path:
        if p[0]>hmax: break
        lastv=p; nv=p[4]-net_cost
        if nv<=SL_MULT*gross: trigger=("SL_FIRST",p); break
        if nv>=TP_MULT*gross:
            same=[q for q in path if q[1]==p[1] and q[0]<=hmax]; trigger=("SL_FIRST",p) if any(q[4]-net_cost<=SL_MULT*gross for q in same) else ("TP_FIRST",p); break
    if migrated and trigger is not None and (trigger[1][1],trigger[1][2],trigger[1][3])<comp_key: res["label_kind"]="CURVE_RESOLVED_BEFORE_MIGRATION"
    if migrated and not splice_ok and (trigger is None or (trigger[1][1],trigger[1][2],trigger[1][3])>=comp_key): res.update(state=None,pnl=None,unavailable=True); return dict(status="OK",entry_i=j,tokens=h,migrated_in_window=migrated,splice_ok=splice_ok,**{"15M":res})
    if trigger is None: res["pnl"]=(lastv[4]-net_cost-gross)/LAMP; res["venue"]=lastv[5]; res["t_exit"]=min(hmax,lastv[0])-dec_ts; res["exit_value_ratio"]=lastv[4]/gross
    else:
        kind,p=trigger; exit_slot=p[1]+land; ex=p
        for q in path:
            if q[1]>exit_slot: break
            if (q[1],q[2],q[3])>=(p[1],p[2],p[3]): ex=q
        res["state"]=kind; res["pnl"]=(ex[4]-net_cost-gross)/LAMP; res["venue"]=ex[5]; res["t_exit"]=p[0]-dec_ts; res["exit_value_ratio"]=ex[4]/gross; res["trigger_value_ratio"]=p[4]/gross
    return dict(status="OK",entry_i=j,tokens=h,migrated_in_window=migrated,splice_ok=splice_ok,**{"15M":res})
def mint_id(m): return hashlib.sha256(("external-review-v1:"+m).encode()).hexdigest()[:16]

def chain_ok(T,i0,i1):
    """integritatea lantului de rezerve intre starile T[i0..i1] (post-stare[i] -> post-stare[i+1] consistenta cu trade-ul i+1: buy => vs creste cu sol net, sell => vs scade cu sol)."""
    for q in range(i0+1,i1+1):
        a,b=T[q-1],T[q]
        if b[7]==1:
            if b[10]-a[10]!=b[5] and abs((b[10]-a[10])-b[5])>b[5]*0.0130+2: return False   # sol brut vs net (taxa <= 1,3 %)
        else:
            if abs((a[10]-b[10])-b[5])>b[5]*0.0130+2: return False
        if b[8]-a[8]!=b[10]-a[10]: return False   # rezerva reala si virtuala se misca identic
    return True
def entry_positions(T,i_trig,land,comp_key):
    """pozitiile plauzibile ale tranzactiei noastre in slotul de aterizare (fara transactionIndex): inainte de primul trade din slot si dupa fiecare trade din slot.
    Returneaza lista de indici de stare j (starea de dinaintea tranzactiei noastre) sau None daca lantul de rezerve nu permite limite corecte."""
    land_slot=T[i_trig][1]+land; pre=i_trig; inslot=[]
    for q in range(i_trig+1,len(T)):
        if comp_key is not None and (T[q][1],T[q][2],T[q][3])>=comp_key: break
        if T[q][1]<land_slot: pre=q
        elif T[q][1]==land_slot: inslot.append(q)
        else: break
    pos=[pre]+inslot
    if inslot and not chain_ok(T,pre,inslot[-1]): return None
    return pos
def simulate_v3_bounds(rec,i_trig,dec_ts,N=N_REF,land=LAND,cost_mult=1.0,pool=None):
    """rezultatul pentru toate pozitiile plauzibile ale tranzactiei in slotul de intrare si in slotul de iesire. Returneaza optimistic / midpoint / conservative (primar = conservative),
    fiecare cu (state, pnl). Exclude (status=CHAIN_BREAK) cand lantul de rezerve nu permite limite."""
    T=rec["trades"]; gross=int(N*LAMP); fee=int(round(L.FEE_CURVE*cost_mult)); net_cost=int(L.NET_COST*cost_mult)
    comp_key=(rec["complete_slot"],rec["complete_seq"],10**9) if (rec.get("complete_ts") is not None and rec["complete_ts"]<=dec_ts+H_PRIMARY) else None
    land_slot=T[i_trig][1]+land
    if comp_key is not None and rec["complete_slot"]<=land_slot: return dict(status="NO_FILL_MIGRATED")
    pos=entry_positions(T,i_trig,land,comp_key)
    if pos is None: return dict(status="CHAIN_BREAK")
    hmax=dec_ts+H_PRIMARY; outcomes=[]
    for j in pos:
        st=T[j]; h,ds=L.curve_buy(st[10],st[11],gross,fee)
        if h<=0: continue
        # traiectoria: starile de dupa pozitia noastra (in slotul de aterizare, starile ulterioare pozitiei; apoi tot restul), plus pool
        path=[(st[0],st[1],st[2],st[3],L.curve_liq(st[10],st[11],st[8],h,ds,fee),"curve")]
        for t in T[j+1:]:
            if comp_key is not None and L.order_key(t)>=comp_key: break
            if t[0]>hmax: break
            path.append((t[0],t[1],t[2],t[3],L.curve_liq(t[10],t[11],t[8],h,ds,fee),"curve"))
        migrated=comp_key is not None; splice_ok=None
        if migrated:
            if pool is not None:
                splice_ok=True
                for s_ in pool["states"]:
                    if s_[0]>hmax: break
                    path.append((s_[0],s_[1],s_[2],s_[3],L.pool_liq(s_[4],s_[5],pool["vq"],h,int(round(s_[6]*cost_mult))),"pool"))
            else: splice_ok=False
        path.sort(key=lambda p:(p[1],p[2],p[3])); trigger=None; lastv=path[0]
        for p in path:
            if p[0]>hmax: break
            lastv=p; nv=p[4]-net_cost
            if nv<=SL_MULT*gross: trigger=("SL_FIRST",p); break
            if nv>=TP_MULT*gross:
                same=[q for q in path if q[1]==p[1] and q[0]<=hmax]; trigger=("SL_FIRST",p) if any(q[4]-net_cost<=SL_MULT*gross for q in same) else ("TP_FIRST",p); break
        if migrated and not splice_ok and (trigger is None or (trigger[1][1],trigger[1][2],trigger[1][3])>=comp_key): outcomes.append(dict(state=None,unavailable=True)); continue
        if trigger is None: outcomes.append(dict(state="TIMEOUT_OTHER",pnl_lo=(lastv[4]-net_cost-gross)/LAMP,pnl_hi=(lastv[4]-net_cost-gross)/LAMP,pnl_mid=(lastv[4]-net_cost-gross)/LAMP,venue=lastv[5],entry_pos=j)); continue
        kind,p=trigger; exit_slot=p[1]+land; vals=[q[4] for q in path if (q[1],q[2],q[3])>=(p[1],p[2],p[3]) and q[1]<=exit_slot]   # toate pozitiile plauzibile de iesire in slotul de aterizare (inclusiv 'inainte de primul trade' = starea de declansare)
        inx=[q for q in path if q[1]==exit_slot]; vals=[p[4]]+[q[4] for q in path if p[1]<q[1]<exit_slot]+[q[4] for q in inx] if exit_slot>p[1] else [p[4]]
        lo=min(vals); hi=max(vals); mid=sorted(vals)[len(vals)//2]; outcomes.append(dict(state=kind,pnl_lo=(lo-net_cost-gross)/LAMP,pnl_hi=(hi-net_cost-gross)/LAMP,pnl_mid=(mid-net_cost-gross)/LAMP,venue=p[5],entry_pos=j,n_exit_positions=len(vals)))
    if not outcomes: return dict(status="NO_FILL")
    if all(o.get("unavailable") for o in outcomes): return dict(status="OK",unavailable=True,migrated_in_window=comp_key is not None,n_entry_positions=len(pos))
    ok=[o for o in outcomes if not o.get("unavailable")]; cons=min(ok,key=lambda o:o["pnl_lo"]); opt=max(ok,key=lambda o:o["pnl_hi"]); mid=sorted(ok,key=lambda o:o["pnl_mid"])[len(ok)//2]
    return dict(status="OK",migrated_in_window=comp_key is not None,n_entry_positions=len(pos),conservative=dict(state=cons["state"],pnl=cons["pnl_lo"],venue=cons["venue"]),midpoint=dict(state=mid["state"],pnl=mid["pnl_mid"],venue=mid["venue"]),optimistic=dict(state=opt["state"],pnl=opt["pnl_hi"],venue=opt["venue"]),states=collections.Counter(o["state"] for o in ok))
