"""FORWARD PAPER — persistenta atomica a starii, integritatea fisierelor procesate, spec_sha256 recalculat, labeler prospectiv (reconstruieste exclusiv din fisierele forward:
trade-uri de curba pana la orizont, CompleteEvent relevant, pool canonic + splice post-migrare, conservative/midpoint/optimistic, land5, cost125, CHAIN_BREAK/GAP/UNAVAILABLE, maturizare >= 960 s)."""
import os,sys,json,gzip,glob,hashlib,base64,struct,collections,zlib,time,tempfile
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0,os.path.join(ROOT,"research","curve2x_v3_reclaim")); sys.path.insert(0,os.path.join(ROOT,"strategy_e"))
import v3_lib as V; L=V.L; from watcher_v3 import Stream,Mint; import pda
PAMM="pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"; PUMPFUN="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"; WSOL_B=pda.b58d("So11111111111111111111111111111111111111112"); MATURITY_S=960; GAP_JUMP_S=120
def sha_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
def sha_obj(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":"),default=float).encode()).hexdigest()
def atomic_write(path,text):
    d=os.path.dirname(path); fd,tmp=tempfile.mkstemp(dir=d,prefix=".tmp_",suffix=".part")
    with os.fdopen(fd,"w") as f: f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path); dfd=os.open(d,os.O_RDONLY); os.fsync(dfd); os.close(dfd)
def spec_sha(spec): return hashlib.sha256(json.dumps({k:v for k,v in spec.items() if k!="spec_sha256"},sort_keys=True,indent=1).encode()).hexdigest()
def load_spec(path):
    spec=json.load(open(path)); h=spec_sha(spec)
    if h!=spec.get("spec_sha256"): raise SystemExit(f"FORWARD_SPEC_SHA_MISMATCH recalculat {h[:16]} != declarat {str(spec.get('spec_sha256'))[:16]}")
    return spec
# ---- serializarea starii Stream ----
def stream_dump(E):
    M={}
    for k,m in E.M.items(): M[k]={s:getattr(m,s) for s in Mint.__slots__}
    return dict(M=M,wal={u:list(d) for u,d in E.wal.items()},decisions=list(E.decisions),last_prune=E.last_prune)
def stream_load(d):
    E=Stream(); E.last_prune=d["last_prune"]; E.decisions=list(d["decisions"])
    for k,v in d["M"].items():
        m=Mint(v["creator"],v["create_ts"])
        for s in Mint.__slots__: setattr(m,s,v[s])
        m.T=[tuple(t) for t in m.T]; m.trough=tuple(m.trough) if m.trough else None; E.M[k]=m
    for u,lst in d["wal"].items(): E.wal[u]=collections.deque(tuple(x) for x in lst)
    return E
class ForwardState:
    """stare persistata atomic: seq, decided, files_done {nume: sha256}, stream, clock; state_hash pentru integritate."""
    def __init__(self,path): self.path=path; self.seq=0; self.decided=set(); self.files_done={}; self.stream=Stream(); self.clock=0; self.last_file=None
    def save(self):
        payload=dict(seq=self.seq,decided=sorted(self.decided),files_done=self.files_done,stream=stream_dump(self.stream),clock=self.clock,last_file=self.last_file); payload["state_hash"]=sha_obj({k:v for k,v in payload.items()}); atomic_write(self.path,json.dumps(payload,default=float))
    @classmethod
    def load(cls,path):
        st=cls(path)
        if not os.path.exists(path): return st
        p=json.load(open(path)); h=p.pop("state_hash",None)
        if sha_obj(p)!=h: raise SystemExit("FORWARD_STATE_INTEGRITY_FAILED (state_hash)")
        st.seq=p["seq"]; st.decided=set(p["decided"]); st.files_done=p["files_done"]; st.stream=stream_load(p["stream"]); st.clock=p["clock"]; st.last_file=p.get("last_file"); return st
    def verify_files(self,source):
        bad=[]
        for fn,h in self.files_done.items():
            p=os.path.join(source,fn)
            if not os.path.exists(p) or sha_file(p)!=h: bad.append(fn)
        return bad
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
def decode_pamm(raw):
    ts,=struct.unpack_from("<q",raw,8); amt,mx,ub,uq,rb,rq,q2=struct.unpack_from("<QQQQQQQ",raw,16); lpbp,lpf,prbp,prf,q3,uq2=struct.unpack_from("<QQQQQQ",raw,72); return ts,amt,rb,rq,q2,lpbp,lpf,prbp,prf,q3,uq2
