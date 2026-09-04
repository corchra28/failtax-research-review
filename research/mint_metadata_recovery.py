"""PREGATIT, NEEXECUTAT (fetch): maximum 2 apeluri getMultipleAccounts pentru mint-urile ELIGIBLE_BEFORE_TOKEN_PROGRAM (research/atomic_same_mint_arb_populations_frozen.json).
Obtine: owner-ul contului, primii 82 bytes ai Mint (mint_authority option[4+32]@0, supply u64@36, decimals u8@44, is_initialized u8@45, freeze_authority option[4+32]@46), commitment finalized, base64.
Token-2022 si owner necunoscut => EXCLUSE. Supply cu mint_authority prezenta (poate varia) => token exclus din tierele de taxe pe supply, daca tierul nu este demonstrat din evenimente.
Etape: freeze (lista + sha + batch-uri, FARA RPC) -> fetch (NUMAI cu aprobare explicita) -> normalize."""
import gzip,json,hashlib,time,sys,os,base64,struct,subprocess
sys.path.insert(0,'.'); sys.path.insert(0,'strategy_e'); import pda
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; RAW=f"{D}/mint_accounts_raw.jsonl.gz"; MAN="research/mint_metadata_recovery_manifest.json"; POP="research/atomic_same_mint_arb_populations_frozen.json"
SPL_TOKEN="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"; TOKEN_2022="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"; SLICE=82; BATCH=100; MAX_CALLS=2
stage=sys.argv[1]
if stage=="freeze":
    mints=sorted(json.load(open(POP))["proposed_mint_rpc"]["eligible_mints"]); assert len(mints)<=BATCH*MAX_CALLS, "peste bugetul de 2 apeluri"
    lst="\n".join(mints); open(f"{D}/mint_list_frozen.txt","w").write(lst)
    man=dict(frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),source_commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True).stdout.strip(),n_mints=len(mints),mint_list_sha256=hashlib.sha256(lst.encode()).hexdigest(),batch_size=BATCH,n_batches=(len(mints)+BATCH-1)//BATCH,max_calls=MAX_CALLS,rpc_method="getMultipleAccounts",params=dict(commitment="finalized",encoding="base64",dataSlice=dict(offset=0,length=SLICE)),layout="mint_authority option(4+32)@0 supply u64@36 decimals u8@44 is_initialized u8@45 freeze_authority option(4+32)@46",script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest(),status="FROZEN_NOT_EXECUTED (fetch cere aprobare explicita)")
    json.dump(man,open(MAN,"w"),indent=1); print(json.dumps(man,indent=1)); sys.exit(0)
man=json.load(open(MAN)); mints=open(f"{D}/mint_list_frozen.txt").read().split("\n"); assert hashlib.sha256("\n".join(mints).encode()).hexdigest()==man["mint_list_sha256"]
if stage=="fetch":
    assert os.environ.get("MINT_RPC_APPROVED")=="YES", "fetch neaprobat: seteaza MINT_RPC_APPROVED=YES doar dupa aprobare explicita"
    from load_key import get_helius_key; import requests
    url=f"https://mainnet.helius-rpc.com/?api-key={get_helius_key()}"; S=requests.Session(); calls=0; errors=[]
    with gzip.open(RAW,"wt") as f:
        for b in range(man["n_batches"]):
            if calls>=MAX_CALLS: errors.append(dict(batch=b,error="BUDGET_EXHAUSTED")); continue
            chunk=mints[b*BATCH:(b+1)*BATCH]; calls+=1
            try:
                j=S.post(url,json={"jsonrpc":"2.0","id":b,"method":"getMultipleAccounts","params":[chunk,{"commitment":"finalized","encoding":"base64","dataSlice":{"offset":0,"length":SLICE}}]},timeout=60).json()
                if "result" not in j: errors.append(dict(batch=b,error=str(j.get("error",""))[:200])); continue
                for a,v in zip(chunk,j["result"]["value"]): f.write(json.dumps(dict(mint=a,account=v))+"\n")
            except Exception as e: errors.append(dict(batch=b,error=type(e).__name__))
    man.update(status="FETCHED",rpc_request_count=calls,errors=errors,fetched_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),raw_cache_sha256=hashlib.sha256(open(RAW,"rb").read()).hexdigest()); json.dump(man,open(MAN,"w"),indent=1); print("calls",calls,"errors",len(errors)); sys.exit(0)
if stage=="normalize":
    out={}; cnt={"SPL_TOKEN":0,"TOKEN_2022_EXCLUDED":0,"UNKNOWN_OWNER_EXCLUDED":0,"NULL":0,"SHORT":0}
    for l in gzip.open(RAW,"rt"):
        r=json.loads(l); v=r["account"]
        if v is None: cnt["NULL"]+=1; continue
        raw=base64.b64decode(v["data"][0])
        if len(raw)<SLICE: cnt["SHORT"]+=1; continue
        owner=v["owner"]; ma_opt,=struct.unpack_from("<I",raw,0); supply,=struct.unpack_from("<Q",raw,36); dec=raw[44]; init=raw[45]; fa_opt,=struct.unpack_from("<I",raw,46)
        status="SPL_TOKEN" if owner==SPL_TOKEN else ("TOKEN_2022_EXCLUDED" if owner==TOKEN_2022 else "UNKNOWN_OWNER_EXCLUDED"); cnt[status]+=1
        out[r["mint"]]=dict(owner=owner,status=status,supply=supply,decimals=dec,initialized=bool(init),mint_authority_present=bool(ma_opt),freeze_authority_present=bool(fa_opt),supply_may_vary=bool(ma_opt),eligible_for_pnl=(status=="SPL_TOKEN" and bool(init)))
    json.dump(out,open("research/token_program_map_full.json","w"),indent=1); json.dump({m:v["owner"] for m,v in out.items()},open("research/token_program_map.json","w"),indent=1); print(cnt); sys.exit(0)
