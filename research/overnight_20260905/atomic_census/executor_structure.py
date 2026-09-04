"""Faza 4: structura executorilor (fara portofele in clar) + ARBER_PERSISTENCE_V1 (spec inghetat)."""
import gzip,json,hashlib,collections,statistics as S,random,time
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/overnight_20260905/atomic_census"; NS="external-review-v1"; LAMP=10**9
def hid(v): return hashlib.sha256(f"{NS}:{v}".encode()).hexdigest()[:32]
rows=[json.loads(l) for l in gzip.open(f"{D}/census_rows.jsonl.gz","rt")]; ex=[r for r in rows if r["cls"]=="EXACT"]
byu=collections.defaultdict(list); [byu[r["user"]].append(r) for r in ex]
E={}
for u,rs in byu.items():
    days=sorted({r["day"] for r in rs}); hours=collections.Counter(time.strftime("%H",time.gmtime(r["t"])) for r in rs); pp=collections.Counter(tuple(r["pools"]) for r in rs)
    E[hid(u)]=dict(cycles=len(rs),repeat=(len(rs)>1),tokens=len({r["token"] for r in rs}),pool_pairs=len(pp),days=days,hours_active=len(hours),median_paid_sol=S.median([r["paid"]/LAMP for r in rs]),median_net_sol=S.median([r["net_PRIMARY"]/LAMP for r in rs]),total_net_sol=sum(r["net_PRIMARY"] for r in rs)/LAMP,canonical_involved_share=sum(1 for r in rs if r["canon"]>0)/len(rs),route_persistence_top_pair_share=pp.most_common(1)[0][1]/len(rs),same_pools_across_days=sum(1 for p,c in pp.items() if len({r["day"] for r in rs if tuple(r["pools"])==p})>1),swaps_hist=dict(collections.Counter(r["n_swaps"] for r in rs)),direction_buy_first_pool=dict(collections.Counter(hid(r["first_pool_buy"]) for r in rs).most_common(3)))
struct_=dict(n_executors=len(E),one_off=sum(1 for v in E.values() if not v["repeat"]),repeat=sum(1 for v in E.values() if v["repeat"]),cycles_by_swaps=dict(collections.Counter(r["n_swaps"] for r in ex)),exact_round_trip_share=1.0,temporary_inventory_share=0.0,note="populatia EXACT are prin definitie base conservat (round trip exact); ciclurile cu inventar temporar sunt in populatia DUST/respinse",profit_concentration=dict(top1_executor_share=(max(v["total_net_sol"] for v in E.values() if v["total_net_sol"]>0)/sum(v["total_net_sol"] for v in E.values() if v["total_net_sol"]>0)) if any(v["total_net_sol"]>0 for v in E.values()) else None,executors_with_positive_total=sum(1 for v in E.values() if v["total_net_sol"]>0)),by_day=dict(collections.Counter(r["day"] for r in ex)),by_hour=dict(sorted(collections.Counter(time.strftime("%H",time.gmtime(r["t"])) for r in ex).items())),canonical_composition=dict(collections.Counter(("CANONICAL+NONCANONICAL" if r["canon"]>0 else "NONCANONICAL+NONCANONICAL") for r in ex)),executors_hashed=E)
json.dump(struct_,open(f"{OUT}/executor_structure.json","w"),indent=1,default=str)
# ---- ARBER_PERSISTENCE_V1 ----
spec=json.load(open(f"{OUT}/arber_persistence_frozen_spec.json")); days_all=sorted({r["day"] for r in ex}); first={u:min(r["day"] for r in rs) for u,rs in byu.items()}
elig={u:rs for u,rs in byu.items() if first[u]<days_all[-1]} if days_all else {}
fd_ev={u:S.mean([r["net_PRIMARY"] for r in rs if r["day"]==first[u]])/LAMP for u,rs in elig.items()}
res=dict(spec=spec,eligible_prior_day_executors=len(elig))
if len(elig)>=1:
    q3=sorted(fd_ev.values())[int(0.75*len(fd_ev))]; top={u for u,v in fd_ev.items() if v>=q3}; sub=[r for u in top for r in byu[u] if r["day"]>first[u]]
    v=[r["net_PRIMARY"]/LAMP for r in sub]; w=[a for a in v if a>0]; l=[a for a in v if a<=0]; srt=sorted(v,reverse=True); n=len(v)
    st=dict(N=n,EV=(sum(v)/n if n else None),PF=((sum(w)/abs(sum(l))) if (l and sum(l)<0) else (float("inf") if w else 0.0)) if n else None,EX_BEST_1PCT=(sum(srt[max(1,n//100):])/max(1,n-max(1,n//100)) if n else None),by_day={d:S.mean([r["net_PRIMARY"]/LAMP for r in sub if r["day"]==d]) for d in sorted({r["day"] for r in sub})})
    rng=random.Random(20260905); g=collections.defaultdict(list); [g[(r["user"],r["day"])].append(r["net_PRIMARY"]/LAMP) for r in sub]; G=list(g.values()); bs=[]
    for _ in range(10000 if G else 0):
        tot=0.0; cnt=0
        for _k in range(len(G)): a=G[rng.randrange(len(G))]; tot+=sum(a); cnt+=len(a)
        bs.append(tot/cnt)
    bs.sort(); ci=(bs[250],bs[9749]) if bs else None
    gate=dict(executors10=len(elig)>=10,cycles30=n>=30,EV=(st["EV"] or -1)>0,PF=(st["PF"] or 0)>=1.5,CI_low=(ci[0]>0) if ci else False,exb1pct=(st["EX_BEST_1PCT"] or -1)>0,every_day_positive=(bool(st["by_day"]) and all(v>0 for v in st["by_day"].values())))
    res.update(dict(q3_first_day_EV=q3,top_quartile_executors=len(top),subsequent=st,CI95_user_day=ci,gate=gate,verdict=("ARBER_PERSISTENCE_CONFIRMED" if all(gate.values()) else ("ARBER_PERSISTENCE_INSUFFICIENT_SAMPLE" if not (gate["executors10"] and gate["cycles30"]) else "ARBER_PERSISTENCE_NOT_CONFIRMED"))))
else: res["verdict"]="ARBER_PERSISTENCE_INSUFFICIENT_SAMPLE"
json.dump(res,open(f"{OUT}/arber_persistence_results.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in struct_.items() if k!="executors_hashed"},default=str)[:800]); print("PERSISTENCE",{k:v for k,v in res.items() if k in ("eligible_prior_day_executors","top_quartile_executors","subsequent","gate","verdict")}); print("STRUCTURE_DONE")
