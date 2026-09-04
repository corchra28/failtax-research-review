"""Faza 3: implementare INDEPENDENTA a recensamantului (nu importa functiile primare): reparcurge banda cu propriul decodor si propria grupare, numara semnaturi candidate, cicluri exact conservate, sume, profit brut, token-uri/zile; esantion determinist de 100 semnaturi verificat camp cu camp. Compara cu iesirea primara la lamport."""
import gzip,json,base64,struct,os,glob,sys,time,zlib,hashlib,collections,random
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/overnight_20260905/atomic_census"; TAPE="strategy_m/data/tape"; WSOL="So11111111111111111111111111111111111111112"
ALPH="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58(b):
    n=int.from_bytes(b,"big"); s=""
    while n: n,r=divmod(n,58); s=ALPH[r]+s
    return "1"*(len(b)-len(b.lstrip(b"\0")))+s
meta={}
for l in gzip.open("research/pool_metadata_normalized.jsonl.gz","rt"): r=json.loads(l); meta[r["pool"]]=(r["base_mint"],r["quote_mint"],r["orientation"])
def u64(raw,o): return int.from_bytes(raw[o:o+8],"little")
def parse(ev):
    raw=base64.b64decode(ev["raw"]); L=len(raw); kind=ev["ev"]
    if (kind=="BuyEvent" and L not in (465,480)) or (kind=="SellEvent" and L!=417): return None
    base=u64(raw,16); q64=u64(raw,64); q112=u64(raw,112); rb=u64(raw,48); rq=u64(raw,56); q104=u64(raw,104); lpf=u64(raw,80)
    if kind=="BuyEvent": return dict(kind="B",pool=b58(raw[120:152]),user=b58(raw[152:184]),base=base,uq=max(q64,q112),pre=(rb,rq),post=(rb-base,rq+q104),ok=(rb-base>=0 and q104-lpf>=0),fee=(u64(raw,72),u64(raw,88)))
    return dict(kind="S",pool=b58(raw[120:152]),user=b58(raw[152:184]),base=base,uq=min(q64,q112),pre=(rb,rq),post=(rb+base,rq-q104),ok=(rq-q104>=0),fee=(u64(raw,72),u64(raw,88)))
def scan():
    cand=[]; nsw=0; t0=time.time()
    for fp in sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")):
        try:
            with gzip.open(fp,"rt") as f:
                for line in f:
                    if '"src":"pamm"' not in line: continue
                    c=line.count('Event"'); 
                    if line.count('"BuyEvent"')+line.count('"SellEvent"')<2:
                        nsw+=line.count('"BuyEvent"')+line.count('"SellEvent"'); continue
                    r=json.loads(line); P=[]; bad=False; keys=set()
                    for k,e in enumerate(r["events"]):
                        if e["ev"] in ("BuyEvent","SellEvent"):
                            nsw+=1; d=parse(e)
                            if d is None: bad=True; continue
                            if (d["pool"],k) in keys: bad=True
                            keys.add((d["pool"],k)); d["k"]=k; P.append(d)
                        elif e["ev"]!="CreatePoolEvent": bad=True
                    G=collections.defaultdict(list)
                    for d in P:
                        m=meta.get(d["pool"]); tok=(m[0] if (m and m[1]==WSOL) else (m[1] if m else "?")); G[(d["user"],tok)].append(d)
                    for (u,tok),g in G.items():
                        if len({d["pool"] for d in g})<2 or not any(d["kind"]=="B" for d in g) or not any(d["kind"]=="S" for d in g): continue
                        strict=all(meta.get(d["pool"]) and meta[d["pool"]][1]==WSOL and meta[d["pool"]][2]=="STRICT" and meta[d["pool"]][0]==tok for d in g)
                        chain_ok=True; last={}
                        for d in g:
                            if d["pool"] in last and last[d["pool"]]!=d["pre"]: chain_ok=False
                            last[d["pool"]]=d["post"]
                        bought=sum(d["base"] for d in g if d["kind"]=="B"); sold=sum(d["base"] for d in g if d["kind"]=="S")
                        ok=(not bad) and strict and chain_ok and all(d["ok"] for d in g) and [d["k"] for d in g]==sorted(d["k"] for d in g)
                        cand.append(dict(sig=r["sig"],user=u,tok=tok,day=time.strftime("%Y-%m-%d",time.gmtime(r["t"])),exact=(ok and bought==sold and bought>0),dust=(ok and bought!=sold and bought>0 and abs(bought-sold)*10000<=bought),gross=(sum(d["uq"] for d in g if d["kind"]=="S")-sum(d["uq"] for d in g if d["kind"]=="B")),events=g))
        except (EOFError,zlib.error,OSError): pass
        print(os.path.basename(fp),len(cand),round(time.time()-t0),flush=True)
    return cand,nsw
if __name__=="__main__":
    cand,nsw=scan(); ex=[c for c in cand if c["exact"]]; du=[c for c in cand if c["dust"]]
    res=dict(TOTAL_SWAP_EVENTS_SCANNED=nsw,CANDIDATE_SIGNATURES=len({c["sig"] for c in cand}),candidate_groups=len(cand),EXACT=len(ex),DUST=len(du),gross_sum_exact_lamports=sum(c["gross"] for c in ex),unique_tokens_exact=len({c["tok"] for c in ex}),unique_users_exact=len({c["user"] for c in ex}),dates=sorted({c["day"] for c in ex}),by_day=dict(collections.Counter(c["day"] for c in ex)))
    # esantion determinist de 100 semnaturi exacte, verificat camp cu camp fata de cache-ul primar
    prim={}
    for l in gzip.open(f"{D}/census_candidates.jsonl.gz","rt"):
        c=json.loads(l); prim[(c["sig"],c["user"],c["token"])]=c
    rng=random.Random(20260905); sample=rng.sample(ex,min(100,len(ex))) if ex else []; agree=0; diffs=[]
    for c in sample:
        p=prim.get((c["sig"],c["user"],c["tok"]))
        if not p: diffs.append((c["sig"][:12],"MISSING_IN_PRIMARY")); continue
        pe=p["events"]; ok=(len(pe)==len(c["events"]) and all(a["pool"]==b["pool"] and a["user"]==b["user"] and (a["is_buy"]==1)==(b["kind"]=="B") and a["base"]==b["base"] and a["user_quote"]==b["uq"] and (a["rb_pre"],a["rq_pre"])==b["pre"] and (a["rb_post"],a["rq_post"])==b["post"] and (a["lp_bp"],a["pr_bp"])==b["fee"] and a["k"]==b["k"] for a,b in zip(pe,c["events"])))
        ok=ok and (sum(d["user_quote"] for d in pe if not d["is_buy"])-sum(d["user_quote"] for d in pe if d["is_buy"])==c["gross"])
        agree+=ok
        if not ok and len(diffs)<10: diffs.append((c["sig"][:12],"FIELD_MISMATCH"))
    res["sample_100"]=dict(n=len(sample),field_agreement=agree,diffs=diffs)
    json.dump(res,open(f"{OUT}/independent_census_results.json","w"),indent=1); print(json.dumps(res)); print("INDEPENDENT_DONE")
