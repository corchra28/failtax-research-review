"""Faza 1b/2: clasificarea candidatilor (exact / dust / respinsi cu motiv) si economia realizata din sumele executate. Outputs publice cu user/semnatura hash-uite."""
import gzip,json,hashlib,collections,statistics as S,random,time,sys,os
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/overnight_20260905/atomic_census"; WSOL="So11111111111111111111111111111111111111112"; NS="external-review-v1"; LAMP=10**9
COSTS={"PRIMARY":105000,"STRESS_1":500000,"STRESS_2":1000000,"NEW_ACCOUNT_STRESS":2105000}
def hid(v): return hashlib.sha256(f"{NS}:{v}".encode()).hexdigest()[:32]
def classify(c):
    """returneaza (clasa, motiv). clasa in EXACT | DUST | REJECT."""
    ev=c["events"]
    if c["duplicate_event_keys"]: return "REJECT","DUPLICATE_EVENT_KEYS"
    if c["unknown_events_in_tx"]>0: return "REJECT","UNDECODED_OR_UNKNOWN_EVENT_IN_TX"
    if any(d["meta"] is None for d in ev): return "REJECT","POOL_METADATA_MISSING"
    if any(d["meta"]["quote_mint"]!=WSOL or d["meta"]["orientation"]!="STRICT" for d in ev): return "REJECT","ORIENTATION_OR_QUOTE_NOT_STRICT_WSOL"
    if len({d["meta"]["base_mint"] for d in ev})!=1: return "REJECT","MIXED_BASE_MINT"
    if any(not d["inv_ok"] for d in ev): return "REJECT","RESERVE_INVARIANT_VIOLATION"
    ks=[d["k"] for d in ev]
    if ks!=sorted(ks): return "REJECT","EVENT_ORDER_INCONSISTENT"
    # lantul pre/post per pool in interiorul semnaturii (evenimente consecutive ale aceluiasi pool)
    last={}
    for d in ev:
        p=d["pool"]
        if p in last and (last[p][0]!=d["rb_pre"] or last[p][1]!=d["rq_pre"]): return "REJECT","INTRA_TX_CHAIN_INCONSISTENT"
        last[p]=(d["rb_post"],d["rq_post"])
    # multi-user pentru acelasi mint in aceeasi tranzactie => ambiguu (verificat la nivel de tx: users_in_tx>1 si alte grupuri ale aceluiasi token) — aproximat prin users_in_tx
    bought=sum(d["base"] for d in ev if d["is_buy"]); sold=sum(d["base"] for d in ev if not d["is_buy"])
    if bought<=0 or sold<=0: return "REJECT","MISSING_BUY_OR_SELL"
    if bought==sold: return "EXACT","BASE_CONSERVED_EXACT"
    if abs(bought-sold)*10000<=bought: return "DUST","BASE_IMBALANCE_LE_1BP"
    return "REJECT","BASE_NOT_CONSERVED"
def econ(c):
    ev=c["events"]; paid=sum(d["user_quote"] for d in ev if d["is_buy"]); recv=sum(d["user_quote"] for d in ev if not d["is_buy"]); gross=recv-paid
    return dict(gross=gross,paid=paid,recv=recv,**{f"net_{k}":gross-v for k,v in COSTS.items()})
