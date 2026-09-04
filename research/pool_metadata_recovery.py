"""PHASE 1 POOL METADATA RECOVERY — aprobat explicit: max 325 apeluri getMultipleAccounts (100 adrese/apel), read-only, finalized, base64, dataSlice 0..107,
exclusiv pentru pool-urile PumpSwap deja observate local. Fara retry peste buget. Tokenul/URL-ul Helius nu se afiseaza si nu se salveaza. Fara PnL.
Etape: freeze (lista + sha + batch-uri + manifest) -> fetch -> validare -> control semantic vs CreatePoolEvent -> normalizare (creatori hash-uiti) -> grupare same-mint."""
import gzip,json,hashlib,time,sys,os,base64,collections,struct,subprocess
sys.path.insert(0,'.'); sys.path.insert(0,'strategy_e'); import pda; from load_key import get_helius_key
import requests
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; INV=f"{D}/pamm_pool_inventory.json.gz"; RAW=f"{D}/pool_accounts_raw.jsonl.gz"; MAN="research/pool_metadata_recovery_manifest.json"
PAMM="pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"; PUMP="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"; WSOL="So11111111111111111111111111111111111111112"; NS="external-review-v1"
DISC=hashlib.sha256(b"account:Pool").digest()[:8]; SLICE=107; BATCH=100; MAX_CALLS=325
def hid(a): return hashlib.sha256(f"{NS}:{a}".encode()).hexdigest()[:32]
stage=sys.argv[1]
if stage=="freeze":
    inv=json.load(gzip.open(INV,"rt")); pools=sorted(inv["stats"].keys()); assert len(pools)==len(set(pools))
    lst="\n".join(pools); sha=hashlib.sha256(lst.encode()).hexdigest(); nb=(len(pools)+BATCH-1)//BATCH; assert nb<=MAX_CALLS
    open(f"{D}/pool_list_frozen.txt","w").write(lst)
    man=dict(frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),source_commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True).stdout.strip(),n_pools=len(pools),pool_list_sha256=sha,batch_size=BATCH,n_batches=nb,max_calls=MAX_CALLS,rpc_method="getMultipleAccounts",params=dict(commitment="finalized",encoding="base64",dataSlice=dict(offset=0,length=SLICE)),discriminator_hex=DISC.hex(),layout="disc[0:8] pool_bump[8] index u16le[9:11] creator[11:43] base_mint[43:75] quote_mint[75:107]",script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest(),inventory_sha256=hashlib.sha256(open(INV,"rb").read()).hexdigest(),status="FROZEN_BEFORE_CALLS")
    json.dump(man,open(MAN,"w"),indent=1); print(json.dumps(man,indent=1)); sys.exit(0)
man=json.load(open(MAN)); pools=open(f"{D}/pool_list_frozen.txt").read().split("\n"); assert hashlib.sha256("\n".join(pools).encode()).hexdigest()==man["pool_list_sha256"]
if stage=="fetch":
    assert man["status"]=="FROZEN_BEFORE_CALLS"
    url=f"https://mainnet.helius-rpc.com/?api-key={get_helius_key()}"; S=requests.Session(); calls=0; errors=[]; t0=time.time()
    with gzip.open(RAW,"wt") as f:
        for b in range(man["n_batches"]):
            chunk=pools[b*BATCH:(b+1)*BATCH]
            if calls>=MAX_CALLS: errors.append(dict(batch=b,error="BUDGET_EXHAUSTED")); continue
            calls+=1
            try:
                r=S.post(url,json={"jsonrpc":"2.0","id":b,"method":"getMultipleAccounts","params":[chunk,{"commitment":"finalized","encoding":"base64","dataSlice":{"offset":0,"length":SLICE}}]},timeout=60); j=r.json()
                if "result" not in j: errors.append(dict(batch=b,error=str(j.get("error",""))[:200])); continue
                for a,v in zip(chunk,j["result"]["value"]): f.write(json.dumps(dict(pool=a,batch=b,account=v))+"\n")
            except Exception as e: errors.append(dict(batch=b,error=type(e).__name__))
            time.sleep(0.15)
    man.update(status="FETCHED",rpc_request_count=calls,errors=errors,fetched_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),wall_s=round(time.time()-t0,1),raw_cache_sha256=hashlib.sha256(open(RAW,"rb").read()).hexdigest()); json.dump(man,open(MAN,"w"),indent=1)
    print("calls",calls,"errors",len(errors),"wall",round(time.time()-t0,1)); sys.exit(0)