# ---- labeler prospectiv: reconstruieste din fisierele forward procesate ----
def label_forward(journal_path,outcomes_path,source,files_done,clock):
    """eticheteaza predictiile maturizate (decision_time + MATURITY_S <= clock) din fisierele procesate (hash verificat). Nu foloseste nimic in afara fisierelor forward."""
    done=set()
    if os.path.exists(outcomes_path):
        for l in open(outcomes_path): done.add(json.loads(l)["prediction_id"])
    pend=[json.loads(l) for l in open(journal_path)] if os.path.exists(journal_path) else []; pend=[p for p in pend if p["prediction_id"] not in done and p["decision_time"]+MATURITY_S<=clock]
    if not pend: return 0
    mints={p["mint"] for p in pend}; R={}; pools={}; POOLS={}; creates=[]; seq=0
    for fn in sorted(files_done):
        for line in readlines(os.path.join(source,fn)):
            if '"src":"pump"' in line:
                r=json.loads(line); t=int(r["t"]); slot=r["slot"]
                for k,e in enumerate(r["events"]):
                    ev=e.get("ev")
                    if ev=="CreateEvent":
                        creates.append(t)
                        if e.get("mint") in mints and e["mint"] not in R: R[e["mint"]]=dict(mint=e["mint"],creator=e["user"],create_ts=t,trades=[],complete_ts=None,complete_slot=None,complete_seq=None,pool=None)
                    elif ev=="TradeEvent":
                        v=R.get(e.get("mint"))
                        if v is not None: v["trades"].append([e.get("ts") or t,slot,seq,k,e["user"],e["sol"],e["tok"],1 if e["is_buy"] else 0,e["rsol"],e["rtok"],e["vsol"],e["vtok"]])
                    elif ev=="CompleteEvent":
                        v=R.get(e.get("mint"))
                        if v is not None and v["complete_ts"] is None: v["complete_ts"]=int(next((x.get("ts") for x in r["events"] if x.get("ev")=="TradeEvent" and x.get("mint")==e["mint"] and x.get("ts")),t)); v["complete_slot"]=slot; v["complete_seq"]=seq
                seq+=1
            elif '"src":"pamm"' in line:
                if 'CreatePoolEvent' in line:
                    r=json.loads(line)
                    for k,e in enumerate(r["events"]):
                        if e.get("ev")!="CreatePoolEvent": continue
                        raw=base64.b64decode(e["raw"]); ts,=struct.unpack_from("<q",raw,8); idx,=struct.unpack_from("<H",raw,16); creator=raw[18:50]; bm=pda.b58e(raw[50:82]); qm=raw[82:114]; base_in,quote_in,pool_base,pool_quote=struct.unpack_from("<QQQQ",raw,116); pool_b=raw[173:205]; v=R.get(bm)
                        if v is None or v["pool"] is not None: continue
                        auth=pda.find_pda([b"pool-authority",pda.b58d(bm)],pda.b58d(PUMPFUN))[0]; v["pool"]=dict(pool=pda.b58e(pool_b),index=idx,canonical=bool(idx==0 and pda.b58e(creator)==auth),quote_wsol=bool(qm==WSOL_B),cp_ts=ts,cp_slot=r["slot"],cp_seq=seq,pool_base=pool_base,pool_quote=pool_quote,events=[]); POOLS[pool_b]=bm
                    seq+=1
                elif POOLS and ('BuyEvent' in line or 'SellEvent' in line):
                    r=json.loads(line)
                    for k,e in enumerate(r["events"]):
                        if e.get("ev") not in ("BuyEvent","SellEvent"): continue
                        raw=base64.b64decode(e["raw"]); m=POOLS.get(raw[120:152])
                        if m is None: continue
                        ts,amt,rb,rq,q2,lpbp,lpf,prbp,prf,q3,uq2=decode_pamm(raw)
                        if e["ev"]=="BuyEvent": rb_post=rb-amt; rq_post=rq+q3; cp_q=q3-lpf; gross=max(q2,uq2); cce=max(0,round((gross-cp_q-lpf-prf)*10000/cp_q)) if cp_q>0 else 0
                        else: rb_post=rb+amt; rq_post=rq-q3; cp_q=q3+lpf; net=min(q2,uq2); cce=max(0,round((cp_q-lpf-prf-net)*10000/cp_q)) if cp_q>0 else 0
                        R[m]["pool"]["events"].append([ts,r["slot"],seq,k,1 if e["ev"]=="BuyEvent" else 0,rb,rq,rb_post,rq_post,amt,cp_q,lpbp,prbp,cce])
                    seq+=1
                else: seq+=1
            else: seq+=1
    gaps=[]; prev=None
    for t in creates:
        if prev is not None and t-prev>GAP_JUMP_S: gaps.append((prev,t))
        prev=t
    out=open(outcomes_path,"a"); n=0
    for p in pend:
        rec=R.get(p["mint"]); o=dict(prediction_id=p["prediction_id"],mint_hash=p["mint_hash"],model_role=p["model_role"],labeled_at_clock=clock,maturity_s=MATURITY_S,source="FORWARD_FILES_ONLY")
        if rec is None or len(rec["trades"])<=p["dec_i"]: o.update(state=None,label_quality="NO_RECORD")
        else:
            # verificam ca decizia jurnalizata corespunde trade-ului reconstruit (slot)
            if rec["trades"][p["dec_i"]][1]!=p["decision_slot"]: o.update(state=None,label_quality="DECISION_MISMATCH")
            else:
                pool=L.pool_prepare(rec["pool"]) if rec["pool"] else None; hz=p["decision_time"]+V.H_PRIMARY; gap=any(not (e<=p["decision_time"] or s>=hz) for s,e in gaps)
                b=V.simulate_v3_bounds(rec,p["dec_i"],p["decision_time"],pool=pool); b5=V.simulate_v3_bounds(rec,p["dec_i"],p["decision_time"],pool=pool,land=V.LAND_STRESS); bc=V.simulate_v3_bounds(rec,p["dec_i"],p["decision_time"],pool=pool,cost_mult=V.COST_STRESS); s=V.simulate_v3(rec,p["dec_i"],p["decision_time"],pool=pool)
                if b.get("status")!="OK": o.update(state=None,label_quality=b.get("status"))
                elif b.get("unavailable"): o.update(state=None,label_quality="UNAVAILABLE",splice_quality="CROSS_MIGRATION_LABEL_UNAVAILABLE")
                else:
                    o.update(state=b["conservative"]["state"],state_midpoint=b["midpoint"]["state"],state_optimistic=b["optimistic"]["state"],realized_net_pnl_conservative=b["conservative"]["pnl"],realized_net_pnl_midpoint=b["midpoint"]["pnl"],realized_net_pnl_optimistic=b["optimistic"]["pnl"],realized_net_pnl=b["conservative"]["pnl"],
                      realized_net_pnl_land5=(b5["conservative"]["pnl"] if b5.get("status")=="OK" and not b5.get("unavailable") else None),realized_net_pnl_cost125=(bc["conservative"]["pnl"] if bc.get("status")=="OK" and not bc.get("unavailable") else None),execution_venue=b["conservative"]["venue"],exit_slot=None,n_entry_positions=b["n_entry_positions"],
                      label_quality=("GAP" if gap else "OK"),splice_quality=(s["15M"]["label_kind"] if s.get("status")=="OK" else s.get("status")),migrated_in_window=b["migrated_in_window"])
        out.write(json.dumps(o,default=float)+"\n"); n+=1
    out.close(); return n
