"""CURVE2X V3 RECLAIM — BUILD (implementarea BATCH, per mint, offline): (1) detectie anchor/pullback/trough/reclaim + trasaturi din cache-ul de curbe V2;
(2) wallet_reuse_share printr-o trecere separata peste flux (index rolling pe portofele cu liste sortate + bisect); (3) etichete first-passage (base / land5 / cost125);
(4) split cronologic din frozen_spec. Iesire: derived_v3/v3_rows.jsonl.gz, dataset_manifest.json, feature_dictionary.csv. Zero RPC."""
import os,sys,gzip,json,time,bisect,collections,datetime,hashlib,csv
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L
D2=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(HERE),"curve2x_v2","derived")); D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(HERE,"derived_v3"))
SPEC=json.load(open(os.path.join(HERE,"frozen_spec.json"))); SPL=SPEC["split"]
def utc(s): return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc).timestamp()
B=[(utc(SPL["train_end_utc"]),"TRAIN"),(utc(SPL["cal_end_utc"]),"CAL"),(utc(SPL["val_end_utc"]),"VAL")]; EMB=SPL["embargo_s"]
def split_of(ct):
    for b,name in B:
        if ct<b: return name if ct<b-EMB else "EMBARGO"
    return "CONF"
VAR={"base":dict(land=V.LAND,cost_mult=1.0),"land5":dict(land=V.LAND_STRESS,cost_mult=1.0),"cost125":dict(land=V.LAND,cost_mult=V.COST_STRESS)}
def main():
    t0=time.time(); man=json.load(open(f"{D2}/curve2x_pass_manifest.json")); OUT_W=[tuple(w) for w in man["outage_windows"]]
    def in_outage(a,b): return any(not (e<=a or s>=b) for s,e in OUT_W)
    dec={}; n_mints=0; n_anch=0; n_pb=0; recs_needed={}
    # etapa 1: detectie per mint (batch, offline)
    with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
        for line in f:
            r=json.loads(line); n_mints+=1; T=r["trades"]
            if not T: continue
            ck=(r["complete_slot"],r["complete_seq"],10**9) if r.get("complete_ts") is not None else None
            # contorizare anchor/pullback (diagnostic, fara outcome)
            anch=any(t[8]>=V.ANCHOR_PROG*L.TARGET_RS and t[0]<=r["create_ts"]+V.DEC_WINDOW and (ck is None or (t[1],t[2],t[3])<ck) for t in T)
            if anch: n_anch+=1
            d=V.detect(T,r["create_ts"],ck)
            if anch:
                # pullback-uri: numarul de episoade PB (inclusiv abandonate) — recalcul simplu
                n_pb+=count_pullbacks(T,r["create_ts"],ck)
            if d is None: continue
            td=T[d["dec"]]; post_buyers=sorted({t[4] for t in T[d["trough"]+1:d["dec"]+1] if t[7]})
            dec[r["mint"]]=dict(mint=r["mint"],creator=r["creator"],create_ts=r["create_ts"],d=d,ts=td[0],slot=td[1],seq=td[2],k=td[3],post_buyers=post_buyers,lab=None)
            recs_needed[r["mint"]]=None
    print("mints",n_mints,"anchored",n_anch,"pullbacks",n_pb,"reclaim decisions",len(dec),round(time.time()-t0),"s",flush=True)
    # etapa 2: wallet_reuse_share (trecere separata peste flux; index rolling: portofel -> lista sortata de (ts, mint))
    idx=collections.defaultdict(list); by_seq=sorted(dec.values(),key=lambda x:(x["seq"],x["k"])); ptr=0; reuse={}
    for line in gzip.open(f"{D2}/curve2x_stream.jsonl.gz","rt"):
        e=json.loads(line)
        if e[0]!="T": continue
        seq,k=e[3],e[4]
        while ptr<len(by_seq) and (by_seq[ptr]["seq"],by_seq[ptr]["k"])<=(seq,k):
            x=by_seq[ptr]; ptr+=1
            if (x["seq"],x["k"])==(seq,k):
                # evenimentul curent este chiar decizia: il includem inainte de calcul (cumparatorul deciziei conteaza cu trecutul sau)
                if e[9]==1: idx[e[6]].append((e[1],e[5]))
                n=0
                for u in x["post_buyers"]:
                    lst=idx.get(u,[]); lo=bisect.bisect_left(lst,(x["ts"]-V.WALLET_WINDOW,"")); others={m for (ts_,m) in lst[lo:] if ts_<=x["ts"] and m!=x["mint"]}
                    n+=(1 if others else 0)
                reuse[x["mint"]]=(n/len(x["post_buyers"])) if x["post_buyers"] else 0.0
                continue
            else:
                n=0
                for u in x["post_buyers"]:
                    lst=idx.get(u,[]); lo=bisect.bisect_left(lst,(x["ts"]-V.WALLET_WINDOW,"")); others={m for (ts_,m) in lst[lo:] if ts_<=x["ts"] and m!=x["mint"]}
                    n+=(1 if others else 0)
                reuse[x["mint"]]=(n/len(x["post_buyers"])) if x["post_buyers"] else 0.0
        if e[9]==1 and not (ptr>0 and (by_seq[ptr-1]["seq"],by_seq[ptr-1]["k"])==(seq,k)): idx[e[6]].append((e[1],e[5]))
    for x in by_seq[ptr:]: reuse[x["mint"]]=0.0
    print("wallet reuse computed",len(reuse),round(time.time()-t0),"s",flush=True)
    # etapa 3: trasaturi + etichete
    rows=[]
    with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
        for line in f:
            m=line[9:60].split('"')[0]
            if m not in dec: continue
            r=json.loads(line); x=dec[m]; T=r["trades"]; d=x["d"]; f_=V.features(T,r["create_ts"],r["creator"],d,reuse.get(m,0.0)); pool=L.pool_prepare(r.get("pool")) if r.get("pool") else None
            lab={vn:V.simulate_v3(r,d["dec"],x["ts"],pool=pool,**kw) for vn,kw in VAR.items()}
            rows.append(dict(mint=m,creator=r["creator"],create_ts=r["create_ts"],ts=x["ts"],slot=x["slot"],seq=x["seq"],k=x["k"],dec_i=d["dec"],anchor_i=d["anchor"],pb_i=d["pb"],trough_i=d["trough"],f=f_,lab=lab,gap=bool(in_outage(x["ts"],x["ts"]+V.H_PRIMARY)),split=split_of(r["create_ts"]),day=datetime.datetime.utcfromtimestamp(r["create_ts"]).strftime("%Y-%m-%d"),hour=int(x["ts"]//3600)))
    rows.sort(key=lambda r:(r["create_ts"],r["mint"])); h=hashlib.sha256()
    os.makedirs(D3,exist_ok=True)
    with gzip.open(f"{D3}/v3_rows.jsonl.gz","wt") as f:
        for r in rows: s=json.dumps(r,separators=(",",":"),default=str)+"\n"; f.write(s); h.update(s.encode())
    st=lambda r:(r["lab"]["base"].get("status") if r["lab"]["base"].get("status")!="OK" else (r["lab"]["base"]["15M"]["state"] or "UNAVAILABLE"))
    man3=dict(label="HISTORICAL_DEV_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),mints_in_cache=n_mints,N_ANCHORED=n_anch,N_PULLBACKS=n_pb,N_RECLAIMS=len(rows),by_split=dict(collections.Counter(r["split"] for r in rows)),by_day=dict(collections.Counter(r["day"] for r in rows)),
        gap_rows=sum(r["gap"] for r in rows),status_base=dict(collections.Counter(st(r) for r in rows)),migrated=sum(1 for r in rows if r["lab"]["base"].get("migrated_in_window")),splice_ok=sum(1 for r in rows if r["lab"]["base"].get("splice_ok")),splice_unavailable=sum(1 for r in rows if r["lab"]["base"].get("splice_ok") is False),
        rows_sha256=h.hexdigest(),inputs=dict(curves_sha256=man["curves_sha256"],stream_sha256=man["stream_sha256"]),runtime_s=round(time.time()-t0,1),rpc_calls=0)
    json.dump(man3,open(os.path.join(HERE,"dataset_manifest.json"),"w"),indent=1)
    with open(os.path.join(HERE,"feature_dictionary.csv"),"w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["feature","definition","window","block"])
        for k,v in FEATURE_DOC.items(): w.writerow([k,v[0],v[1],v[2]])
    print(json.dumps(man3)); print("BUILD_DONE",flush=True)
def count_pullbacks(T,create_ts,ck):
    a=None; h=ds=None; runmax=None; state="TRACK"; pb_t=None; n=0
    for t in T:
        if ck is not None and (t[1],t[2],t[3])>=ck: break
        if t[0]>create_ts+V.DEC_WINDOW: break
        if a is None:
            if t[8]>=V.ANCHOR_PROG*L.TARGET_RS:
                h,ds=L.curve_buy(t[10],t[11],int(V.N_REF*L.LAMP))
                if h<=0: return 0
                a=t; runmax=V.ref_value(t,h,ds)
            continue
        v=V.ref_value(t,h,ds)
        if state=="TRACK":
            if v>runmax: runmax=v
            elif runmax>0 and v<=(1-V.PB_DROP)*runmax: state="PB"; pb_t=t[0]; n+=1; trough=v; maxpb=runmax
        else:
            trough=min(trough,v)
            if t[0]-pb_t>V.RECLAIM_MAX_S: state="TRACK"; runmax=v; continue
            if maxpb>trough and v>=trough+V.RECLAIM_FRAC*(maxpb-trough): break
    return n
FEATURE_DOC={"pullback_depth":("1 - trough/max_pb pe valoarea executabila a pozitiei de referinta 0,25 SOL","pullback","PULLBACK"),"pullback_duration_s":("secunde de la startul pullback-ului la trough","pullback","PULLBACK"),"pullback_slots":("sloturi pb->trough","pullback","PULLBACK"),"pullback_trades":("trade-uri pb->trough","pullback","PULLBACK"),
 "reclaim_duration_s":("secunde trough->decizie","reclaim","RECLAIM"),"reclaim_slots":("sloturi trough->decizie","reclaim","RECLAIM"),"reclaim_trades":("trade-uri trough->decizie","reclaim","RECLAIM"),"recovery_fraction":("(V_dec - trough)/(max_pb - trough)","reclaim","RECLAIM"),"recovery_speed":("recovery_fraction / max(0,4 s, durata reclaim)","reclaim","RECLAIM"),"time_since_anchor_s":("secunde de la anchor la decizie","anchor->dec","STATE"),"anchor_progress":("progresul la anchor","anchor","STATE"),
 "buy_vol_pre":("volum quote cumparari pb->trough (SOL)","pullback","FLOW"),"sell_vol_pre":("volum quote vanzari pb->trough","pullback","FLOW"),"buy_vol_post":("volum quote cumparari trough->dec","reclaim","FLOW"),"sell_vol_post":("volum quote vanzari trough->dec","reclaim","FLOW"),"sell_intensity_change":("SOL/s vanzari post - pre","window","ABSORPTION"),"sell_intensity_ratio":("intensitate post / pre","window","ABSORPTION"),"uniq_sellers_window":("vanzatori unici pb->dec","window","ABSORPTION"),"seller_inventory_decline":("tokens vandute / tokens cumparate de vanzatori (istoric intreg)","history","ABSORPTION"),
 "uniq_buyers":("cumparatori unici (istoric)","history","BREADTH"),"new_buyers_post":("cumparatori noi in reclaim (nevazuti inainte)","reclaim","BREADTH"),"buyer_retention":("cota cumparatorilor de dinaintea pullback-ului care nu au vandut","history","BREADTH"),"imbalance_window":("(buy - sell)/(buy + sell) pb->dec","window","FLOW"),"net_quote_flow_window":("buy - sell (SOL) pb->dec","window","FLOW"),
 "top1_share":("cota top 1 portofel din volumul de cumparare","history","COORDINATION"),"top3_share":("top 3","history","COORDINATION"),"top10_share":("top 10","history","COORDINATION"),"hhi":("HHI al volumului de cumparare","history","COORDINATION"),"wallet_reuse_share":("cota cumparatorilor din reclaim vazuti cumparand alte lansari in ultimele 60 min (doar trecut)","cross-mint 60 min","COORDINATION"),"same_slot_max_wallets":("max portofele cumparatoare in acelasi slot in reclaim","reclaim","COORDINATION"),"same_slot_share":("cota cumpararilor din slotul modal al reclaim-ului","reclaim","COORDINATION"),
 "creator_inventory_share":("inventarul net al creatorului / oferta neta cumparata","history","CREATOR"),"creator_sold_flag":("creatorul a vandut","history","CREATOR"),"creator_sell_share":("tokens vandute / cumparate de creator","history","CREATOR"),"progress":("rezerva reala / 85 SOL la decizie","state","STATE"),"dist_to_migration_sol":("85 - rezerva reala","state","STATE"),"rs_sol":("rezerva reala","state","STATE"),"vs_sol":("rezerva virtuala SOL","state","STATE"),"headroom_025":("plafon mecanic curve-only pentru 0,25 SOL","state","STATE"),"slippage_bp_025":("impact propriu 0,25 SOL","state","STATE"),"n_trades_total":("trade-uri pana la decizie","history","STATE")}
if __name__=="__main__": main()
