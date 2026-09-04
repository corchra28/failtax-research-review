"""Lista per pool a migrarilor EXCLUSE din populatia regimului (SEP02-04), cu motivul (trecerea 1 + ferestre; motivele care necesita trecerea 2 sunt marcate NO_EVENTS_OR_VQ_UNVERIFIABLE prin diferenta fata de cache)."""
import gzip,json,base64,struct,os,glob,collections,sys,time,zlib,datetime
sys.path.insert(0,'strategy_e'); from pda import b58e
SCR="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad"; TAPE="strategy_m/data/tape"; POOL_TOK=206_900_000_000_000; WSOL="So11111111111111111111111111111111111111112"
def lt(s): return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M:%S").timestamp()
OUT_W=[]; open_t=None
for line in open(f"{TAPE}/collector.log"):
    if len(line)<20: continue
    try: t=lt(line[:19])
    except Exception: continue
    if "DECONECTARE" in line and open_t is None: open_t=t
    if "conectat:" in line and open_t is not None: OUT_W.append((open_t,t)); open_t=None
last_hb=max(lt(l[:19]) for l in open(f"{TAPE}/collector.log") if "[HB]" in l); OUT_W.append((last_hb+600,time.time()))
files=sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")); trunc_last_t={}
def readlines(fpath):
    try:
        with gzip.open(fpath,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
complete={}; poolmap={}
for fp in files:
    last=None
    for line in readlines(fp):
        if '"src":"pump"' in line and 'CompleteEvent' in line:
            r=json.loads(line); last=r["t"]
            for e in r["events"]:
                if e["ev"]=="CompleteEvent" and e["mint"] not in complete:
                    ts=next((x.get("ts") for x in r["events"] if x["ev"]=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),None) or int(r["t"]); complete[e["mint"]]=dict(t=r["t"],ts=ts,slot=r["slot"])
        elif '"src":"pamm"' in line and 'CreatePoolEvent' in line:
            r=json.loads(line); last=r["t"]
            for e in r["events"]:
                if e["ev"]=="CreatePoolEvent":
                    raw=base64.b64decode(e["raw"]); ts,=struct.unpack_from("<q",raw,8); bm=b58e(raw[50:82]); qm=b58e(raw[82:114]); pb,pq=struct.unpack_from("<QQ",raw,132)
                    if bm in complete and bm not in poolmap: poolmap[bm]=dict(pool=b58e(raw[173:205]),t=r["t"],ts=ts,slot=r["slot"],pool_base=pb,pool_quote=pq,quote_mint=qm)
        if last is None and '"t":' in line[:40]:
            try: last=float(line.split('"t":')[1].split(',')[0])
            except Exception: pass
    trunc_last_t[os.path.basename(fp)]=last
def in_outage(a,b): return any(not (e<=a or s>=b) for s,e in OUT_W)
def unreadable(a,b):
    for fn,last in trunc_last_t.items():
        if last is None: continue
        h=datetime.datetime.strptime(fn[7:17],"%Y%m%d%H").timestamp(); end=h+3600
        if last<end-5 and not (b<last or a>end): return True
    return False
cache={json.loads(l)["mint"] for l in gzip.open(f"{SCR}/derived/regime_pools.jsonl.gz","rt")}
rows=[]
for m,c in complete.items():
    pm=poolmap.get(m)
    if pm is None: rows.append(dict(mint=m,pool=None,complete_ts=c["ts"],complete_slot=c["slot"],T0_ts=None,reason="NO_POOL_CREATION_OBSERVED",pool_quote_initial=None)); continue
    if m in cache: continue
    if pm["quote_mint"]!=WSOL: reason="NON_SOL_QUOTE"
    elif pm["pool_base"]!=POOL_TOK or not (80e9<=pm["pool_quote"]<=90e9): reason="NOT_BOOST_PROXY_INITIAL_STATE"
    elif in_outage(c["t"]-1,pm["t"]+420): reason="OUTAGE_IN_REQUIRED_INTERVAL"
    elif unreadable(c["t"]-1,pm["t"]+420): reason="UNREADABLE_SEGMENT_IN_REQUIRED_INTERVAL"
    else: reason="NO_EVENTS_OR_VQ_UNVERIFIABLE_OR_FIRST_STATE_NOT_BOOST"
    rows.append(dict(mint=m,pool=pm["pool"],complete_ts=c["ts"],complete_slot=c["slot"],T0_ts=pm["ts"],reason=reason,pool_quote_initial=pm["pool_quote"]))
json.dump(rows,open(f"{SCR}/derived/regime_excluded_pools.json","w")); print("excluse",len(rows),dict(collections.Counter(r["reason"] for r in rows))); print("EXCL_DONE",flush=True)
