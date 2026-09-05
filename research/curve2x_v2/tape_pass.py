"""CURVE2X V2 — HISTORICAL_REMEDIATION_NOT_SEALED. Trecerea unica peste banda locala existenta (zero RPC): pentru fiecare CreateEvent pump.fun,
trade-urile de curba pana la create+WINDOW s si, pentru mint-urile care migreaza, evenimentele pool-ului PumpSwap creat in banda (CreatePoolEvent),
decodate exact (layout validat anterior: ts@8, amt..q2@16 x7 u64, lpbp,lpf,prbp,prf,q3,uq2@72, pool@120, user@152; rezervele = PRE-trade).
Iesiri (cache local, nepublicat): derived/curve2x_curves.jsonl.gz (un mint per linie), derived/curve2x_stream.jsonl.gz (evenimente de curba in ordinea benzii,
folosite de motorul de decizie in batch si in replay), derived/curve2x_pass_manifest.json. Nu modifica banda bruta."""
import gzip,json,os,glob,sys,time,zlib,collections,hashlib,base64,struct,datetime
sys.path.insert(0,"strategy_e"); import pda
D=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(os.path.abspath(__file__)),"derived")); TAPE="strategy_m/data/tape"; WINDOW=3720
PAMM="pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"; PUMP="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"; WSOL="So11111111111111111111111111111111111111112"; WSOL_B=pda.b58d(WSOL)
META={}
for l in gzip.open("research/pool_metadata_normalized.jsonl.gz","rt"): _r=json.loads(l); META[_r["pool"]]=_r["canonical"]
CANON_CMP=collections.Counter()
M={}; POOLS={}; t0=time.time(); n_tr=0; n_pe=0; seq=0; flushed=0; trunc={}; c_ev=collections.Counter()
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
out=gzip.open(f"{D}/curve2x_curves.jsonl.gz","wt"); stream=gzip.open(f"{D}/curve2x_stream.jsonl.gz","wt")
def flush(before_ts):
    global flushed
    for m in [m for m,v in M.items() if v["create_ts"]+WINDOW+90<before_ts]:
        v=M.pop(m)
        if v.get("pool"): POOLS.pop(v["pool"]["key"],None); v["pool"].pop("key",None)
        out.write(json.dumps(v,separators=(",",":"))+"\n"); flushed+=1
