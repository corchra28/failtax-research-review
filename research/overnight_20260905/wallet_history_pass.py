"""Stage 1 (o singura trecere grea, fara outcome-uri): istoricul comportamental al portofelelor relevante din tape-ul existent — pentru fiecare portofel relevant, per mint tranzactionat (curba sau pool), timestamp-ul primei tranzactii.
Pool -> mint prin CreatePoolEvent (in banda) + metadatele RPC normalizate (pool_metadata_normalized.jsonl.gz, deja recuperate). Iesire: derived/wallet_history.jsonl.gz {wallet: {mint: first_ts}}."""
import gzip,json,base64,struct,os,glob,sys,time,zlib,hashlib,collections
sys.path.insert(0,'strategy_e'); from pda import b58e
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; TAPE="strategy_m/data/tape"
W=set(open(f"{D}/relevant_wallets.txt").read().split("\n")); pool2mint={}
for l in gzip.open("research/pool_metadata_normalized.jsonl.gz","rt"): r=json.loads(l); pool2mint[r["pool"]]=r["token_mint"] or r["base_mint"]
inv=json.load(gzip.open(f"{D}/pamm_pool_inventory.json.gz","rt"))
for p,m in inv["pools"].items(): pool2mint.setdefault(p,m["base_mint"] if m["quote_mint"]=="So11111111111111111111111111111111111111112" else m["quote_mint"])
H=collections.defaultdict(dict); t0=time.time(); n_ev=0
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
for fp in sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")):
    for line in readlines(fp):
        if '"src":"pump"' in line:
            if 'TradeEvent' not in line: continue
            r=json.loads(line)
            for e in r["events"]:
                if e["ev"]=="TradeEvent" and e["user"] in W:
                    h=H[e["user"]]; m=e["mint"]; ts=e.get("ts") or int(r["t"])
                    if m not in h or ts<h[m]: h[m]=ts
                    n_ev+=1
        elif '"src":"pamm"' in line and ('BuyEvent' in line or 'SellEvent' in line):
            r=json.loads(line)
            for e in r["events"]:
                if e["ev"] not in ("BuyEvent","SellEvent"): continue
                raw=base64.b64decode(e["raw"]); u=b58e(raw[152:184])
                if u not in W: continue
                pool=b58e(raw[120:152]); m=pool2mint.get(pool)
                if not m: continue
                ts,=struct.unpack_from("<q",raw,8); h=H[u]
                if m not in h or ts<h[m]: h[m]=ts
                n_ev+=1
    print(os.path.basename(fp),"wallets",len(H),"ev",n_ev,round(time.time()-t0),"s",flush=True)
hh=hashlib.sha256()
with gzip.open(f"{D}/wallet_history.jsonl.gz","wt") as f:
    for u in sorted(H): s=json.dumps(dict(w=u,m=H[u]),separators=(",",":"))+"\n"; f.write(s); hh.update(s.encode())
json.dump(dict(built=time.strftime("%Y-%m-%d %H:%M:%S"),relevant_wallets=len(W),wallets_with_history=len(H),events=n_ev,content_sha256=hh.hexdigest(),pool2mint_entries=len(pool2mint),script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest()),open(f"{D}/wallet_history_manifest.json","w"),indent=1)
print("WALLET_HISTORY_DONE",flush=True)
