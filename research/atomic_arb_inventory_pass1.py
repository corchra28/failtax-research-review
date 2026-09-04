"""ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE — trecerea 1 (FARA PnL): inventarul complet al pool-urilor PumpSwap din banda prospectiva.
CreatePoolEvent decodat integral (pool, index, creator, base/quote mint, zecimale, cantitati initiale, slot, ts, sig, t) + per pool: numar Buy/Sell, primul/ultimul slot,
histograma bps observate (lp, protocol, creator), evenimente cu taxa zero; tipurile de evenimente prezente. Iesire: scratchpad/derived/pamm_pool_inventory.json(.gz)."""
import gzip,json,base64,struct,os,glob,collections,sys,time,zlib,hashlib
sys.path.insert(0,'strategy_e'); import pda; from pda import b58e
TAPE="strategy_m/data/tape"; OUT="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; PUMP="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"; PUMPB=pda.b58d(PUMP)
files=sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz"))
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
pools={}; evn=collections.Counter(); PS=collections.defaultdict(lambda:dict(n_buy=0,n_sell=0,first_slot=None,last_slot=None,first_t=None,last_t=None,bps=collections.Counter(),zero_fee=0,rawlen=collections.Counter())); t0=time.time(); seq=0
for fp in files:
    for line in readlines(fp):
        if '"src":"pamm"' not in line: continue
        r=json.loads(line)
        for k,e in enumerate(r["events"]):
            ev=e["ev"]; evn[ev]+=1
            if ev=="CreatePoolEvent":
                raw=base64.b64decode(e["raw"]); ts,=struct.unpack_from("<q",raw,8); idx,=struct.unpack_from("<H",raw,16); creator=b58e(raw[18:50]); bm=b58e(raw[50:82]); qm=b58e(raw[82:114]); bd,qd=raw[114],raw[115]
                base_in,quote_in,pool_base,pool_quote=struct.unpack_from("<QQQQ",raw,116); pool=b58e(raw[173:205]); coin_creator=b58e(raw[-32:])
                auth=pda.find_pda([b"pool-authority",pda.b58d(bm)],PUMPB)[0]
                canonical=(idx==0 and creator==auth)
                pools[pool]=dict(pool=pool,index=idx,creator=creator,base_mint=bm,quote_mint=qm,base_dec=bd,quote_dec=qd,base_in=base_in,quote_in=quote_in,pool_base=pool_base,pool_quote=pool_quote,coin_creator=coin_creator,slot=r["slot"],ts=ts,t=r["t"],sig=r["sig"],rawlen=len(raw),pump_authority=auth,canonical=canonical,seq=seq,k=k)
            elif ev in ("BuyEvent","SellEvent"):
                raw=base64.b64decode(e["raw"]); pool=b58e(raw[120:152]); lpbp,lpf,prbp,prf=struct.unpack_from("<QQQQ",raw,72); ccbp=struct.unpack_from("<Q",raw,344)[0] if len(raw)>=352 else -1
                s=PS[pool]; s["n_buy" if ev=="BuyEvent" else "n_sell"]+=1; s["first_slot"]=r["slot"] if s["first_slot"] is None else min(s["first_slot"],r["slot"]); s["last_slot"]=r["slot"] if s["last_slot"] is None else max(s["last_slot"],r["slot"]); s["first_t"]=r["t"] if s["first_t"] is None else min(s["first_t"],r["t"]); s["last_t"]=r["t"] if s["last_t"] is None else max(s["last_t"],r["t"])
                s["bps"][f"{lpbp}/{prbp}/{ccbp}"]+=1; s["rawlen"][len(raw)]+=1
                if lpbp==0 and prbp==0: s["zero_fee"]+=1
        seq+=1
    print(os.path.basename(fp),"pools",len(pools),"active",len(PS),round(time.time()-t0),"s",flush=True)
inv=dict(built=time.strftime("%Y-%m-%d %H:%M:%S"),event_types=dict(evn),n_create_pool=len(pools),n_active_pools=len(PS),pools=pools,stats={p:dict(v,bps=dict(v["bps"]),rawlen=dict(v["rawlen"])) for p,v in PS.items()})
os.makedirs(OUT,exist_ok=True)
with gzip.open(f"{OUT}/pamm_pool_inventory.json.gz","wt") as f: json.dump(inv,f)
print("event_types",dict(evn),"create",len(pools),"active",len(PS)); print("INVENTORY_DONE",flush=True)
