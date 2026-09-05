#!/usr/bin/env python3
"""CURVE2X V3 RECLAIM — watcher STREAMING (implementare separata de batch): masina de stari incrementala per mint, trasaturi calculate la decizie din starea acumulata,
index rolling de portofele cu deque. Emite exclusiv REJECT / WATCH (niciodata PAPER_CANDIDATE; policy_enabled=false). Mod suportat: --mode replay pe banda existenta.
Garzi: --paper-only obligatoriu, model hash, self-check (fara trimitere/semnare de tranzactii, fara chei, fara endpoint-uri), schema necunoscuta, stop file, RLIMIT_AS."""
import os,sys,json,gzip,glob,argparse,hashlib,collections,resource,zlib,time,math,statistics
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L; import numpy as np
FORB=tuple(a+b for a,b in (("send","Transaction"),("sign","Transaction"),("PRIVATE","_KEY"),("SECRET","_KEY"),("wss",":"+"//"),("heli","us-rpc")))
def die(m,code=2): print(f"FATAL | {m}",flush=True); sys.exit(code)
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
class Mint:
    __slots__=("creator","create_ts","T","a","h","ds","runmax","state","pb","trough","maxpb","done","complete")
    def __init__(s,creator,ts): s.creator=creator; s.create_ts=ts; s.T=[]; s.a=None; s.h=s.ds=None; s.runmax=None; s.state="TRACK"; s.pb=None; s.trough=None; s.maxpb=None; s.done=False; s.complete=False
