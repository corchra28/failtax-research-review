"""S3 CROSS_POOL_FLOW_LEAD_LAG (spec inghetat in cod): pentru token-urile cu >= 2 pool-uri (grupuri pass2), liderul per token = pool-ul cu (volum anterior, traderi unici anteriori, latenta istorica de raspuns) — definit EXCLUSIV din activitatea DEV anterioara, inghetat;
eveniment = slot cu flux semnat al liderului (net quote buy - sell) in decila superioara DEV (relativ la rq), fara semnatura comuna cu tinta, tinta ancorata; tranzactie: cumparare in pool-ul tinta la +3 sloturi (worst-of), 0,10 SOL, iesire +60 s; stres +5; cost x1.25."""
import sys,gzip,json,collections,statistics as S,time,bisect; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"; LAMP=10**9
spec=dict(strategy="S3_CROSS_POOL_FLOW_LEAD_LAG",mechanism="o tranzactie mare intr-un pool actualizeaza informatia inainte ca participantii celuilalt pool sa reactioneze",who_loses="LP-urile si traderii pool-ului tinta care coteaza pretul vechi",leader_rule="per token, din activitatea DEV (09-02) anterioara: scor = rang(volum quote) + rang(traderi unici) + rang(-latenta mediana de raspuns a celuilalt pool la miscarile acestuia); liderul = scor maxim; inghetat; daca nu exista activitate DEV pentru token => token exclus",
  event="slot s cu flux net al liderului (quote buy - sell in slot s) / rq_pre >= decila 9 DEV (pozitiv => cumparam in tinta); excluse: semnaturi care ating ambele pool-uri, semnaturi din recensamantul de arbitraj, tinta fara stare ancorata la landing, rupturi",execution="+3 sloturi worst-of, 0,10 SOL exact-B in tinta, iesire +60 s; stres +5; cost x1.25; max o pozitie per slot",rejects=["efectul dispare fara tranzactiile atomice","liderul schimbat retroactiv","< 20 token-uri independente"],frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s3_frozen_spec.json",spec)
E=A.load_pass2(); meta=A.load_rpc_meta(); Pp=json.load(open(A.POPFILE)); groups=json.load(open(A.RPC_PAIRS))["pairs"]; cens=set()
for l in gzip.open(f"{C.D}/census_rows.jsonl.gz","rt"):
    c=json.loads(l)
    if c["cls"] in ("EXACT","DUST"): cens.add(c["sig"])
DEV0=1788307200.0; DEV1=DEV0+86400   # 2026-09-02 UTC
leaders={}; rows=[]; cnt=collections.Counter()
for tok,ps in groups.items():
    ok=[p for p in ps if p in E and E[p] and meta[p]["orientation"]=="STRICT"]
    if len(ok)<2: continue
    sc={}
    for p in ok:
        dev=[e for e in E[p] if DEV0<=e[1]<DEV1]
        if len(dev)<5: continue
        vol=sum(e[11] for e in dev); users=len({e[15] for e in dev if isinstance(e[15],str)})
        # latenta de raspuns: pentru fiecare miscare a lui p in DEV, sloturi pana la urmatorul eveniment al oricarui alt pool
        others=sorted(e[2] for q in ok if q!=p for e in E[q] if DEV0<=e[1]<DEV1); lat=[]
        for e in dev[::max(1,len(dev)//50)]:
            j=bisect.bisect_right(others,e[2]); 
            if j<len(others): lat.append(others[j]-e[2])
        sc[p]=(vol,users,-(S.median(lat) if lat else 1e9))
    if len(sc)<2: cnt["TOKEN_NO_DEV_ACTIVITY"]+=1; continue
    ranks=collections.Counter()
    for k in range(3):
        for i,p in enumerate(sorted(sc,key=lambda p:sc[p][k])): ranks[p]+=i
    leader=max(ranks,key=lambda p:ranks[p]); leaders[tok]=leader; targets=[p for p in ok if p!=leader]
    L=E[leader]; byslot=collections.defaultdict(list); [byslot[e[2]].append(e) for e in L]
    for s,es in byslot.items():
        sigs={e[15] for e in es if isinstance(e[15],str) and len(e[15])>50}
        if any(x in cens for x in sigs): cnt["EXCL_ARB_SIG"]+=1; continue
        for tgt in targets:
            if any(e[2]==s and e[15] in sigs for e in E[tgt]): cnt["EXCL_COMMON_SIG"]+=1; continue
            net=sum(e[11] if e[5] else -e[11] for e in es); rq=es[0][7]
            rows.append(dict(token=tok,mint=tok,leader=leader,target=tgt,slot=s,ts=es[0][1],day=time.strftime("%Y-%m-%d",time.gmtime(es[0][1])),flow_rel=net/rq if rq>0 else 0.0))
dev=[r for r in rows if r["day"]==C.DAYS["DEV"]]; q9=sorted(r["flow_rel"] for r in dev)[int(0.9*len(dev))] if dev else None
C.write("s3_thresholds_frozen.json",dict(q9_flow_rel=q9,leaders_hashed={C.hid(t):C.hid(p) for t,p in leaders.items()},n_tokens=len(leaders),frozen_at=time.strftime("%Y-%m-%d %H:%M:%S")))
sig=[r for r in rows if q9 is not None and r["flow_rel"]>=q9]; bys=collections.defaultdict(list); [bys[r["slot"]].append(r) for r in sig]; chosen=[max(v,key=lambda r:r["flow_rel"]) for v in bys.values()]
out=[]
for r in chosen:
    ev=E[r["target"]]; vq=A.implied_vq(ev[:max(5,bisect.bisect_right([e[2] for e in ev],r["slot"]))])[0]
    if vq is None: cnt["VQ_INVALID"]+=1; continue
    o=C.execute_at(ev,int(vq),r["slot"],3,0.10,60); o5=C.execute_at(ev,int(vq),r["slot"],5,0.10,60); oc=C.execute_at(ev,int(vq),r["slot"],3,0.10,60,fee_mult=1.25)
    out.append(dict(r,status=o["status"],pnl=o.get("pnl"),pnl5=o5.get("pnl"),pnlc=oc.get("pnl")))
test=[r for r in out if r["day"]!=C.DAYS["DEV"]]; st=C.stats(test); bs=C.boot(test); st5=C.stats(test,"pnl5"); stc=C.stats(test,"pnlc"); g,verdict=C.global_gate(st,bs,st5,stc,0.05)
if len(leaders)<20 and verdict.startswith("PASS"): verdict="FAIL_FEWER_THAN_20_TOKENS"
res=dict(spec_sha256=C.sha(f"{OUT}/s3_frozen_spec.json"),tokens_with_leader=len(leaders),counts=dict(cnt),events=len(rows),signals=len(sig),chosen=len(chosen),q9_flow_rel=q9,dev_descriptive=C.stats([r for r in out if r["day"]==C.DAYS["DEV"]]),test=st,bootstrap=bs,stress5=st5,cost125=stc,status_counts=dict(collections.Counter(r["status"] for r in out)),gate=g,verdict=verdict)
C.write("s3_results.json",res); print("S3",verdict,"tokens",len(leaders),"signals",len(sig),"test",{k:(st or {}).get(k) for k in ("N","mints","EV","PF")},dict(cnt)); print("S3_DONE")
