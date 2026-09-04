"""Faza 9: teste de proprietate/fuzz pentru matematica intreaga a swap-urilor, semantica exact-base round trip, lant de rezerve cu Deposit/Withdraw ascunse, incertitudine pre/post slot."""
import sys,random,json; sys.path.insert(0,'research'); import atomic_same_mint_arb as A
rng=random.Random(20260905); res={"fuzz_cases":0,"violations":[]}
for _ in range(3000):
    rb=rng.randint(10**9,10**15); rq=rng.randint(10**8,10**12); vq=rng.choice([0,17_584_000_000,rng.randint(0,10**11)]); lp,pr,cc=rng.choice([(25,5,0),(20,5,95),(2,93,30),(20,5,5)]); Q=rng.randint(10**5,10**9)
    B=A.max_base_for_budget(rb,rq,vq,Q,lp,pr,cc); res["fuzz_cases"]+=1
    if B<0 or B>=rb: res["violations"].append(("B_range",rb,rq,Q)); continue
    if B>0:
        bo=A.buy_exact_out(rb,rq,vq,B,lp,pr,cc)
        if bo is None or bo[0]>Q: res["violations"].append(("budget",rb,rq,vq,Q,B)); continue
        nb=A.buy_exact_out(rb,rq,vq,B+1,lp,pr,cc)
        if nb is not None and nb[0]<=Q: res["violations"].append(("not_max",rb,rq,vq,Q,B))
        # invariant CP dupa buy: (rb-B)*(rq+vq+q2) >= rb*(rq+vq)
        if (rb-B)*(rq+vq+bo[1])<rb*(rq+vq): res["violations"].append(("k_invariant_buy",rb,rq,vq,B))
        # round trip exact: vanzarea aceluiasi B in acelasi pool (dupa buy) nu poate produce profit (taxe) si nu lasa inventar
        out,brut,_,_,_=A.exec_sell(rb-B,rq+bo[1]+bo[2],vq,B,lp,pr,cc)
        if out>bo[0]: res["violations"].append(("free_lunch_same_pool",rb,rq,vq,B))
        if out<0 or out>rq+bo[1]+bo[2]: res["violations"].append(("sell_cap",rb,rq,vq,B))
    # exec_sell monotonie in B
    o1=A.exec_sell(rb,rq,vq,10**6,lp,pr,cc)[0]; o2=A.exec_sell(rb,rq,vq,2*10**6,lp,pr,cc)[0]
    if o2<o1: res["violations"].append(("sell_monotone",rb,rq,vq))
# lant de rezerve cu Deposit/Withdraw ascuns: o schimbare ascunsa de rezerve intre doua evenimente rupe ancora si exclude starea
ev=[[0,0,10,0,0,1,1000,1000,990,1010,10,10,25,5,0,"s"],[0,1,11,1,0,1,990,1010,980,1020,10,10,25,5,0,"s"],[0,2,12,2,0,1,980,1020,970,1030,10,10,25,5,0,"s"]]
ev2=[list(e) for e in ev]; ev2[2][6]=1980; ev2[2][7]=2020   # deposit ascuns intre ev[1] si ev[2]
res["hidden_deposit_breaks_anchor"]=(A.anchored(ev,1) and not A.anchored(ev2,1) and A.state_provable(ev2,11) is None and A.state_provable(ev,11) is not None)
res["tail_unanchored"]=(A.state_provable(ev,12) is None)
res["pre_post_worstcase"]="verificat in slow_atomic_revert_arb_tests (v2_landing_slot_worst_case_used)"
res["PASS"]=(not res["violations"]) and res["hidden_deposit_breaks_anchor"] and res["tail_unanchored"]
json.dump(res,open("research/overnight_20260905/atomic_census/property_tests.json","w"),indent=1); print("PROPERTY_TESTS",res["PASS"],"cases",res["fuzz_cases"],"violations",len(res["violations"]))