class Stream:
    """motor streaming: consuma evenimente si emite decizii (o singura data per mint)."""
    def __init__(s): s.M={}; s.wal={}; s.decisions=[]; s.last_prune=0
    def create(s,ts,slot,seq,mint,creator):
        if mint not in s.M: s.M[mint]=Mint(creator,ts)
        if ts-s.last_prune>600: s.prune(ts)
    def complete(s,mint):
        m=s.M.get(mint)
        if m: m.complete=True
    def prune(s,ts):
        s.last_prune=ts
        for k in [k for k,m in s.M.items() if ts-m.create_ts>V.YOUNG_WINDOW+120]: del s.M[k]
        for u in [u for u,d in s.wal.items() if (not d) or d[-1][0]<ts-V.WALLET_WINDOW]: del s.wal[u]
    def trade(s,ts,slot,seq,k,mint,user,sol,tok,is_buy,rs,rt,vs,vt):
        m=s.M.get(mint)
        if is_buy and m is not None and ts<=m.create_ts+V.YOUNG_WINDOW:   # indexul de reutilizare acopera doar lansarile tinere (CreateEvent vazut, varsta <= 3720 s), identic cu fluxul batch
            d=s.wal.get(user)
            if d is None: d=s.wal[user]=collections.deque()
            d.append((ts,mint))
            while d and d[0][0]<ts-V.WALLET_WINDOW-1: d.popleft()
        if m is None or m.complete or m.done or ts>m.create_ts+V.DEC_WINDOW+V.H_PRIMARY: return
        t=(ts,slot,seq,k,user,sol,tok,is_buy,rs,rt,vs,vt); m.T.append(t)
        if ts>m.create_ts+V.DEC_WINDOW: return
        if m.a is None:
            if rs>=V.ANCHOR_PROG*L.TARGET_RS:
                h,ds=L.curve_buy(vs,vt,int(V.N_REF*L.LAMP))
                if h<=0: m.done=True; return
                m.a=len(m.T)-1; m.h,m.ds=h,ds; m.runmax=L.curve_liq(vs,vt,rs,h,ds)
            return
        v=L.curve_liq(vs,vt,rs,m.h,m.ds); i=len(m.T)-1
        if m.state=="TRACK":
            if v>m.runmax: m.runmax=v
            elif m.runmax>0 and v<=(1-V.PB_DROP)*m.runmax: m.state="PB"; m.pb=i; m.maxpb=m.runmax; m.trough=(i,v)
            return
        if v<m.trough[1]: m.trough=(i,v)
        if ts-m.T[m.pb][0]>V.RECLAIM_MAX_S: m.state="TRACK"; m.runmax=v; m.pb=None; m.trough=None; m.maxpb=None; return
        if m.maxpb>m.trough[1] and v>=m.trough[1]+V.RECLAIM_FRAC*(m.maxpb-m.trough[1]) and m.trough[0]<i:
            m.done=True; d=dict(anchor=m.a,pb=m.pb,trough=m.trough[0],dec=i,h_ref=m.h,ds_ref=m.ds,maxpb=m.maxpb,trough_v=m.trough[1],v_dec=v)
            post_buyers={x[4] for x in m.T[m.trough[0]+1:] if x[7]}; n=0
            for u in post_buyers:
                dq=s.wal.get(u) or (); others={mm for (t_,mm) in dq if t_<=ts and t_>=ts-V.WALLET_WINDOW and mm!=mint}
                n+=(1 if others else 0)
            reuse=(n/len(post_buyers)) if post_buyers else 0.0
            f=s.features(m,d,reuse); s.decisions.append(dict(mint=mint,creator=m.creator,create_ts=m.create_ts,ts=ts,slot=slot,seq=seq,k=k,dec_i=i,f=f))
    def features(s,m,d,reuse):
        """implementare streaming a definitiilor (acumulatori explciti; aceleasi formule ca in v3_lib.features, cod separat)."""
        T=m.T[:d["dec"]+1]; ta,tp,tt,td=T[d["anchor"]],T[d["pb"]],T[d["trough"]],T[-1]; f={}
        depth=1-d["trough_v"]/d["maxpb"] if d["maxpb"]>0 else 0.0; f["pullback_depth"]=depth; f["pullback_duration_s"]=tt[0]-tp[0]; f["pullback_slots"]=tt[1]-tp[1]; f["pullback_trades"]=d["trough"]-d["pb"]
        f["reclaim_duration_s"]=td[0]-tt[0]; f["reclaim_slots"]=td[1]-tt[1]; f["reclaim_trades"]=d["dec"]-d["trough"]; rf=(d["v_dec"]-d["trough_v"])/(d["maxpb"]-d["trough_v"]) if d["maxpb"]>d["trough_v"] else 0.0; f["recovery_fraction"]=rf; f["recovery_speed"]=rf/max(0.4,f["reclaim_duration_s"])
        f["time_since_anchor_s"]=td[0]-ta[0]; f["anchor_progress"]=ta[8]/L.TARGET_RS
        bpre=spre=bpost=spost=0; sellers=set(); bought=collections.Counter(); sold=collections.Counter(); bu=collections.Counter(); seen_pre_trough=set(); newpost=set(); prebuyers=set(); bw=sw=0; ps=collections.defaultdict(set); pc=collections.Counter()
        for i,t in enumerate(T):
            if t[7]: bought[t[4]]+=t[6]; bu[t[4]]+=t[5]
            else: sold[t[4]]+=t[6]
            if i<d["pb"] and t[7]: prebuyers.add(t[4])
            if i<=d["trough"] and t[7]: seen_pre_trough.add(t[4])
            if d["pb"]<=i<=d["trough"]:
                if t[7]: bpre+=t[5]
                else: spre+=t[5]
            if i>d["trough"]:
                if t[7]: bpost+=t[5]; newpost.add(t[4]); ps[t[1]].add(t[4]); pc[t[1]]+=1
                else: spost+=t[5]
            if i>=d["pb"]:
                if t[7]: bw+=t[5]
                else: sw+=t[5]; sellers.add(t[4])
        f["buy_vol_pre"]=bpre/L.LAMP; f["sell_vol_pre"]=spre/L.LAMP; f["buy_vol_post"]=bpost/L.LAMP; f["sell_vol_post"]=spost/L.LAMP
        dpre=max(0.4,f["pullback_duration_s"]); dpost=max(0.4,f["reclaim_duration_s"]); ipre=f["sell_vol_pre"]/dpre; ipost=f["sell_vol_post"]/dpost; f["sell_intensity_change"]=ipost-ipre; f["sell_intensity_ratio"]=ipost/(ipre+1e-6)
        f["uniq_sellers_window"]=len(sellers); sb=sum(bought[u] for u in sold); f["seller_inventory_decline"]=min(1.0,sum(sold.values())/sb) if sb>0 else 0.0
        f["uniq_buyers"]=len(bu); f["new_buyers_post"]=len(newpost-seen_pre_trough); f["buyer_retention"]=(sum(1 for u in prebuyers if sold[u]==0)/len(prebuyers)) if prebuyers else 0.0
        f["imbalance_window"]=(bw-sw)/(bw+sw) if (bw+sw)>0 else 0.0; f["net_quote_flow_window"]=(bw-sw)/L.LAMP
        sv=sorted(bu.values(),reverse=True); tot=sum(sv) or 1; f["top1_share"]=sv[0]/tot if sv else 0.0; f["top3_share"]=sum(sv[:3])/tot; f["top10_share"]=sum(sv[:10])/tot; f["hhi"]=sum((x/tot)**2 for x in sv)
        f["wallet_reuse_share"]=reuse; f["same_slot_max_wallets"]=max((len(v) for v in ps.values()),default=0); f["same_slot_share"]=(max(pc.values())/sum(pc.values())) if pc else 0.0
        cr=m.creator; net_supply=sum(bought.values())-sum(sold.values()) or 1; f["creator_inventory_share"]=max(0,bought[cr]-sold[cr])/net_supply; f["creator_sold_flag"]=1.0 if sold[cr]>0 else 0.0; f["creator_sell_share"]=(sold[cr]/bought[cr]) if bought[cr]>0 else 0.0
        rs,vs,vt=td[8],td[10],td[11]; f["progress"]=rs/L.TARGET_RS; f["dist_to_migration_sol"]=(L.TARGET_RS-rs)/L.LAMP; f["rs_sol"]=rs/L.LAMP; f["vs_sol"]=vs/L.LAMP
        hr,tok,dsn=L.curve_headroom(vs,vt,rs,int(V.N_REF*L.LAMP)); f["headroom_025"]=hr; f["slippage_bp_025"]=((dsn/tok)/(vs/vt)-1)*1e4 if (tok>0 and vs>0) else 1e5; f["n_trades_total"]=len(T)
        return f
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",required=True); ap.add_argument("--source",required=True); ap.add_argument("--paper-only",action="store_true"); ap.add_argument("--model-hash",required=True); ap.add_argument("--stop-file",required=True); ap.add_argument("--out",default=os.path.join(HERE,"watcher_signals.jsonl")); ap.add_argument("--max-events",type=int,default=0); ap.add_argument("--quiet",action="store_true")
    a=ap.parse_args()
    if not a.paper_only: die("PAPER_ONLY_REQUIRED")
    if a.mode!="replay": die(f"MODE_NOT_SUPPORTED: {a.mode} (doar replay; nu exista mod live)")
    src=open(__file__).read()+open(os.path.join(HERE,"v3_lib.py")).read()
    for tok in FORB:
        if tok in src: die(f"SELF_CHECK_FAILED {tok}")
    resource.setrlimit(resource.RLIMIT_AS,(3*2**30,)*2)
    raw=open(os.path.join(HERE,"model_artifact.json"),"rb").read(); mh=hashlib.sha256(raw).hexdigest()
    if mh!=a.model_hash: die(f"MODEL_HASH_MISMATCH {mh[:16]}.. != {a.model_hash[:16]}..")
    art=json.loads(raw); M=art["models"]; fl=art["features"]; fill=np.array(art["fill"]); pol=art["policy"]; armed=bool(art.get("policy_enabled") is True)
    print(f"START | mode=replay paper_only=True model_hash={mh[:16]}.. policy={pol} policy_enabled={art.get('policy_enabled')} final_verdict={art.get('final_verdict')} => PAPER_CANDIDATE_POSSIBLE=False (V3 emite doar WATCH)",flush=True)
    files=sorted(glob.glob(os.path.join(a.source,"events_*.jsonl.gz"))) if os.path.isdir(a.source) else sorted(glob.glob(a.source)); E=Stream(); seq=0; n_ev=0; counts=collections.Counter(); out=open(a.out,"w"); t0=time.time(); unknown=collections.Counter()
    def flush():
        while E.decisions:
            d=E.decisions.pop(0); counts["decisions"]+=1; X,_=L.X_of([d],fl,fill); P=L.apply_cal(M["cal"],L.predict(M["clf"],X)); ev=float(L.pred_gbm_reg(M["reg"],X)[0]); rs=M["regstats"]; dec=int(np.clip(np.searchsorted(rs["edges"],ev,side="right"),0,4)); n=max(1,rs["n"][dec]); p=float(P[0,0])
            W=np.array(M["drv"]["W"]); z=(X[0]-np.array(M["drv"]["mu"]))/np.array(M["drv"]["sd"]); contrib=z*(W[:,0]-W[:,1]); top=[fl[j] for j in np.argsort(-contrib)[:3]]; bot=[fl[j] for j in np.argsort(contrib)[:3]]
            sc=dict(p_tp=p,p_sl=float(P[0,1]),p_to=float(P[0,2]),ev=ev,ev_lcb=ev-1.2816*rs["sd"][dec]/math.sqrt(n),uncertainty=math.sqrt(p*(1-p)/n),n_similar=int(n),top_positive=top,top_risk=bot)
            if p>=pol["p_tp_min"] and ev>0: action,why="WATCH","ELIGIBLE_POLICY_DISABLED"
            else: action,why="REJECT",("P_TP_BELOW_MIN" if p<pol["p_tp_min"] else "EV_NOT_POSITIVE")
            counts[action]+=1; rec=dict(mint_id=V.mint_id(d["mint"]),mint=d["mint"],ts=d["ts"],seq=d["seq"],k=d["k"],dec_i=d["dec_i"],action=action,reason=why,**sc,f=d["f"]); out.write(json.dumps(rec,default=float)+"\n")
            if not a.quiet or action=="WATCH": print(f"SIGNAL | MINT={rec['mint_id']} | AGE={d['ts']-d['create_ts']}s | PROGRESS={d['f']['progress']:.2f} | ACTION={action} | REASON={why} | P_TP_FIRST={p:.3f} | P_SL_FIRST={sc['p_sl']:.3f} | P_TIMEOUT={sc['p_to']:.3f} | EXPECTED_NET_SOL={ev:+.4f} | EXPECTED_NET_LCB90={sc['ev_lcb']:+.4f} | PREDICTION_UNCERTAINTY={sc['uncertainty']:.3f} | TOP_POSITIVE_DRIVERS={','.join(top)} | TOP_RISK_DRIVERS={','.join(bot)} | PAPER_ONLY",flush=True)
    for fp in files:
        for line in readlines(fp):
            if '"src":"pump"' not in line: seq+=1; continue
            try: r=json.loads(line); t=int(r["t"]); slot=r["slot"]
            except Exception: unknown["BAD_RECORD"]+=1; seq+=1; continue
            for k,e in enumerate(r["events"]):
                ev=e.get("ev")
                if ev=="CreateEvent" and "mint" in e and "user" in e: E.create(t,slot,seq,e["mint"],e["user"])
                elif ev=="TradeEvent" and all(x in e for x in ("mint","user","sol","tok","is_buy","rsol","rtok","vsol","vtok")): E.trade(e.get("ts") or t,slot,seq,k,e["mint"],e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"])
                elif ev=="CompleteEvent" and "mint" in e: E.complete(e["mint"])
                else: unknown[ev or "NONE"]+=1
                n_ev+=1
            flush(); seq+=1
            if seq%300000==0:
                print(f"HB | file={os.path.basename(fp)} seq={seq} events={n_ev} decisions={counts['decisions']} watch={counts['WATCH']} reject={counts['REJECT']} elapsed={time.time()-t0:.0f}s",flush=True)
                if os.path.exists(a.stop_file): print("STOP | stop file",flush=True); out.close(); return
                if sum(unknown.values())>1000: die("UNKNOWN_SCHEMA_GUARD")
            if a.max_events and n_ev>=a.max_events: break
        if a.max_events and n_ev>=a.max_events: break
    out.close(); print(f"DONE | events={n_ev} decisions={counts['decisions']} WATCH={counts['WATCH']} REJECT={counts['REJECT']} PAPER_CANDIDATE=0 unknown={dict(unknown)} elapsed={time.time()-t0:.0f}s | LIVE_TRADING_ENABLED=NO",flush=True)
if __name__=="__main__": main()