files=sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz"))
for fp in files:
    last=None
    for line in readlines(fp):
        if '"src":"pump"' in line:
            r=json.loads(line); t=int(r["t"]); last=t; slot=r["slot"]
            for k,e in enumerate(r["events"]):
                ev=e["ev"]; c_ev[ev]+=1
                if ev=="CreateEvent":
                    if e["mint"] not in M:
                        M[e["mint"]]=dict(mint=e["mint"],creator=e["user"],create_ts=t,create_slot=slot,create_seq=seq,complete_ts=None,complete_slot=None,complete_seq=None,trades=[],pool=None)
                        stream.write(json.dumps(["C",t,slot,seq,e["mint"],e["user"]],separators=(",",":"))+"\n")
                elif ev=="TradeEvent":
                    v=M.get(e["mint"])
                    if v is None: continue
                    ts=e.get("ts") or t
                    if ts>v["create_ts"]+WINDOW: continue
                    row=[ts,slot,seq,k,e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"]]; v["trades"].append(row); n_tr+=1
                    stream.write(json.dumps(["T",ts,slot,seq,k,e["mint"],e["user"],e["sol"],e["tok"],row[7],e["rsol"],e["rtok"],e["vsol"],e["vtok"]],separators=(",",":"))+"\n")
                elif ev=="CompleteEvent":
                    v=M.get(e["mint"])
                    if v is not None and v["complete_ts"] is None:
                        v["complete_ts"]=int(next((x.get("ts") for x in r["events"] if x["ev"]=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),t)); v["complete_slot"]=slot; v["complete_seq"]=seq
                        stream.write(json.dumps(["X",v["complete_ts"],slot,seq,e["mint"]],separators=(",",":"))+"\n")
            seq+=1
            if slot%2000==0: flush(t)
        elif '"src":"pamm"' in line:
            if 'CreatePoolEvent' in line:
                r=json.loads(line); t=int(r["t"]); last=t
                for k,e in enumerate(r["events"]):
                    if e["ev"]!="CreatePoolEvent": continue
                    c_ev["CreatePoolEvent"]+=1; raw=base64.b64decode(e["raw"]); ts,=struct.unpack_from("<q",raw,8); idx,=struct.unpack_from("<H",raw,16); creator=raw[18:50]; bm=pda.b58e(raw[50:82]); qm_b=raw[82:114]
                    base_in,quote_in,pool_base,pool_quote=struct.unpack_from("<QQQQ",raw,116); pool_b=raw[173:205]; v=M.get(bm)
                    if v is None or v["pool"] is not None: continue
                    auth=pda.find_pda([b"pool-authority",pda.b58d(bm)],pda.b58d(PUMP))[0]
                    v["pool"]=dict(key=pool_b,pool=pda.b58e(pool_b),index=idx,canonical=bool(idx==0 and pda.b58e(creator)==auth),quote_wsol=bool(qm_b==WSOL_B),cp_ts=ts,cp_slot=r["slot"],cp_seq=seq,pool_base=pool_base,pool_quote=pool_quote,events=[])
                    POOLS[pool_b]=bm; _c=META.get(v["pool"]["pool"]); CANON_CMP["NOT_IN_METADATA" if _c is None else ("MATCH" if _c==v["pool"]["canonical"] else "MISMATCH")]+=1
                seq+=1
            elif POOLS and ('BuyEvent' in line or 'SellEvent' in line):
                r=json.loads(line); t=int(r["t"]); last=t
                for k,e in enumerate(r["events"]):
                    if e["ev"] not in ("BuyEvent","SellEvent"): continue
                    raw=base64.b64decode(e["raw"]); m=POOLS.get(raw[120:152])
                    if m is None: continue
                    v=M.get(m)
                    if v is None: continue
                    ts,=struct.unpack_from("<q",raw,8)
                    if ts>v["create_ts"]+WINDOW: continue
                    amt,mx,ub,uq,rb,rq,q2=struct.unpack_from("<QQQQQQQ",raw,16); lpbp,lpf,prbp,prf,q3,uq2=struct.unpack_from("<QQQQQQ",raw,72)
                    if e["ev"]=="BuyEvent":
                        rb_post=rb-amt; rq_post=rq+q3; cp_q=q3-lpf; gross=max(q2,uq2); cce=max(0,round((gross-cp_q-lpf-prf)*10000/cp_q)) if cp_q>0 else 0
                    else:
                        rb_post=rb+amt; rq_post=rq-q3; cp_q=q3+lpf; net=min(q2,uq2); cce=max(0,round((cp_q-lpf-prf-net)*10000/cp_q)) if cp_q>0 else 0
                    v["pool"]["events"].append([ts,r["slot"],seq,k,1 if e["ev"]=="BuyEvent" else 0,rb,rq,rb_post,rq_post,amt,cp_q,lpbp,prbp,cce]); n_pe+=1
                seq+=1
            else: seq+=1
        else: seq+=1
    trunc[os.path.basename(fp)]=last
    print(os.path.basename(fp),"open",len(M),"flushed",flushed,"trades",n_tr,"pool_ev",n_pe,round(time.time()-t0),"s",flush=True)
flush(10**12); out.close(); stream.close()
OUT_W=[]; o=None
for line in open(f"{TAPE}/collector.log"):
    if len(line)<20: continue
    try: tt=datetime.datetime.strptime(line[:19],"%Y-%m-%d %H:%M:%S").timestamp()
    except Exception: continue
    if "DECONECTARE" in line and o is None: o=tt
    if "conectat:" in line and o is not None: OUT_W.append((o,tt)); o=None
man=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),files=len(files),mints=flushed,trades=n_tr,pool_events=n_pe,window_s=WINDOW,events_seen=dict(c_ev),outage_windows=OUT_W,file_last_t=trunc,
         curves_sha256=hashlib.sha256(open(f"{D}/curve2x_curves.jsonl.gz","rb").read()).hexdigest(),stream_sha256=hashlib.sha256(open(f"{D}/curve2x_stream.jsonl.gz","rb").read()).hexdigest(),script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest(),runtime_s=round(time.time()-t0,1),rpc_calls=0,canonical_vs_phase1_metadata=dict(CANON_CMP))
json.dump(man,open(f"{D}/curve2x_pass_manifest.json","w"),indent=1); print("TAPE_PASS_DONE",flush=True)
