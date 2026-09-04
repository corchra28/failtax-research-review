"""MASTER EDGE — Lane M: constructia cache-ului derivat (FARA trasaturi, FARA outcome-uri). Reproduce populatia sigilata (946 pool-uri BOOST) din
research/premigration_path_sealed_manifest.json si salveaza per pool: trade-urile de curba (cu portofel) si evenimentele pool-ului pana la T0+420 s (cu portofel).
Iesire: <scratchpad>/derived/m_pools.jsonl.gz + m_cache_manifest.json (sha256, versiune parser). Zero date noi."""
import gzip,json,base64,struct,hashlib,os,glob,collections,statistics as S,sys,time,zlib,datetime
sys.path.insert(0,'strategy_e'); from pda import b58e
PARSER_VERSION="m_cache_v1 (adaptor v3 al evaluarii sigilate: pool@173, q_net=@104-@80, taxa creator derivata)"
OUT=sys.argv[1] if len(sys.argv)>1 else "/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"
TAPE="strategy_m/data/tape"; POOL_TOK=206_900_000_000_000
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
create_t={}; create_user={}; complete={}; poolmap={}
for fp in files:
    last=None
    for line in readlines(fp):
        if '"src":"pump"' in line:
            if 'CreateEvent' in line or 'CompleteEvent' in line:
                r=json.loads(line); last=r["t"]
                for e in r["events"]:
                    if e["ev"]=="CreateEvent": create_t.setdefault(e["mint"],r["t"]); create_user[e["mint"]]=e["user"]
                    elif e["ev"]=="CompleteEvent" and e["mint"] not in complete:
                        ts=next((x.get("ts") for x in r["events"] if x["ev"]=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),None) or e.get("ts") or int(r["t"])
                        complete[e["mint"]]=dict(t=r["t"],ts=ts,slot=r["slot"])
        elif '"src":"pamm"' in line and 'CreatePoolEvent' in line:
            r=json.loads(line); last=r["t"]
            for e in r["events"]:
                if e["ev"]=="CreatePoolEvent":
                    raw=base64.b64decode(e["raw"]); ts,=struct.unpack_from("<q",raw,8); base_mint=b58e(raw[50:82]); quote_mint=b58e(raw[82:114])
                    pool_base,pool_quote=struct.unpack_from("<QQ",raw,132); pool=b58e(raw[173:205])
                    if base_mint in complete or base_mint in create_t: poolmap[base_mint]=dict(pool=pool,t=r["t"],ts=ts,slot=r["slot"],pool_base=pool_base,pool_quote=pool_quote,quote_mint=quote_mint)
    trunc_last_t[os.path.basename(fp)]=last
mig=[m for m in complete if m in poolmap]; print("pass1 completari",len(complete),"cu pool",len(mig),flush=True)
pool2mint={v["pool"]:m for m,v in poolmap.items()}; TR=collections.defaultdict(list); PE=collections.defaultdict(list); seq=0
for fp in files:
    for line in readlines(fp):
        if '"src":"pump"' in line:
            if 'TradeEvent' not in line: continue
            r=json.loads(line)
            for k,e in enumerate(r["events"]):
                if e["ev"]=="TradeEvent" and e["mint"] in complete: TR[e["mint"]].append([r["slot"],seq,k,e["sol"],e["tok"],int(e["is_buy"]),e["user"],e["rsol"],e.get("ts"),r["t"]])
            seq+=1
        elif '"src":"pamm"' in line and ('BuyEvent' in line or 'SellEvent' in line):
            r=json.loads(line)
            for k,e in enumerate(r["events"]):
                if e["ev"] not in ("BuyEvent","SellEvent"): continue
                raw=base64.b64decode(e["raw"]); pool=b58e(raw[120:152]); m=pool2mint.get(pool)
                if m is None or r["t"]>poolmap[m]["t"]+420: continue
                ts,=struct.unpack_from("<q",raw,8); amt,mx,ub,uq,rb,rq,q2=struct.unpack_from("<QQQQQQQ",raw,16); lpbp,lpf,prbp,prf,q3,uq2=struct.unpack_from("<QQQQQQ",raw,72)
                if e["ev"]=="BuyEvent":
                    rb_post=rb-amt; rq_post=rq+q3; cp_q=q3-lpf; gross=max(q2,uq2); cce=max(0,round((gross-cp_q-lpf-prf)*10000/cp_q)) if cp_q>0 else 0
                else:
                    rb_post=rb+amt; rq_post=rq-q3; cp_q=q3+lpf; net=min(q2,uq2); cce=max(0,round((cp_q-lpf-prf-net)*10000/cp_q)) if cp_q>0 else 0
                PE[m].append([r["t"],ts,r["slot"],seq,k,1 if e["ev"]=="BuyEvent" else 0,rb,rq,rb_post,rq_post,amt,cp_q,lpbp,prbp,cce,b58e(raw[152:184])])
            seq+=1
