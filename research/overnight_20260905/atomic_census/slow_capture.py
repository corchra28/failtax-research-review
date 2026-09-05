"""Faza 5: SLOW_CAPTURE_OF_EXECUTED_ARB_V1 pe spec-ul inghetat; foloseste motorul V2 (run_engine) pe populatia inghetata (PRIMARY_MEME + SECONDARY), fara recensamant in selectie. Faza 6: half-life descriptiv."""
import gzip,json,hashlib,collections,statistics as S,random,time,sys,copy,bisect
sys.path.insert(0,'research'); import atomic_same_mint_arb as A
D=A.D; OUT="research/overnight_20260905/atomic_census"; LAMP=10**9
spec=json.load(open(f"{OUT}/slow_capture_frozen_spec.json")); Pp=json.load(open(A.POPFILE)); meta=A.load_rpc_meta(); E=A.load_pass2(); OUT_W=A.outages(); TR=A.truncated_tails()
pop={}
for k in ("PRIMARY_MEME","SECONDARY_ALL_NONCANONICAL"):
    for t,v in Pp[k]["tokens"].items(): pop.setdefault(t,[]); pop[t]=sorted(set(pop[t])|set(v["pools"]))
# motorul V2 exclude pool-urile canonice din populatia SECONDARY; pentru acest studiu general permitem canonical+noncanonical marcand meta canonical=False? NU — pastram semantica: rulam run_engine per token cu meta reala, iar perechile cu canonical necesita tier demonstrat (event_tier_at) sau supply validat; canonical fara supply => rute excluse automat (resolve_fee None)
espec=dict(status="FROZEN_NOT_EXECUTED",notional_sol=0.25,landing=dict(primary_slots=3,stress_slots=5),costs=dict(base_signature_fee_lamports=5000,priority_fee_lamports=100000),gates=dict(episodes_min=50,tokens_min=5,PF_min=1.5,positive_days_min=2,token_share_max=0.4))
m2={p:dict(v) for p,v in meta.items()}
for p in m2: m2[p]["canonical"]=False if not m2[p]["canonical"] else True
pools_loaded=sum(len(v) for v in pop.values()); pools_with_events=sum(1 for v in pop.values() for p in v if p in E and E[p]); pools_noncanonical_strict=sum(1 for v in pop.values() for p in v if p in E and E[p] and not m2[p]["canonical"] and m2[p]["orientation"]=="STRICT")
res=A.run_engine(pop,m2,E,espec,OUT_W=OUT_W,TR=TR); ev=A.evaluate_slow_arb(res["rows"],espec)
tokens_2plus_eligible=len(pop)-res["violations"].get("TOKEN_WITHOUT_2_ELIGIBLE_POOLS",0)
ev["population_actually_evaluated"]=dict(pools_listed_in_frozen_populations=pools_loaded,pools_with_pass2_events=pools_with_events,pools_noncanonical_strict_eligible=pools_noncanonical_strict,canonical_pools_excluded_by_engine=res["violations"].get("CANONICAL_POOL_IN_SECONDARY_POPULATION",0),tokens_listed=len(pop),tokens_with_2plus_eligible_pools=tokens_2plus_eligible,note="motorul V2 (run_engine) exclude neconditionat pool-urile canonice => PRIMARY_MEME (canonical+noncanonical) NU a fost evaluat; rezultatul este o evaluare SECONDARY/NONCANONICAL")
viol=res["violations"]; tp_unverified=True
ev["token_program"]="UNVERIFIED (fara RPC) => incalcare de semantica pentru poarta"; g=ev.get("gate")
def reserve_gate_ok(viol):
    """poarta de integritate a rezervelor: ZERO incalcari (rupturi de lant intre decizie si landing, stari de landing neprobabile, stari in outage/trunchiere). Fara scurtcircuit."""
    return all(viol.get(k,0)==0 for k in ("CHAIN_BREAK_DECISION_TO_LANDING","LANDING_STATE_NOT_PROVABLE","STATE_IN_OUTAGE_OR_TRUNCATION"))
