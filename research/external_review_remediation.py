"""REMEDIERE DUPA REVIZUIREA EXTERNA: (A) taxa zero la intrare in pool_outcomes h=5 (prospectiv), (B) fee resolver corect + teste, (C) audit de timing entry_ts >= pool_creation_ts,
(D) contaminarea rezultatelor REGIME (raportata, NU recalculata in fisierele existente). Nu modifica niciun artefact anterior."""
import gzip,json,csv,hashlib,collections,statistics as S,sys,os,math
sys.path.insert(0,'.'); import pumpswap_fees as PF
sys.path.insert(0,'research'); import regime_gate as RG
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; B="research/external_review_bundle"; NS="external-review-v1"; SUPPLY=10**15
def hid(a): return hashlib.sha256(f"{NS}:{a}".encode()).hexdigest()[:32] if a else ""
inv=json.load(gzip.open(f"{D}/pamm_pool_inventory.json.gz","rt")); POOLS=inv["pools"]; STATS=inv["stats"]
# ---------------- fee resolver ----------------
def resolve_fee(pool_addr,rb,rq,vq):
    """(lp_bp, protocol_bp, creator_bp) intregi. Canonical: tabel de tiere dupa mcap (fractiile rotunjite in sus, conservator). Noncanonical: 25/5/0 = 30 bps. Pool necunoscut in inventar: None."""
    m=POOLS.get(pool_addr)
    if m is None: return None
    if m["canonical"]:
        f=PF.fees_for(rb,rq,vq,SUPPLY); return int(f["lp_bp"]),int(math.ceil(f["protocol_bp"])),int(math.ceil(f["creator_bp"]))
    return 25,5,0
R={}
# B. teste resolver
tests={}
# tier boundaries: total > 0 si monoton descrescator in mcap
tot=[]
for floor_,cr,pr,lp in PF.TIERS: tot.append(cr+pr+lp)
tests["tier_totals_bps"]=tot; tests["tier_total_range"]=[min(tot),max(tot)]; tests["tier_monotone_nonincreasing"]=all(a>=b for a,b in zip(tot,tot[1:])); tests["all_tiers_positive"]=all(t>0 for t in tot)
# comparatie cu swap-uri observate (bps din evenimente, cache-ul regimului = pool-uri canonice prospective)
obs_match=obs_mis=0; mis_examples=[]; zero_fee_events=0; zero_fee_first_event=0; nonc_obs=collections.Counter(); n_states=0; n_fee_pos=0
with gzip.open(f"{D}/regime_pools.jsonl.gz","rt") as f:
    for l in f:
        x=json.loads(l)
        if x["source"]!="PROSPECTIVE_TAPE_EVENTS": continue
        m=POOLS.get(x["pool"])
        for i,e in enumerate(x["ev"]):
            if obs_match+obs_mis>=200000: break
            lp,pr,cc=e[12],e[13],e[14]
            if lp==0 and pr==0: zero_fee_events+=1; zero_fee_first_event+=(i==0); continue
            r=resolve_fee(x["pool"],e[6],e[7],x["vq"]); n_states+=1
            if r is None: continue
            if sum(r)>0: n_fee_pos+=1
            if (r[0],r[1])==(lp,pr) and abs(r[2]-cc)<=1: obs_match+=1
            else:
                obs_mis+=1
                if len(mis_examples)<12: mis_examples.append(dict(pool=hid(x["pool"]),i=i,observed=(lp,pr,cc),resolver=r,mcap_sol=PF.mcap_sol(e[6],e[7],x["vq"],SUPPLY)))
tests["observed_swaps_compared"]=obs_match+obs_mis; tests["observed_match"]=obs_match; tests["observed_mismatch"]=obs_mis; tests["mismatch_examples"]=mis_examples; tests["zero_fee_events_seen"]=zero_fee_events; tests["zero_fee_as_first_event_of_pool"]=zero_fee_first_event
tests["canonical_fee_total_positive_for_all_states"]=(n_fee_pos==n_states); 
# noncanonical: bps observate in pool-urile noncanonice din inventar
for p,m in POOLS.items():
    if not m["canonical"] and p in STATS:
        for k,v in STATS[p]["bps"].items(): nonc_obs[k]+=v
tests["noncanonical_observed_bps_hist_top"]=nonc_obs.most_common(8); tests["noncanonical_resolver_total"]=30
# A. pool_outcomes h=5
pm={}
with gzip.open(f"{B}/pool_master.csv.gz","rt") as f:
    for r in csv.DictReader(f): pm[r["pool_id"]]=r
zero_rows=[]; tot_rows=0; fee_dist=collections.Counter()
with gzip.open(f"{B}/pool_outcomes.csv.gz","rt") as f:
    for r in csv.DictReader(f):
        if r["horizon_s"]!="5": continue
        src=pm.get(r["pool_id"],{}).get("source","")
        if src!="PROSPECTIVE_TAPE_EVENTS": continue
        tot_rows+=1
        if r.get("OUT_TP100_SL30_300_entry_fee_bps")=="0": zero_rows.append(r)
R["A_pool_outcomes_h5"]=dict(prospective_rows=tot_rows,entry_fee_zero_rows=len(zero_rows),share=len(zero_rows)/max(1,tot_rows))
# recalculare corecta pe randurile afectate (doar diagnostic; artefactele existente nu se modifica)
cache={}
with gzip.open(f"{D}/regime_pools.jsonl.gz","rt") as f:
    for l in f: x=json.loads(l); x["_ts"]=[e[1] for e in x["ev"]]; cache[hid(x["pool"])]=x
