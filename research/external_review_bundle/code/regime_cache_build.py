"""REGIME GATE — cache unificat al migrarilor BOOST (FARA outcome-uri): 2026-09-01 (hist24: pool tapes din solduri vault, ordonare exacta, taxe pe tiere)
+ 2026-09-02..04 (banda prospectiva: evenimente Buy/Sell cu rezerve si portofele, taxe observate). Fara cerinta de CreateEvent (nu sunt necesare trasaturi de curba).
Format eveniment unificat: [t_local, ts, slot, seq, k, is_buy, rb_pre, rq_pre, rb_post, rq_post, amt_base, quote_cp, lp_bp, protocol_bp, creator_bp, user|None]."""
import gzip,json,base64,struct,hashlib,os,glob,collections,statistics as S,sys,time,zlib,datetime
sys.path.insert(0,'strategy_e'); from pda import b58e
sys.path.insert(0,'.'); import pumpswap_fees as PF
OUT=sys.argv[1] if len(sys.argv)>1 else "/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"
TAPE="strategy_m/data/tape"; H24="strategy_m/data/hist24"; POOL_TOK=206_900_000_000_000; SUPPLY=10**15; WSOL="So11111111111111111111111111111111111111112"
P=[]; excl=collections.Counter()
# ---------------- SEP01 (hist24) ----------------
comp01={}
with gzip.open(f"{H24}/events.jsonl.gz","rt") as f:
    for line in f:
        if 'CompleteEvent' not in line: continue
        r=json.loads(line)
        for e in r["events"]:
            if e["ev"]=="CompleteEvent" and e["mint"] not in comp01: comp01[e["mint"]]=dict(ts=r["blockTime"],slot=r["slot"],idx=r["idx"],sig=r["sig"])
print("SEP01 completari",len(comp01),flush=True)
for l in gzip.open(f"{H24}/pool_tapes.jsonl.gz","rt"):
    t=json.loads(l); m=t["mint"]; rows=[x for x in t["tape"] if x[3] is not None and x[4] is not None and x[3]>0]
    if m not in comp01: excl["SEP01_NO_COMPLETE"]+=1; continue
    if not rows: excl["SEP01_NO_ROWS"]+=1; continue
    keys=[(x[1],x[2] if x[2] is not None else 10**6) for x in rows]; rows=[r for _,r in sorted(zip(keys,rows))]
    vq=t["vq"]
    if not (abs(vq-17.58e9)<0.1e9): excl["SEP01_NOT_BOOST_VQ"]+=1; continue
    if rows[0][3]!=POOL_TOK or not (60e9<=rows[0][4]<=75e9): excl["SEP01_NOT_BOOST_INITIAL_STATE"]+=1; continue
    c=comp01[m]; T0=rows[0][0]
    if rows[-1][0]<T0+420: excl["SEP01_COVERAGE_LT_420S"]+=1; continue
    ev=[]; prev=None; seq=0
    for x in rows:
        bt,sl,idx,rb,rq=x
        if prev is None: prev=x; continue
        rb0,rq0=prev[3],prev[4]
        if rb==rb0 and rq==rq0: prev=x; continue
        f=PF.fees_for(rb0,rq0,vq,SUPPLY); lp,pr,cc=f["lp_bp"],f["protocol_bp"],f["creator_bp"]
        if rb<rb0 and rq>rq0: isb=1; amt=rb0-rb; q3=rq-rq0; q2=q3*10000//(10000+lp)
        elif rb>rb0 and rq<rq0: isb=0; amt=rb-rb0; q3=rq0-rq; q2=q3*10000//(10000-lp)
        else: isb=-1; amt=abs(rb-rb0); q2=abs(rq-rq0)   # LP add/remove sau altceva: pastrat ca stare, fara CP
        ev.append([float(bt),int(bt),sl,seq,idx if idx is not None else 0,isb,rb0,rq0,rb,rq,amt,q2,lp,pr,cc,None]); seq+=1; prev=x
    if not ev: excl["SEP01_NO_TRADES"]+=1; continue
    P.append(dict(mint=m,pool=t["pool"],day="2026-09-01",source="SEP01_HIST24_VAULT_BALANCES",fee_mode="TIER_TABLE",complete_ts=c["ts"],complete_slot=c["slot"],complete_idx=c["idx"],complete_sig=c["sig"],T0_ts=T0,T0_slot=rows[0][1],vq=int(vq),ordering="EXACT_SLOT_TXINDEX",ev=[e for e in ev if e[1]<=T0+420]))
