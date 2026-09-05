"""Faza 1: scanare completa a benzii (o singura trecere grea, nice 19) — grupare (semnatura, user, base_mint) pe fiecare linie (tranzactie); candidati = grupuri cu >=2 pool-uri distincte si >=1 buy + >=1 sell.
Cache local (nepublicat): derived/census_candidates.jsonl.gz cu evenimentele decodate integral. Fara profit."""
import gzip,json,base64,struct,os,glob,sys,time,zlib,hashlib,collections
sys.path.insert(0,'strategy_e'); from pda import b58e
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; TAPE="strategy_m/data/tape"; WSOL="So11111111111111111111111111111111111111112"
META={}
for l in gzip.open("research/pool_metadata_normalized.jsonl.gz","rt"): r=json.loads(l); META[r["pool"]]=r
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
def decode(e):
    raw=base64.b64decode(e["raw"]); L=len(raw)
    if e["ev"]=="BuyEvent" and L not in (465,480): return None
    if e["ev"]=="SellEvent" and L!=417: return None
    ts,=struct.unpack_from("<q",raw,8); amt,mx,ub,uq,rb,rq,q2=struct.unpack_from("<QQQQQQQ",raw,16); lpbp,lpf,prbp,prf,q3,uq2=struct.unpack_from("<QQQQQQ",raw,72); pool=b58e(raw[120:152]); user=b58e(raw[152:184])
    if e["ev"]=="BuyEvent": isb=1; rb_post=rb-amt; rq_post=rq+q3; user_q=max(q2,uq2); cp=q3-lpf; inv=(rb_post>=0 and cp>=0)
    else: isb=0; rb_post=rb+amt; rq_post=rq-q3; user_q=min(q2,uq2); cp=q3+lpf; inv=(rq_post>=0)
    return dict(pool=pool,user=user,is_buy=isb,base=amt,user_quote=user_q,q2=q2,uq2=uq2,q3=q3,lpf=lpf,prf=prf,lp_bp=lpbp,pr_bp=prbp,rb_pre=rb,rq_pre=rq,rb_post=rb_post,rq_post=rq_post,ts=ts,rawlen=L,inv_ok=inv)
N=collections.Counter(); out=gzip.open(f"{D}/census_candidates_v2.jsonl.gz","wt"); t0=time.time()
for fp in sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")):
    for line in readlines(fp):
        if '"src":"pamm"' not in line: continue
        nsw=line.count('"BuyEvent"')+line.count('"SellEvent"'); N["swap_events"]+=nsw
        if nsw<2: continue
        r=json.loads(line); N["multi_swap_lines"]+=1; evs=[]; unknown=0; dup=set(); dupflag=False
        for k,e in enumerate(r["events"]):
            if e["ev"] not in ("BuyEvent","SellEvent"): unknown+=(e["ev"]!="CreatePoolEvent"); continue
            d=decode(e)
            if d is None: N["undecodable_events"]+=1; unknown+=1; continue
            key=(d["pool"],k)
            if key in dup: dupflag=True
            dup.add(key); d["k"]=k; m=META.get(d["pool"]); d["meta"]=(dict(base_mint=m["base_mint"],quote_mint=m["quote_mint"],orientation=m["orientation"],canonical=m["canonical"],token_mint=m["token_mint"]) if m else None); evs.append(d)
        groups=collections.defaultdict(list); users_per_token=collections.defaultdict(set)
        for d in evs:
            tok=(d["meta"] or {}).get("token_mint") or ((d["meta"] or {}).get("base_mint")) or "UNKNOWN_POOL"
            groups[(d["user"],tok)].append(d); users_per_token[tok].add(d["user"])   # V2: utilizatori distincti PER TOKEN in aceeasi tranzactie (spec: flux multi-user pe acelasi mint => ambiguu)
        for (u,tok),g in groups.items():
            pools={d["pool"] for d in g}
            if len(pools)<2 or not any(d["is_buy"] for d in g) or not any(not d["is_buy"] for d in g): continue
            N["candidate_groups"]+=1
            out.write(json.dumps(dict(sig=r["sig"],slot=r["slot"],t=r["t"],user=u,token=tok,n_events_in_tx=len(r["events"]),n_swaps_in_tx=len(evs),unknown_events_in_tx=unknown,duplicate_event_keys=dupflag,users_in_tx=len({d["user"] for d in evs}),users_for_token=len(users_per_token[tok]),events=g),separators=(",",":"))+"\n")
    print(os.path.basename(fp),dict(N),round(time.time()-t0),"s",flush=True)
out.close(); json.dump(dict(built=time.strftime("%Y-%m-%d %H:%M:%S"),counters=dict(N),cache_sha256=hashlib.sha256(open(f"{D}/census_candidates_v2.jsonl.gz","rb").read()).hexdigest(),script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest(),pools_in_metadata=len(META)),open(f"{D}/census_scan_manifest_v2.json","w"),indent=1); print("CENSUS_SCAN_DONE",flush=True)
