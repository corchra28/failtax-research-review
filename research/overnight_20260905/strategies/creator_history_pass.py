"""S5 prerechizit: o trecere peste banda (nice) pentru istoricul creatorilor: per mint creat in banda: creator, create_ts, complete_ts (sau None), nr. trade-uri de curba, cumparatori distincti, top1 share (din tokeni cumparati), vanzari ale creatorului pe curba. Fara outcome-uri de pool."""
import gzip,json,os,glob,sys,time,zlib,collections,hashlib
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; TAPE="strategy_m/data/tape"
M={}; t0=time.time()
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
for fp in sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")):
    for line in readlines(fp):
        if '"src":"pump"' not in line: continue
        r=json.loads(line)
        for e in r["events"]:
            if e["ev"]=="CreateEvent": M.setdefault(e["mint"],dict(creator=e["user"],create_ts=int(r["t"]),complete_ts=None,n_trades=0,buyers=set(),top=collections.Counter(),creator_sold=0,creator_bought=0))
            elif e["ev"]=="CompleteEvent" and e["mint"] in M and M[e["mint"]]["complete_ts"] is None: M[e["mint"]]["complete_ts"]=int(next((x.get("ts") for x in r["events"] if x["ev"]=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),r["t"]))
            elif e["ev"]=="TradeEvent" and e["mint"] in M:
                m=M[e["mint"]]; m["n_trades"]+=1
                if e["is_buy"]: m["buyers"].add(e["user"]); m["top"][e["user"]]+=e["tok"]
                if e["user"]==m["creator"]: m["creator_sold" if not e["is_buy"] else "creator_bought"]+=e["tok"]
    print(os.path.basename(fp),len(M),round(time.time()-t0),"s",flush=True)
with gzip.open(f"{D}/creator_history.jsonl.gz","wt") as f:
    for mint,m in M.items():
        tot=sum(m["top"].values()); f.write(json.dumps(dict(mint=mint,creator=m["creator"],create_ts=m["create_ts"],complete_ts=m["complete_ts"],n_trades=m["n_trades"],n_buyers=len(m["buyers"]),top1_share=(max(m["top"].values())/tot if tot else None),creator_sold=m["creator_sold"],creator_bought=m["creator_bought"]))+"\n")
print("CREATOR_HISTORY_DONE",len(M),flush=True)
