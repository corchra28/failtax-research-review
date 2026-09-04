"""S5 CREATOR_TRACK_RECORD_PERSISTENCE (spec inghetat in cod): calitatea creatorului DOAR din lansarile anterioare (creator_history: create/complete/curba pentru toate creatiile din banda + m_pools pentru outcome-ul intrarii intarziate 60 s);
eligibil: >= 3 lansari anterioare complet observate (create_ts + 420 s < create_ts curent); scor = medie ranguri DEV (rata de migrare anterioara, -timp median pana la migrare, -concentrare top1 anterioara, -vanzari creator anterioare, outcome net anterior al intrarii la 60 s);
semnal: scor >= Q3 DEV pentru lansarile din m_pools (migrate) la decizie T0+60 s; intrare +3 sloturi, 0,10 SOL, iesire +60 s; stres +5; cost x1.25."""
import sys,gzip,json,collections,statistics as S,time,bisect; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"
spec=dict(strategy="S5_CREATOR_TRACK_RECORD_PERSISTENCE",mechanism="unii creatori produc repetat lansari cu lichiditate reala, altii extrag repetat; doar lansarile anterioare definesc calitatea",who_loses="cumparatorii lansarilor creatorilor extractivi (evitati) / vanzatorii timpurii ai lansarilor creatorilor cu istoric bun",history_source="toate CreateEvent din banda (creator, create_ts, complete_ts, trade-uri curba, cumparatori, top1, vanzari creator) + outcome-ul intrarii fixe la 60 s pentru lansarile migrate anterioare (m_pools)",eligibility=">= 3 lansari anterioare complet observate (create_ts_anterior + 420 s < create_ts curent); fara informatie din lansarea curenta; creatorii distincti raman distincti",score="medie egal ponderata a rangurilor DEV: +rata migrare anterioara, -timp median pana la migrare, -top1 anterior median, -cota vanzarilor creatorului anterioara, +EV anterior al intrarii la 60 s (None => rang median)",signal="scor >= Q3 DEV; decizie T0+60 s; intrare +3 sloturi worst-of, 0,10 SOL exact-B; iesire +60 s; stres +5; cost x1.25",rejects=["< 20 creatori eligibili","rezultat purtat de un singur creator (> 40 % din profitul brut)"],frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s5_frozen_spec.json",spec)
H=[json.loads(l) for l in gzip.open(f"{C.D}/creator_history.jsonl.gz","rt")]; byc=collections.defaultdict(list); [byc[h["creator"]].append(h) for h in H]
X={}
for l in gzip.open(f"{C.D}/m_pools.jsonl.gz","rt"): x=json.loads(l); X[x["mint"]]=x
# outcome-ul intrarii fixe la 60 s pentru lansarile migrate (folosit DOAR ca istoric anterior al creatorului)
def fixed_outcome(x):
    ts=[e[1] for e in x["ev"]]; di=bisect.bisect_right(ts,x["T0_ts"]+60)-1; ds=x["ev"][di][2] if di>=0 else x["ev"][0][2]; o=C.execute_at(x["ev"],x["vq"],ds,3,0.10,60); return (o.get("pnl"),ds,o["status"])
OC={m:fixed_outcome(x) for m,x in X.items()}
def creator_feats(c,t_now):
    prior=[h for h in byc[c] if h["create_ts"]+420<t_now]
    if len(prior)<3: return None
    mig=[h for h in prior if h["complete_ts"] is not None]; ttm=[h["complete_ts"]-h["create_ts"] for h in mig]; top=[h["top1_share"] for h in prior if h["top1_share"] is not None]; cs=[(h["creator_sold"]/h["creator_bought"]) if h["creator_bought"] else 0.0 for h in prior]
    outs=[OC[h["mint"]][0] for h in mig if h["mint"] in OC and OC[h["mint"]][0] is not None and X[h["mint"]]["T0_ts"]+420<t_now]
    return dict(n_prior=len(prior),mig_rate=len(mig)/len(prior),ttm_med=(S.median(ttm) if ttm else None),top1_med=(S.median(top) if top else None),creator_sell=S.mean(cs),prior_ev=(S.mean(outs) if outs else None))
rows=[]
for m,x in X.items():
    f=creator_feats(x["creator"],x["create_t"])
    if f is None: continue
    rows.append(dict(mint=m,creator=x["creator"],day=x["day"],f=f))
dev=[r for r in rows if r["day"]==C.DAYS["DEV"]]; keys=[("mig_rate",1),("ttm_med",-1),("top1_med",-1),("creator_sell",-1),("prior_ev",1)]
sd={k:sorted(r["f"][k] for r in dev if r["f"][k] is not None) for k,_ in keys}
def score(r):
    s=0.0
    for k,sg in keys:
        v=r["f"][k]
        if v is None or not sd[k]: s+=0.5; continue
        pr=bisect.bisect_right(sd[k],v)/len(sd[k]); s+=(pr if sg>0 else 1-pr)
    return s/len(keys)
for r in rows: r["score"]=score(r)
q3=sorted(r["score"] for r in dev)[int(0.75*len(dev))] if dev else None
C.write("s5_thresholds_frozen.json",dict(q3_score=q3,n_dev_eligible=len(dev),creators_eligible_total=len({r["creator"] for r in rows}),frozen_at=time.strftime("%Y-%m-%d %H:%M:%S")))
out=[]
for r in rows:
    if r["day"]==C.DAYS["DEV"] or q3 is None or r["score"]<q3: continue
    x=X[r["mint"]]; ts=[e[1] for e in x["ev"]]; di=bisect.bisect_right(ts,x["T0_ts"]+60)-1; ds=x["ev"][di][2] if di>=0 else x["ev"][0][2]
    o=C.execute_at(x["ev"],x["vq"],ds,3,0.10,60); o5=C.execute_at(x["ev"],x["vq"],ds,5,0.10,60); oc=C.execute_at(x["ev"],x["vq"],ds,3,0.10,60,fee_mult=1.25)
    out.append(dict(mint=r["mint"],creator=r["creator"],day=r["day"],status=o["status"],pnl=o.get("pnl"),pnl5=o5.get("pnl"),pnlc=oc.get("pnl")))
st=C.stats(out); bs=C.boot(out); st5=C.stats(out,"pnl5"); stc=C.stats(out,"pnlc"); g,verdict=C.global_gate(st,bs,st5,stc,0.05)
ncre=len({r["creator"] for r in rows}); cshare=None
if out:
    pos=collections.defaultdict(float); [pos.__setitem__(r["creator"],pos[r["creator"]]+max(0,r["pnl"] or 0)) for r in out]; gp=sum(pos.values()) or 1e-12; cshare=max(pos.values())/gp
    if verdict.startswith("PASS") and (ncre<20 or cshare>=0.4): verdict="FAIL_CREATOR_RULE"
res=dict(spec_sha256=C.sha(f"{OUT}/s5_frozen_spec.json"),creations_in_tape=len(H),creators=len(byc),launches_with_3plus_prior=len(rows),eligible_creators=ncre,q3_score=q3,signals=len(out),test=st,bootstrap=bs,stress5=st5,cost125=stc,top_creator_share=cshare,status_counts=dict(collections.Counter(r["status"] for r in out)),gate=g,verdict=verdict)
C.write("s5_results.json",res); print("S5",verdict,"eligible launches",len(rows),"creators",ncre,"signals",len(out),{k:(st or {}).get(k) for k in ("N","mints","EV","PF")}); print("S5_DONE")