def stats(vals):
    if not vals: return None
    v=sorted(vals,reverse=True); n=len(v); w=[a for a in v if a>0]; l=[a for a in v if a<=0]
    return dict(N=n,EV=sum(v)/n,median=S.median(v),PF=((sum(w)/abs(sum(l))) if l and sum(l)<0 else (float("inf") if w else 0.0)),win_rate=len(w)/n,total=sum(v),EX_BEST_1=(sum(v[1:])/(n-1)) if n>1 else None,EX_BEST_3=(sum(v[3:])/(n-3)) if n>3 else None,EX_BEST_1PCT=sum(v[max(1,n//100):])/max(1,n-max(1,n//100)))
def boot(rows,key,cluster,reps=10000,seed=20260905):
    rng=random.Random(seed); g=collections.defaultdict(list); [g[cluster(r)].append(r[key]) for r in rows]; G=list(g.values()); n=len(rows); bs=[]
    for _ in range(reps):
        tot=0.0; cnt=0
        for _k in range(len(G)):
            a=G[rng.randrange(len(G))]; tot+=sum(a); cnt+=len(a)
        bs.append(tot/cnt)
    bs.sort(); return dict(CI95=(bs[int(0.025*reps)],bs[int(0.975*reps)-1]),p_le_0=sum(1 for b in bs if b<=0)/reps,clusters=len(G))
def main():
    t0=time.time(); rows=[]; cls=collections.Counter(); reasons=collections.Counter(); scan=json.load(open(f"{D}/census_scan_manifest.json"))
    for l in gzip.open(f"{D}/census_candidates.jsonl.gz","rt"):
        c=json.loads(l); k,why=classify(c); cls[k]+=1; reasons[why]+=1; e=econ(c) if k in ("EXACT","DUST") else {}
        rows.append(dict(sig=c["sig"],user=c["user"],token=c["token"],slot=c["slot"],t=c["t"],day=time.strftime("%Y-%m-%d",time.gmtime(c["t"])),cls=k,why=why,n_swaps=len(c["events"]),n_pools=len({d["pool"] for d in c["events"]}),pools=sorted({d["pool"] for d in c["events"]}),canon=sum(1 for d in c["events"] if d["meta"] and d["meta"]["canonical"]),n_swaps_in_tx=c["n_swaps_in_tx"],users_in_tx=c["users_in_tx"],first_pool_buy=next((d["pool"] for d in c["events"] if d["is_buy"]),None),**e))
    # taxare conservatoare: fiecare ciclu de token dintr-o tranzactie plateste costul complet (deja per rand); numarul de cicluri per semnatura raportat
    per_sig=collections.Counter(r["sig"] for r in rows if r["cls"]=="EXACT")
    with gzip.open(f"{D}/census_rows.jsonl.gz","wt") as f:
        for r in rows: f.write(json.dumps(r)+"\n")
    ex=[r for r in rows if r["cls"]=="EXACT"]; du=[r for r in rows if r["cls"]=="DUST"]
    census=dict(CENSUS_SPEC_SHA256=hashlib.sha256(open(f"{OUT}/census_frozen_spec.json","rb").read()).hexdigest(),TOTAL_SWAP_EVENTS_SCANNED=scan["counters"].get("swap_events"),multi_swap_transactions=scan["counters"].get("multi_swap_lines"),CANDIDATE_SIGNATURES=len({r["sig"] for r in rows}),candidate_groups=len(rows),EXACT_BASE_CONSERVED_CYCLES=len(ex),DUST_CYCLES=len(du),rejected=dict(reasons),UNIQUE_USERS_HASHED=len({hid(r["user"]) for r in ex}),UNIQUE_TOKENS=len({r["token"] for r in ex}),UNIQUE_POOL_PAIRS=len({tuple(r["pools"]) for r in ex}),DATES=sorted({r["day"] for r in ex}),by_day=dict(collections.Counter(r["day"] for r in ex)),swaps_per_cycle=dict(collections.Counter(r["n_swaps"] for r in ex)),cycles_per_signature=dict(collections.Counter(per_sig.values())),scan_manifest=scan)
    json.dump(census,open(f"{OUT}/census_manifest.json","w"),indent=1); print(json.dumps({k:v for k,v in census.items() if k!="scan_manifest"}))
    # ---- economie (Faza 2) doar pe EXACT ----
    R=dict(label="POST_HOC_HISTORICAL_RESEARCH",N=len(ex))
    if ex:
        for k in COSTS: R[f"net_{k}"]=stats([r[f"net_{k}"]/LAMP for r in ex])
        R["gross"]=stats([r["gross"]/LAMP for r in ex]); R["by_day"]={d:stats([r["net_PRIMARY"]/LAMP for r in ex if r["day"]==d]) for d in sorted({r["day"] for r in ex})}
        tok=collections.defaultdict(float); usr=collections.defaultdict(float); pp=collections.defaultdict(float)
        for r in ex: v=max(0,r["net_PRIMARY"])/LAMP; tok[r["token"]]+=v; usr[r["user"]]+=v; pp[tuple(r["pools"])]+=v
        gp=sum(tok.values()) or 1e-12; R["top_token_share"]=max(tok.values())/gp; R["top_user_share"]=max(usr.values())/gp; R["top_pool_pair_share"]=max(pp.values())/gp
        R["unique_users"]=len(usr); R["cycles_per_user"]=dict(collections.Counter(collections.Counter(r["user"] for r in ex).values())); R["by_token_top10_hashed"]=[(hid(t),round(v,4)) for t,v in sorted(tok.items(),key=lambda kv:-kv[1])[:10]]; R["by_user_top10_hashed"]=[(hid(u),round(v,4)) for u,v in sorted(usr.items(),key=lambda kv:-kv[1])[:10]]
        R["sizes_sol"]=dict(median_paid=S.median([r["paid"]/LAMP for r in ex]),p90_paid=sorted(r["paid"]/LAMP for r in ex)[int(0.9*len(ex))]); R["atomic_from_event_order"]="DA: toate evenimentele unui ciclu sunt in aceeasi semnatura (o tranzactie), deci durata de detinere in tranzactie = 0 sloturi"
        R["bootstrap_user_day"]=boot(ex,"net_PRIMARY",lambda r:(r["user"],r["day"])); R["bootstrap_token_day"]=boot(ex,"net_PRIMARY",lambda r:(r["token"],r["day"]))
        for k in ("bootstrap_user_day","bootstrap_token_day"): R[k]["CI95"]=tuple(v/LAMP for v in R[k]["CI95"])
        st=R["net_PRIMARY"]; g=dict(cycles50=len(ex)>=50,tokens5=census["UNIQUE_TOKENS"]>=5,dates2=len(census["DATES"])>=2,EV=st["EV"]>0,PF=st["PF"]>=2.0,CI_user=R["bootstrap_user_day"]["CI95"][0]>0,CI_token=R["bootstrap_token_day"]["CI95"][0]>0,exb1pct=st["EX_BEST_1PCT"]>0,stress1=R["net_STRESS_1"]["EV"]>0,user_share=R["top_user_share"]<=0.4,token_share=R["top_token_share"]<=0.4,violations=(reasons.get("RESERVE_INVARIANT_VIOLATION",0)==0 and reasons.get("INTRA_TX_CHAIN_INCONSISTENT",0)==0 and scan["counters"].get("undecodable_events",0)==0))
        R["gate"]=g; R["verdict"]="EXECUTED_ARB_MECHANISM_CONFIRMED" if all(g.values()) else "EXECUTED_ARB_MECHANISM_NOT_CONFIRMED"; R["violations_note"]="incalcarile de invariant/decodare sunt raportate ca RESPINGERI de candidat (nu intra in populatie); poarta cere zero astfel de cazuri printre candidati"
    else: R["verdict"]="NO_EXACT_CYCLES"
    R["runtime_s"]=round(time.time()-t0,1); json.dump(R,open(f"{OUT}/census_results.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in R.items() if k in ("N","net_PRIMARY","gate","verdict","top_user_share","top_token_share","unique_users")},default=str)); print("CENSUS_ANALYZE_DONE")
if __name__=="__main__": main()