if stage=="normalize":
    inv=json.load(gzip.open(INV,"rt")); CP=inv["pools"]; rows=[]; null=0; bad_owner=0; bad_disc=0; short=0; seen=set(); dup=0
    for l in gzip.open(RAW,"rt"):
        r=json.loads(l); a=r["pool"]
        if a in seen: dup+=1; continue
        seen.add(a); v=r["account"]
        if v is None: null+=1; continue
        if v.get("owner")!=PAMM: bad_owner+=1; continue
        raw=base64.b64decode(v["data"][0])
        if len(raw)<SLICE: short+=1; continue
        if raw[:8]!=DISC: bad_disc+=1; continue
        idx,=struct.unpack_from("<H",raw,9); creator=pda.b58e(raw[11:43]); bm=pda.b58e(raw[43:75]); qm=pda.b58e(raw[75:107])
        rows.append(dict(pool=a,pool_bump=raw[8],index=idx,creator=creator,base_mint=bm,quote_mint=qm))
    # control semantic vs CreatePoolEvent local
    cmp=dict(compared=0,match=0,mismatch=[])
    for r in rows:
        c=CP.get(r["pool"])
        if not c: continue
        cmp["compared"]+=1
        ok=(c["index"]==r["index"] and c["creator"]==r["creator"] and c["base_mint"]==r["base_mint"] and c["quote_mint"]==r["quote_mint"])
        if ok: cmp["match"]+=1
        elif len(cmp["mismatch"])<20: cmp["mismatch"].append(dict(pool=r["pool"],rpc=dict(index=r["index"],base=r["base_mint"][:8],quote=r["quote_mint"][:8]),event=dict(index=c["index"],base=c["base_mint"][:8],quote=c["quote_mint"][:8])))
    cmp["match_rate"]=cmp["match"]/cmp["compared"] if cmp["compared"] else None
    assert cmp["match_rate"] is not None and cmp["match_rate"]>=0.999, f"decodor invalid: match rate {cmp['match_rate']}"
    # clasificare + normalizare publica (creatorii utilizatorilor hash-uiti; autoritatea pump ramane identificabila prin flag)
    auth_cache={}; out=[]
    for r in rows:
        tok=None; orient=None
        if r["quote_mint"]==WSOL and r["base_mint"]!=WSOL: tok=r["base_mint"]; orient="STRICT"
        elif r["base_mint"]==WSOL and r["quote_mint"]!=WSOL: tok=r["quote_mint"]; orient="REVERSED"
        canon=False
        if tok:
            if tok not in auth_cache: auth_cache[tok]=pda.find_pda([b"pool-authority",pda.b58d(tok)],pda.b58d(PUMP))[0]
            canon=(r["index"]==0 and r["creator"]==auth_cache[tok] and orient=="STRICT")
        out.append(dict(pool=r["pool"],index=r["index"],pool_bump=r["pool_bump"],base_mint=r["base_mint"],quote_mint=r["quote_mint"],token_mint=tok or "",orientation=orient or "NO_WSOL",creator_id=hid(r["creator"]),creator_is_pump_authority=bool(tok and r["creator"]==auth_cache[tok]),canonical=canon,in_tape_createpool=(r["pool"] in CP)))
    with gzip.open("research/pool_metadata_normalized.jsonl.gz","wt") as f:
        for o in out: f.write(json.dumps(o)+"\n")
    # grupare same-mint
    groups=collections.defaultdict(list); [groups[o["token_mint"]].append(o) for o in out if o["token_mint"]]
    pairs={t:g for t,g in groups.items() if len(g)>=2}; typ=collections.Counter(); ctyp=collections.Counter()
    for t,g in pairs.items():
        for i in range(len(g)):
            for j in range(i+1,len(g)):
                a,b=g[i],g[j]; o=tuple(sorted([a["orientation"],b["orientation"]])); typ["_".join(o)]+=1; c=a["canonical"]+b["canonical"]; ctyp["CANONICAL+NONCANONICAL" if c==1 else ("NONCANONICAL+NONCANONICAL" if c==0 else "CANONICAL+CANONICAL")]+=1
    rep=dict(TOTAL_ACCOUNTS_REQUESTED=len(pools),RPC_REQUEST_COUNT=man.get("rpc_request_count"),ACCOUNTS_RECOVERED=len(rows),NULL_ACCOUNTS=null,INVALID_OWNER=bad_owner,INVALID_DISCRIMINATOR=bad_disc,SHORT_DATA=short,DUPLICATES=dup,CREATEPOOL_METADATA_MATCH_RATE=cmp["match_rate"],createpool_compared=cmp["compared"],mismatches=cmp["mismatch"],UNIQUE_TOKEN_MINTS=len(groups),SAME_MINT_PAIRS_TOTAL=len(pairs),STRICT_STRICT_PAIRS=typ.get("STRICT_STRICT",0),STRICT_REVERSED_PAIRS=typ.get("REVERSED_STRICT",0),REVERSED_REVERSED_PAIRS=typ.get("REVERSED_REVERSED",0),CANONICAL_NONCANONICAL_PAIRS=ctyp.get("CANONICAL+NONCANONICAL",0),NONCANONICAL_NONCANONICAL_PAIRS=ctyp.get("NONCANONICAL+NONCANONICAL",0),CANONICAL_CANONICAL_PAIRS=ctyp.get("CANONICAL+CANONICAL",0),orientation_counts=dict(collections.Counter(o["orientation"] for o in out)),canonical_pools=sum(1 for o in out if o["canonical"]),same_mint_groups_size_hist=dict(collections.Counter(len(g) for g in pairs.values())),normalized_sha256=hashlib.sha256(open("research/pool_metadata_normalized.jsonl.gz","rb").read()).hexdigest(),raw_cache_sha256=man.get("raw_cache_sha256"))
    json.dump(dict(pairs={t:[o["pool"] for o in g] for t,g in pairs.items()}),open(f"{D}/same_mint_pairs_rpc.json","w"))
    json.dump(rep,open("research/pool_metadata_recovery_report.json","w"),indent=1); print(json.dumps({k:v for k,v in rep.items() if k!="mismatches"},indent=1)); print("mismatches",cmp["mismatch"][:5]); print("NORMALIZE_DONE")