print("SEP01 incluse",len(P),dict(excl),flush=True)
# ---------------- SEP02..04 (banda prospectiva) ----------------
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
                    ts=next((x.get("ts") for x in r["events"] if x["ev"]=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),None) or int(r["t"])
                    complete[e["mint"]]=dict(t=r["t"],ts=ts,slot=r["slot"],sig=r["sig"])
        elif '"src":"pamm"' in line and 'CreatePoolEvent' in line:
            r=json.loads(line); last=r["t"]
            for e in r["events"]:
                if e["ev"]=="CreatePoolEvent":
                    raw=base64.b64decode(e["raw"]); ts,=struct.unpack_from("<q",raw,8); base_mint=b58e(raw[50:82]); quote_mint=b58e(raw[82:114]); pool_base,pool_quote=struct.unpack_from("<QQ",raw,132); pool=b58e(raw[173:205])
                    if base_mint in complete and base_mint not in poolmap: poolmap[base_mint]=dict(pool=pool,t=r["t"],ts=ts,slot=r["slot"],pool_base=pool_base,pool_quote=pool_quote,quote_mint=quote_mint)
        elif '"src":"pump"' in line and last is None: pass
        if last is None and '"t":' in line[:40]:
            try: last=float(line.split('"t":')[1].split(',')[0])
            except Exception: pass
    trunc_last_t[os.path.basename(fp)]=last
mig=[m for m in complete if m in poolmap]; print("SEP02-04 completari",len(complete),"cu pool",len(mig),flush=True)
pool2mint={v["pool"]:m for m,v in poolmap.items()}; PE=collections.defaultdict(list); seq=0
for fp in files:
    for line in readlines(fp):
        if '"src":"pamm"' not in line or ('BuyEvent' not in line and 'SellEvent' not in line): continue
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
def in_outage(a,b): return any(not (e<=a or s>=b) for s,e in OUT_W)
def unreadable(a,b):
    for fn,last in trunc_last_t.items():
        if last is None: continue
        h=datetime.datetime.strptime(fn[7:17],"%Y%m%d%H").timestamp(); end=h+3600
        if last<end-5 and not (b<last or a>end): return True
    return False
for m in mig:
    c=complete[m]; pm=poolmap[m]; T0=pm["t"]
    if pm["quote_mint"]!=WSOL: excl["NON_SOL_QUOTE"]+=1; continue
    if pm["pool_base"]!=POOL_TOK or not (80e9<=pm["pool_quote"]<=90e9): excl["NOT_BOOST_PROXY_INITIAL_STATE"]+=1; continue
    ev=sorted(PE.get(m,[]),key=lambda x:(x[2],x[3],x[4]))
    if not ev: excl["NO_POOL_EVENTS"]+=1; continue
    if not (60e9<=ev[0][7]<=75e9): excl["FIRST_EVENT_REAL_QUOTE_NOT_BOOST"]+=1; continue
    if in_outage(c["t"]-1,T0+420): excl["OUTAGE_IN_REQUIRED_INTERVAL"]+=1; continue
    if unreadable(c["t"]-1,T0+420): excl["UNREADABLE_SEGMENT_IN_REQUIRED_INTERVAL"]+=1; continue
    vqs=[]
    for a in ev[:60]:
        if a[5]==1 and a[10]>0: vqs.append(a[6]*a[11]/a[10]-a[7]-a[11])
        elif a[5]==0 and a[10]>0: vqs.append(a[11]*(a[6]+a[10])/a[10]-a[7])
    vq=S.median(vqs) if len(vqs)>=5 else None
    if vq is None or abs(vq-17.58e9)>0.3e9: excl["VQ_NOT_BOOST_OR_UNVERIFIABLE"]+=1; continue
    P.append(dict(mint=m,pool=pm["pool"],day=datetime.datetime.utcfromtimestamp(c["ts"]).strftime("%Y-%m-%d"),source="PROSPECTIVE_TAPE_EVENTS",fee_mode="OBSERVED_EVENT_BPS",complete_ts=c["ts"],complete_slot=c["slot"],complete_idx=None,complete_sig=c["sig"],T0_ts=pm["ts"],T0_slot=pm["slot"],vq=int(vq),ordering="SLOT_ARRIVAL_NO_TXINDEX",ev=ev))
P.sort(key=lambda x:(x["complete_ts"],x["complete_slot"],x["complete_sig"]))
os.makedirs(OUT,exist_ok=True); h=hashlib.sha256(); pop=hashlib.sha256()
with gzip.open(f"{OUT}/regime_pools.jsonl.gz","wt") as f:
    for x in P: s=json.dumps(x,separators=(",",":"))+"\n"; f.write(s); h.update(s.encode()); pop.update(f"{x['mint']}|{x['complete_slot']}|{x['T0_ts']}|{len(x['ev'])}\n".encode())
man=dict(parser="regime_cache_v1",built=time.strftime("%Y-%m-%d %H:%M:%S"),N=len(P),by_day=dict(collections.Counter(x["day"] for x in P)),by_source=dict(collections.Counter(x["source"] for x in P)),exclusions=dict(excl),population_sha256=pop.hexdigest(),content_sha256=h.hexdigest(),pool_events=sum(len(x["ev"]) for x in P),outage_windows=len(OUT_W),script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest())
json.dump(man,open(f"{OUT}/regime_cache_manifest.json","w"),indent=1); print(json.dumps(man)); print("REGIME_CACHE_DONE",flush=True)
