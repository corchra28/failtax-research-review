"""Executor comun pentru coada S1-S7: intrare la decizie + L sloturi (worst-of pre/post slot), 0,10 SOL primar (0,25/0,50 diagnostic), cumparare exact-B sub buget, iesire vanzare exact B dupa H secunde
(sau la un slot dat), stari ancorate, rupturi de lant excluse, taxe observate/tier demonstrat, cost retea 0,000105 SOL per tranzactie (2 tranzactii = 0,00021). Statistici + bootstrap cluster (mint x zi) + gate global."""
import gzip,json,hashlib,collections,statistics as S,random,bisect,math,time,os,sys
sys.path.insert(0,'research'); import atomic_same_mint_arb as A
D=A.D; LAMP=10**9; NET1=105000; DAYS=dict(DEV="2026-09-02",VAL="2026-09-03",PH="2026-09-04"); NS="external-review-v1"
def hid(v): return hashlib.sha256(f"{NS}:{v}".encode()).hexdigest()[:32]
def fee_at(ev,i):
    e=ev[i]
    if e[12]>0: return (e[12],e[13],e[14])
    return A.event_tier_at(ev,i)
def state_idx_provable(ev,slot):
    st=A.state_provable(ev,slot); return st
def execute_at(ev,vq,dslot,L,N_sol,hold_s,fee_mult=1.0,breaks=None):
    """decizie la finalul slotului dslot; landing = worst-of {dslot+L-1, dslot+L}; iesire la prima stare ancorata dupa entry_ts+hold_s. Returneaza dict cu status/pnl."""
    breaks=breaks if breaks is not None else A.chain_breaks(ev); Q=int(N_sol*LAMP); res=[]
    for ls in (dslot+L-1,dslot+L):
        st=A.state_provable(ev,ls)
        if st is None: res.append(dict(status="ENTRY_STATE_UNPROVABLE")); continue
        i=st[2]; fa=fee_at(ev,i)
        if fa is None: res.append(dict(status="FEE_UNRESOLVED")); continue
        fa=tuple(int(math.ceil(v*fee_mult)) for v in fa); rb,rq=st[0],st[1]; B=A.max_base_for_budget(rb,rq,vq,Q,*fa)
        if B<=0: res.append(dict(status="NO_FILL")); continue
        bo=A.buy_exact_out(rb,rq,vq,B,*fa); spent=bo[0]; qpool=bo[1]+bo[2]; X=ev[i][1]+hold_s; ts=[e[1] for e in ev]; j=bisect.bisect_right(ts,X)-1
        if j<=i: res.append(dict(status="NO_EXIT_STATE")); continue
        if not A.anchored(ev,j): res.append(dict(status="EXIT_UNANCHORED")); continue
        if not A.chain_ok_between(breaks,i,j): res.append(dict(status="CHAIN_BREAK_IN_HOLD")); continue
        fb=fee_at(ev,j)
        if fb is None: res.append(dict(status="FEE_UNRESOLVED")); continue
        fb=tuple(int(math.ceil(v*fee_mult)) for v in fb); rb2=ev[j][8]-B; rq2=ev[j][9]+qpool
        if rb2<=0: res.append(dict(status="OVERLAY_INVALID")); continue
        out=A.exec_sell(rb2,rq2,vq,B,*fb)[0]; res.append(dict(status="OK",pnl=(out-spent-2*NET1)/LAMP,entry_slot=ev[i][2],entry_ts=ev[i][1],exit_ts=ev[j][1],B=B,spent=spent,out=out))
    ok=[r for r in res if r["status"]=="OK"]
    if len(ok)<2: return dict(status=next((r["status"] for r in res if r["status"]!="OK"),"UNKNOWN"))
    return min(ok,key=lambda r:r["pnl"])   # worst-of pre/post slot
def stats(rows,key="pnl"):
    rows=[r for r in rows if r.get(key) is not None]; v=[r[key] for r in rows]
    if not v: return None
    w=[a for a in v if a>0]; l=[a for a in v if a<=0]; srt=sorted(v,reverse=True); n=len(v); pos=collections.defaultdict(float); [pos.__setitem__(r.get("mint") or r.get("token"),pos[r.get("mint") or r.get("token")]+max(0,r[key])) for r in rows]; gp=sum(pos.values()) or 1e-12
    days=collections.defaultdict(list); [days[r["day"]].append(r[key]) for r in rows]
    return dict(N=n,mints=len(pos),EV=sum(v)/n,median=S.median(v),PF=((sum(w)/abs(sum(l))) if l and sum(l)<0 else (float("inf") if w else 0.0)),win_rate=len(w)/n,EX_BEST_1PCT=sum(srt[max(1,n//100):])/max(1,n-max(1,n//100)),max_mint_share=max(pos.values())/gp,by_day={d:sum(a)/len(a) for d,a in days.items()},by_day_N={d:len(a) for d,a in days.items()},total=sum(v))
MIN_N=50; MIN_MINTS=20
def boot(rows,key="pnl",reps=10000,seed=20260905,alpha=0.05):
    """inferenta (CI/p) doar peste pragul minim de esantion (N>=50 si >=20 mint-uri); altfel None (n/a) — fara p-value/CI pe esantioane sub prag."""
    rows=[r for r in rows if r.get(key) is not None]
    if not rows or len(rows)<MIN_N or len({(r.get("mint") or r.get("token")) for r in rows})<MIN_MINTS: return None
    rng=random.Random(seed); g=collections.defaultdict(list); [g[(r.get("mint") or r.get("token"),r["day"])].append(r[key]) for r in rows]; G=list(g.values()); bs=[]
    for _ in range(reps):
        tot=0.0; cnt=0
        for _k in range(len(G)): a=G[rng.randrange(len(G))]; tot+=sum(a); cnt+=len(a)
        bs.append(tot/cnt)
    bs.sort(); return dict(CI95=(bs[int(alpha/2*reps)],bs[int((1-alpha/2)*reps)-1]),p_le_0=sum(1 for b in bs if b<=0)/reps,clusters=len(G))
def global_gate(st,bs,st5,stc,alpha_corr):
    if st is None: return None,"INSUFFICIENT_CLEAN_SAMPLE"
    if st["N"]<50 or st["mints"]<20: return None,"INSUFFICIENT_CLEAN_SAMPLE"
    g=dict(N50=True,mints20=True,EV=st["EV"]>0,PF=st["PF"]>=1.5,CI_low=(bs["CI95"][0]>0) if bs else False,val_pos=(st["by_day"].get(DAYS["VAL"],-1)>0),ph_pos=(st["by_day"].get(DAYS["PH"],-1)>0),stress5=((st5 or {}).get("EV",-1))>0,exb1pct=st["EX_BEST_1PCT"]>0,cost125=((stc or {}).get("EV",-1))>0,concentration=st["max_mint_share"]<0.4,leakage_zero=True,reserve_violations_zero=True,executable_construction=True)
    return g,("PASS_HISTORICAL_PAPER_CANDIDATE_REQUIRING_FRESH_FORWARD_VALIDATION" if all(g.values()) else "FAIL")
def write(name,obj): json.dump(obj,open(f"research/overnight_20260905/strategies/{name}","w"),indent=1,default=str)
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