if g is not None: g["transaction_semantics_violations_zero"]=(not tp_unverified) and viol.get("ORIENTATION_VIOLATION",0)==0; g["reserve_integrity_violations_zero"]=reserve_gate_ok(viol)
ev["verdict"]="SLOW_CAPTURE_HISTORICAL_PAPER_CANDIDATE" if (g and all(g.values())) else "SLOW_CAPTURE_NO_VERIFIED_EDGE"
rows=res["rows"]; port=[r for r in rows if r["in_portfolio"]]
out=dict(spec_sha256=hashlib.sha256(open(f"{OUT}/slow_capture_frozen_spec.json","rb").read()).hexdigest(),population=dict(tokens=len(pop),pools=sum(len(v) for v in pop.values())),engine=dict(episodes=res["episodes"],rows=len(rows),portfolio=len(port),violations=viol,selector_calls=res["selector_calls"]),evaluation=ev,by_token_hashed=dict(collections.Counter(hashlib.sha256(("external-review-v1:"+r["token"]).encode()).hexdigest()[:16] for r in port)),statuses=dict(collections.Counter(r["landing_primary_status"] for r in port)),predicted_vs_realized=dict(pred_EV=(S.mean([r["predicted_net_sol"] for r in port]) if port else None),real_EV=(S.mean([r["realized_primary_sol"] for r in port]) if port else None)))
json.dump(out,open(f"{OUT}/slow_capture_results_v2.json","w"),indent=1,default=str)
# ---- Faza 6: half-life descriptiv al starilor profitabile detectate (predicted > 0), la +1,+2,+3,+5,+8 sloturi, worst-of pre/post ----
H=[1,2,3,5,8]; surv=collections.Counter(); prof={h:[] for h in H}; comp=[]; lifetimes=[]; n_states=0
cens=set()
try:
    for l in gzip.open(f"{D}/census_rows.jsonl.gz","rt"):
        c=json.loads(l)
        if c["cls"]=="EXACT": cens.add(c["sig"])
except Exception: pass
Q=int(0.25*LAMP); FEE=105000
for tok,pools in pop.items():
    ok=[p for p in pools if p in E and E[p] and m2.get(p) and m2[p]["orientation"]=="STRICT"]
    if len(ok)<2: continue
    routes=[(a,b) for a in ok for b in ok if a!=b]; slots=sorted({e[2] for p in ok for e in E[p]})
    for s in slots:
        best=None
        for a,b in routes:
            sa=A.state_provable(E[a],s); sb=A.state_provable(E[b],s)
            if not sa or not sb: continue
            va=A.implied_vq(E[a][:sa[2]+1])[0]; vb=A.implied_vq(E[b][:sb[2]+1])[0]
            if va is None or vb is None: continue
            fa=A.resolve_fee(m2,a,sa[0],sa[1],int(va),ev_tier=A.event_tier_at(E[a],sa[2])); fb=A.resolve_fee(m2,b,sb[0],sb[1],int(vb),ev_tier=A.event_tier_at(E[b],sb[2]))
            if fa is None or fb is None: continue
            B=A.max_base_for_budget(sa[0],sa[1],int(va),Q,*fa)
            if B<=0: continue
            bo=A.buy_exact_out(sa[0],sa[1],int(va),B,*fa); outq=A.exec_sell(sb[0],sb[1],int(vb),B,*fb)[0]; pred=outq-bo[0]-FEE
            if pred>0 and (best is None or pred>best[0]): best=(pred,a,b,B,int(va),int(vb),fa,fb,bo[0])
        if best is None: continue
        n_states+=1; pred,a,b,B,va,vb,fa,fb,q0=best; life=0
        for h in H:
            vals=[]
            for sl in (s+h-1,s+h):
                sa=A.state_provable(E[a],sl); sb=A.state_provable(E[b],sl)
                if not sa or not sb: continue
                bo=A.buy_exact_out(sa[0],sa[1],va,B,*fa)
                if bo is None or bo[0]>Q: vals.append(-FEE); continue
                outq=A.exec_sell(sb[0],sb[1],vb,B,*fb)[0]; vals.append((outq-bo[0]-FEE) if outq>=Q+FEE else -FEE)
            if vals:
                v=min(vals); prof[h].append(v/LAMP)
                if v>0: surv[h]+=1; life=h
        lifetimes.append(life)
        # competitie: alte semnaturi in cele doua pool-uri in (s, s+3]; captura de executori identificati
        others=set(); cap=0
        for p in (a,b):
            for e in E[p]:
                if s<e[2]<=s+3: others.add(e[15]); cap+=(e[15] in cens)
        comp.append((len(others),cap))
hl=dict(profitable_states_detected=n_states,median_lifetime_slots=(S.median(lifetimes) if lifetimes else None),survival_pct={h:(surv[h]/n_states if n_states else None) for h in H},profit_decay_mean_sol={h:(S.mean(prof[h]) if prof[h] else None) for h in H},competition=dict(median_other_signatures_within_3_slots=(S.median([c[0] for c in comp]) if comp else None),share_states_with_identified_arber_within_3_slots=(sum(1 for c in comp if c[1]>0)/len(comp) if comp else None)),plausible_at_3_slots=((surv[3]/n_states)>=0.5 if n_states else None),note="descriptiv; orizonturile nu inlocuiesc alegerea inghetata +3; identificarea executorilor foloseste semnaturile recensamantului doar ca diagnostic")
json.dump(hl,open(f"{OUT}/opportunity_half_life_v2.json","w"),indent=1,default=str); print("SLOW",{k:v for k,v in out.items() if k in ("engine","statuses","predicted_vs_realized")},ev.get("verdict"),ev.get("gate")); print("HALFLIFE",hl); print("SLOW_DONE")