def sim_fixed(x,X,tp_m=2.0,sl_m=0.70,to=300,N=25.0):
    """TP100/SL30 cu taxele din resolver la fiecare stare (nu bps-urile evenimentului)."""
    vq=x["vq"]; ev=x["ev"]; rb,rq,_,_,_,i=RG.state_at(x,X); fee=resolve_fee(x["pool"],rb,rq,vq)
    if fee is None: return None
    q=int(N/100*1e9); tok,qn=RG.exec_buy(rb,rq,vq,q,*fee)
    if tok<=0: return None
    deadline=X+to; j=i+1; out=None
    def liq(e): rb2=e[8]-tok; rq2=e[9]+qn; fe=resolve_fee(x["pool"],rb2,rq2,vq); return (RG.exec_sell(rb2,rq2,vq,tok,*fe)/1e9*100) if rb2>0 else 0.0
    while j<len(ev) and ev[j][1]<=deadline:
        sl_=ev[j][2]; k=j
        while k+1<len(ev) and ev[k+1][2]==sl_ and ev[k+1][1]<=deadline: k+=1
        V=liq(ev[k])
        if V<=N*sl_m: out=V; break
        if V>=N*tp_m: out=V; break
        j=k+1
    if out is None:
        rb3,rq3,_,_,_,i3=RG.state_at(x,deadline); rb2=(rb3 if i3>=0 else rb)-tok; rq2=(rq3 if i3>=0 else rq)+qn; fe=resolve_fee(x["pool"],rb2,rq2,vq); out=(RG.exec_sell(rb2,rq2,vq,tok,*fe)/1e9*100) if rb2>0 else 0.0
    return out-N-0.02,sum(fee)
old=[]; new=[]; fee_dist=collections.Counter()
for r in zero_rows:
    x=cache.get(r["pool_id"])
    if not x: continue
    o=float(r["OUT_TP100_SL30_300_pnl_usd"]); res=sim_fixed(x,float(r["outcome_entry_ts"]))
    if res is None: continue
    old.append(o); new.append(res[0]); fee_dist[res[1]]+=1
R["A_pool_outcomes_h5"].update(dict(rows_recomputed=len(old),old_pnl_sum=sum(old),old_pnl_mean=(S.mean(old) if old else None),corrected_pnl_sum=sum(new),corrected_pnl_mean=(S.mean(new) if new else None),estimated_pnl_impact_sum=sum(new)-sum(old),correct_fee_total_bps_distribution=dict(fee_dist)))
# C. timing audit pe shadow ledger
viol=[]; n_sh=0
with gzip.open(f"{B}/shadow_trade_ledger.csv.gz","rt") as f:
    for r in csv.DictReader(f):
        n_sh+=1; pc=pm.get(r["pool_id"],{}).get("pool_creation_ts")
        if pc and float(r["shadow_entry_ts"])<float(pc): viol.append(dict(pool_id=r["pool_id"],shadow_entry_ts=float(r["shadow_entry_ts"]),pool_creation_ts=float(pc),delta_s=float(pc)-float(r["shadow_entry_ts"]),date=r["date_utc"]))
R["C_timing"]=dict(shadows=n_sh,pre_creation_entries=len(viol),violations=viol[:50],by_date=dict(collections.Counter(v["date"] for v in viol)),rule="entry_ts >= pool_creation_ts; incalcarile trebuie EXCLUSE, nu mutate")
# D. contaminarea REGIME: shadow-uri cu taxa zero la intrare
zero_sh=0; tot_sh=0; deltas=[]; on_affected=0
blocks=json.load(open(f"{D}/regime_blocks.json")); on_mints={b.get("selected_mint") for b in blocks if b["ON"] and b.get("selected_mint")}
for hp,x in cache.items():
    if x["source"]!="PROSPECTIVE_TAPE_EVENTS": continue
    tot_sh+=1; X=x["complete_ts"]+7; rb,rq,lp,pr,cc,i=RG.state_at(x,X)
    if lp==0 and pr==0:
        zero_sh+=1; s=RG.shadow(x); res=sim_fixed(x,X)
        if s and res: deltas.append(res[0]-s["pnl"])
        if x["mint"] in on_mints: on_affected+=1
R["D_regime_contamination"]=dict(prospective_shadows=tot_sh,entry_fee_zero_shadows=zero_sh,share=zero_sh/max(1,tot_sh),mean_pnl_delta_usd=(S.mean(deltas) if deltas else None),sum_pnl_delta_usd=sum(deltas),ON_trades_affected=on_affected,note="raportat doar; regime_gate_results.json NU a fost recalculat; incalcarile de timing (C) trebuie excluse intr-o reevaluare separata")
R["B_fee_resolver_tests"]=tests; R["overlay_limitation"]="Overlay-ul static (rezerve viitoare observate + pozitia proprie) NU este un counterfactual protocol-exact pentru strategiile directionale: tranzactiile ulterioare ale altora s-ar fi executat pe starea modificata de pozitia noastra (preturi/impact diferite) si unele nu s-ar fi produs deloc. Arbitrajul atomic nu are aceasta problema: ambele leg-uri se evalueaza consecutiv pe starea de landing."
R["FEE_RESOLVER_VALID"]=bool(tests["all_tiers_positive"] and tests["canonical_fee_total_positive_for_all_states"] and tests["observed_swaps_compared"]>=1000 and tests["observed_match"]/max(1,tests["observed_swaps_compared"])>=0.95)
json.dump(R,open("research/external_review_remediation.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in R.items() if k!="B_fee_resolver_tests"},default=str)[:1500]); print("tests",{k:v for k,v in tests.items() if k!="mismatch_examples"}); print("REMEDIATION_DONE")
