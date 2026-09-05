"""WALLET_FLOW_HAZARD_V1 — BUILD: (1) graf cauzal de portofele/creatori din cache-ul de curbe V2 (pozitii maturizate), (2) decizii la checkpoint-uri cauzale (landmark-uri V2 20..60 %),
trasaturi A-E strict din trecut, etichete first-passage TP 2x / SL -35 % cu limite de ordine (conservative primar), person-period pentru hazarde; (3) split cronologic cu embargo. Zero RPC."""
import os,sys,gzip,json,time,bisect,collections,datetime,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import wfh_lib as W; V=W.V; L=W.L
D2=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(HERE),"curve2x_v2","derived")); DW=os.environ.get("WFH_DERIVED_DIR",os.path.join(HERE,"derived_wfh")); SPEC=json.load(open(os.path.join(HERE,"frozen_spec.json"))); SPL=SPEC["split"]
def utc(s): return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc).timestamp()
B=[(utc(SPL["train_end_utc"]),"TRAIN"),(utc(SPL["cal_end_utc"]),"CAL"),(utc(SPL["val_end_utc"]),"VAL")]; EMB=SPL["embargo_s"]
def split_of(ct):
    for b,name in B:
        if ct<b: return name if ct<b-EMB else "EMBARGO"
    return "CONF"
LANDMARKS=SPEC["checkpoints"]["grid_pct"]
def main():
    t0=time.time(); G=W.WalletGraph(); CG=W.CreatorGraph(); creates=[]; n=0
    with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
        for line in f:
            r=json.loads(line); n+=1; creates.append(r["create_ts"])
            if not r["trades"]: continue
            G.add(W.wallet_positions_for_mint(r)); CG.add(W.creator_history_for_mint(r))
    G.finalize(); CG.finalize(); creates.sort(); print("graph: mints",n,"wallets",len(G.P),"positions",sum(len(v) for v in G.P.values()),"creators",len(CG.H),round(time.time()-t0),"s",flush=True)
    dec=collections.defaultdict(list)
    for l in gzip.open(f"{D2}/curve2x_rows.jsonl.gz","rt"):
        r=json.loads(l)
        if r["landmark"] in LANDMARKS: dec[r["mint"]].append(dict(landmark=r["landmark"],ts=r["ts"],i=r["i"],slot=r["slot"]))
    print("decision points: mints",len(dec),"rows",sum(len(v) for v in dec.values()),flush=True); rows=[]; man=json.load(open(f"{D2}/curve2x_pass_manifest.json")); OUT_W=[tuple(w) for w in man["outage_windows"]]
    def in_outage(a,b): return any(not (e<=a or s>=b) for s,e in OUT_W)
    with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
        for line in f:
            m=line[9:60].split('"')[0]
            if m not in dec: continue
            r=json.loads(line); pool=L.pool_prepare(r.get("pool")) if r.get("pool") else None
            for d in sorted(dec[m],key=lambda x:x["landmark"]):
                ts=d["ts"]; lr=(bisect.bisect_right(creates,ts)-bisect.bisect_left(creates,ts-600))/10.0; f_=W.features(r,d["i"],ts,d["landmark"],G,CG,lr)
                lab=dict(base=V.simulate_v3(r,d["i"],ts,pool=pool),bounds=V.simulate_v3_bounds(r,d["i"],ts,pool=pool),bounds_land5=V.simulate_v3_bounds(r,d["i"],ts,pool=pool,land=V.LAND_STRESS),bounds_cost125=V.simulate_v3_bounds(r,d["i"],ts,pool=pool,cost_mult=V.COST_STRESS)); pb=W.path_bins(r,d["i"],ts,pool=pool)
                rows.append(dict(mint=m,creator=r["creator"],create_ts=r["create_ts"],landmark=d["landmark"],ts=ts,slot=d["slot"],i=d["i"],f=f_,lab=lab,bins=(None if (pb is None or pb.get("unavailable")) else [{k:v for k,v in b.items() if k!="exit_state"}|{"exit_slot":(b["exit_state"][1] if b["exit_state"] else None)} for b in pb["bins"]]),entry_ratio=(None if (pb is None or pb.get("unavailable")) else pb["entry_ratio"]),gap=bool(in_outage(ts,ts+W.HOR)),split=split_of(r["create_ts"]),day=datetime.datetime.fromtimestamp(r["create_ts"],datetime.timezone.utc).strftime("%Y-%m-%d"),hour=int(ts//3600)))
    rows.sort(key=lambda r:(r["create_ts"],r["mint"],r["landmark"])); os.makedirs(DW,exist_ok=True); h=hashlib.sha256()
    with gzip.open(f"{DW}/wfh_rows.jsonl.gz","wt") as f:
        for r in rows: s=json.dumps(r,separators=(",",":"),default=str)+"\n"; f.write(s); h.update(s.encode())
    st=lambda r:(r["lab"]["bounds"].get("status") if r["lab"]["bounds"].get("status")!="OK" else ("UNAVAILABLE" if r["lab"]["bounds"].get("unavailable") else r["lab"]["bounds"]["conservative"]["state"]))
    dm=dict(label="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),mints=len(dec),rows=len(rows),by_split=dict(collections.Counter(r["split"] for r in rows)),by_landmark=dict(collections.Counter(r["landmark"] for r in rows)),status_conservative=dict(collections.Counter(st(r) for r in rows)),gap_rows=sum(r["gap"] for r in rows),
        wallet_graph=dict(wallets=len(G.P),positions=sum(len(v) for v in G.P.values()),creators=len(CG.H)),share_rows_with_wallet_history=sum(1 for r in rows if r["f"]["wq_share_with_history"]>0)/max(1,len(rows)),rows_sha256=h.hexdigest(),runtime_s=round(time.time()-t0,1),rpc_calls=0)
    json.dump(dm,open(os.path.join(HERE,"dataset_manifest.json"),"w"),indent=1); print(json.dumps(dm)); print("BUILD_DONE",flush=True)
if __name__=="__main__": main()