print("pass2 done",flush=True)
def in_outage(a,b): return any(not (e<=a or s>=b) for s,e in OUT_W)
def unreadable(a,b):
    for fn,last in trunc_last_t.items():
        if last is None: continue
        h=datetime.datetime.strptime(fn[7:17],"%Y%m%d%H").timestamp(); end=h+3600
        if last<end-5 and not (b<last or a>end): return True
    return False
P=[]; excl=collections.Counter()
for m in mig:
    c=complete[m]; pm=poolmap[m]; T0=pm["t"]
    if m not in create_t: excl["NO_CREATE_IN_TAPE"]+=1; continue
    if pm["quote_mint"]!="So11111111111111111111111111111111111111112": excl["NON_SOL_QUOTE"]+=1; continue
    if pm["pool_base"]!=POOL_TOK or not (80e9<=pm["pool_quote"]<=90e9): excl["NOT_BOOST_PROXY_INITIAL_STATE"]+=1; continue
    ev=sorted(PE.get(m,[]),key=lambda x:(x[2],x[3],x[4]))
    if not ev or ev[-1][0]<T0+300: excl["NO_POST_TAPE_300S"]+=1; continue
    if not (60e9<=ev[0][7]<=75e9): excl["FIRST_EVENT_REAL_QUOTE_NOT_BOOST"]+=1; continue
    if in_outage(create_t[m],T0+420): excl["OUTAGE_IN_INTERVAL"]+=1; continue
    if unreadable(create_t[m],T0+420): excl["UNREADABLE_SEGMENT_IN_INTERVAL"]+=1; continue
    tr=sorted([x for x in TR[m] if (x[0],x[1],x[2])<(c["slot"],10**12,0) and x[9]<=c["t"]+0.001],key=lambda x:(x[0],x[1],x[2]))
    if not tr: excl["NO_CURVE_TRADES"]+=1; continue
    vqs=[]
    for a in ev[:60]:
        if a[5]==1 and a[10]>0: vqs.append(a[6]*a[11]/a[10]-a[7]-a[11])
        elif a[5]==0 and a[10]>0: vqs.append(a[11]*(a[6]+a[10])/a[10]-a[7])
    vq=S.median(vqs) if len(vqs)>=5 else None
    if vq is None or abs(vq-17.58e9)>0.3e9: excl["VQ_NOT_BOOST_OR_UNVERIFIABLE"]+=1; continue
    P.append(dict(mint=m,pool=pm["pool"],day=datetime.datetime.fromtimestamp(c["t"]).strftime("%Y-%m-%d"),create_t=create_t[m],creator=create_user[m],complete_t=c["t"],complete_ts=c["ts"],complete_slot=c["slot"],T0=T0,T0_ts=pm["ts"],T0_slot=pm["slot"],vq=int(vq),curve=tr,ev=ev))
P.sort(key=lambda x:x["complete_t"])
pop_sha=hashlib.sha256("\n".join(f"{x['mint']}|{x['complete_slot']}|{x['T0']}|{len(x['ev'])}" for x in P).encode()).hexdigest()
sealed=json.load(open("research/premigration_path_sealed_manifest.json"))["population_manifest_sha256"]
os.makedirs(OUT,exist_ok=True); h=hashlib.sha256()
with gzip.open(f"{OUT}/m_pools.jsonl.gz","wt") as f:
    for x in P: s=json.dumps(x,separators=(",",":"))+"\n"; f.write(s); h.update(s.encode())
man=dict(parser=PARSER_VERSION,built=time.strftime("%Y-%m-%d %H:%M:%S"),N=len(P),by_day=dict(collections.Counter(x["day"] for x in P)),exclusions=dict(excl),population_sha256=pop_sha,matches_sealed_population=(pop_sha==sealed),content_sha256=h.hexdigest(),curve_trades=sum(len(x["curve"]) for x in P),pool_events=sum(len(x["ev"]) for x in P),outage_windows=len(OUT_W),script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest())
json.dump(man,open(f"{OUT}/m_cache_manifest.json","w"),indent=1); print(json.dumps(man),flush=True); print("M_CACHE_DONE",flush=True)
