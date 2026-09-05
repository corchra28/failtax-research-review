"""CURVE2X V2 — HISTORICAL_REMEDIATION_NOT_SEALED. Etapa BUILD: (1) motorul de decizie peste fluxul de curba in ordinea benzii -> randuri (mint, landmark) cu trasaturi;
(2) etichete first-passage per (rand, notional, varianta de executie) din cache-ul de curbe + evenimente de pool; (3) split cronologic cu embargo si excluderi de calitate.
Iesire: derived/curve2x_rows.jsonl.gz (local) + research/curve2x_v2/build_manifest.json. Zero RPC."""
import gzip,json,sys,os,time,collections,datetime,hashlib,multiprocessing as mp
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/curve2x_v2"
SPEC=json.load(open(f"{OUT}/frozen_spec.json")); SPL=SPEC["split"]
def utc(s): return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc).timestamp()
B_TRAIN=utc(SPL["train_end_utc"]); B_CAL=utc(SPL["cal_end_utc"]); B_VAL=utc(SPL["val_end_utc"]); EMB=SPL["embargo_s"]
MAN=json.load(open(f"{D}/curve2x_pass_manifest.json")); OUT_W=[tuple(w) for w in MAN["outage_windows"]]
def in_outage(a,b): return any(not (e<=a or s>=b) for s,e in OUT_W)
def truncated(a,b):
    for fn,last in MAN["file_last_t"].items():
        if last is None: continue
        h=datetime.datetime.strptime(fn[7:17],"%Y%m%d%H").timestamp(); end=h+3600
        if last<end-5 and not (b<last or a>end): return True
    return False
def split_of(ct):
    for b,name in ((B_TRAIN,"TRAIN"),(B_CAL,"CAL"),(B_VAL,"VAL")):
        if ct<b: return name if ct<b-EMB else "EMBARGO"
    return "CONF"
VARIANTS={"base":dict(land=L.LAND,cost_mult=1.0),"land5":dict(land=L.LAND_STRESS,cost_mult=1.0),"cost125":dict(land=L.LAND,cost_mult=L.COST_STRESS)}
def label_mint(args):
    rec,rows=args; pool=L.pool_prepare(rec.get("pool")) if rec.get("pool") else None; out=[]
    for r in rows:
        lab={}
        for N in L.NOTS:
            for vn,kw in VARIANTS.items():
                lab[f"{N}|{vn}"]=L.simulate(rec,r["i"],r["ts"],N,pool=pool,**kw)
        Hmax=max(L.HORIZONS.values()); r["gap"]=bool(in_outage(r["ts"],r["ts"]+Hmax) or truncated(r["ts"],r["ts"]+Hmax)); r["lab"]=lab; out.append(r)
    return out
def main():
    t0=time.time(); E=L.Engine(); n=0
    for line in gzip.open(f"{D}/curve2x_stream.jsonl.gz","rt"):
        E.on_event(json.loads(line)); n+=1
    rows_by=collections.defaultdict(list)
    for r in E.rows: rows_by[r["mint"]].append(r)
    print("engine rows",len(E.rows),"mints",len(rows_by),"events",n,round(time.time()-t0),"s",flush=True); del E
    def tasks():
        with gzip.open(f"{D}/curve2x_curves.jsonl.gz","rt") as f:
            for line in f:
                m=line[9:60].split('"')[0]
                if m not in rows_by: continue
                rec=json.loads(line); yield (rec,rows_by[rec["mint"]])
    labeled=[]; done=0
    with mp.Pool(3) as P:
        for out in P.imap(label_mint,tasks(),chunksize=8):
            labeled.extend(out); done+=1
            if done%2000==0: print("labeled mints",done,round(time.time()-t0),"s",flush=True)
    recs=done; print("records labeled",recs,flush=True)
    labeled.sort(key=lambda r:(r["create_ts"],r["mint"],r["landmark"]))
    for r in labeled: r["split"]=split_of(r["create_ts"]); r["day"]=datetime.datetime.utcfromtimestamp(r["create_ts"]).strftime("%Y-%m-%d"); r["hour"]=int(r["ts"]//3600)
    h=hashlib.sha256()
    with gzip.open(f"{D}/curve2x_rows.jsonl.gz","wt") as f:
        for r in labeled: s=json.dumps(r,separators=(",",":"),default=str)+"\n"; f.write(s); h.update(s.encode())
    P_=f"{L.PRIMARY_N}|base"; H=L.PRIMARY_H
    def st(r): x=r["lab"][P_]; return x.get("status") if x.get("status")!="OK" else (x[H]["state"] or "UNAVAILABLE")
    man=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),rows=len(labeled),mints=len({r["mint"] for r in labeled}),by_split=dict(collections.Counter(r["split"] for r in labeled)),by_landmark=dict(collections.Counter(r["landmark"] for r in labeled)),
        gap_rows=sum(r["gap"] for r in labeled),primary_status=dict(collections.Counter(st(r) for r in labeled)),primary_status_by_landmark={Lm:dict(collections.Counter(st(r) for r in labeled if r["landmark"]==Lm)) for Lm in L.LANDMARKS},
        migrated_rows=sum(1 for r in labeled if r["lab"][P_].get("migrated_in_window")),splice_ok_rows=sum(1 for r in labeled if r["lab"][P_].get("splice_ok")),splice_unavailable_rows=sum(1 for r in labeled if r["lab"][P_].get("splice_ok") is False),
        rows_sha256=h.hexdigest(),stream_sha256=MAN["stream_sha256"],curves_sha256=MAN["curves_sha256"],runtime_s=round(time.time()-t0,1),rpc_calls=0)
    json.dump(man,open(f"{OUT}/build_manifest.json","w"),indent=1); print(json.dumps(man)); print("BUILD_DONE",flush=True)
if __name__=="__main__": main()
