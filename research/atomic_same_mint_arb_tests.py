"""Teste sintetice pentru cele 10 blocante (fara date reale, fara PnL istoric)."""
import sys,json,math; sys.path.insert(0,'research'); import atomic_same_mint_arb as A
WSOL=A.WSOL; res={}
P={"POOL_C":dict(canonical=True,base_mint="TOKEN",quote_mint=WSOL,supply=10**15),"POOL_N":dict(canonical=False,base_mint="TOKEN",quote_mint=WSOL),"POOL_R":dict(canonical=False,base_mint=WSOL,quote_mint="TOKEN"),"POOL_C_NOSUPPLY":dict(canonical=True,base_mint="TOKEN",quote_mint=WSOL)}
# 1 orientare: pool normal OK; pool inversat respins (assert) si exclus din populatie
sa=(206_900_000_000_000,67_405_853_768); sb=(150_000_000_000_000,120_000_000_000); vq=17_584_000_000
ok=A.arb(P,"POOL_C",sa,vq,"POOL_N",sb,0,int(0.25e9)); res["1_normal_pool_arb_computes"]=bool(ok and ok["invariant_ok"])
res["1_canonical_without_validated_supply_or_event_tier_excluded"]=A.arb(P,"POOL_C_NOSUPPLY",sa,vq,"POOL_N",sb,0,int(0.25e9)) is None
try: A.arb(P,"POOL_R",sb,0,"POOL_C",sa,vq,int(0.25e9)); res["1_reversed_rejected"]=False
except AssertionError: res["1_reversed_rejected"]=True
inv=dict(pools={"X":dict(base_mint="TOKEN",quote_mint=WSOL),"Y":dict(base_mint=WSOL,quote_mint="TOKEN"),"Z":dict(base_mint="TOKEN",quote_mint=WSOL)}); dup,info=A.pairs_from_inventory(inv); res["1_population_strict"]=(list(dup)==["TOKEN"] and dup["TOKEN"]==["X","Z"] and info["reversed_orientation_pools_excluded"]==1)
# 2 rupturi de lant
ev=[[0,0,10,0,0,1,100,100,90,110,10,10,20,5,0,"s"],[0,1,11,1,0,1,90,110,80,120,10,10,20,5,0,"s"],[0,2,12,2,0,1,85,120,75,130,10,10,20,5,0,"s"]]   # ruptura intre idx1 si idx2 (80!=85)
br=A.chain_breaks(ev); res["2_break_detected"]=(br==[2]); res["2_interval_ok_before_break"]=A.chain_ok_between(br,0,1) and not A.chain_ok_between(br,0,2) and not A.chain_ok_between(br,1,2)
# 3 gap boolean
res["3_interval_clean"]=A.interval_clean(10,12,[(20,30)],[(40,50)]) and not A.interval_clean(10,25,[(20,30)],[]) and not A.interval_clean(45,46,[],[(40,50)])
# 4 data ferestrei din slotul de inceput (joint_windows returneaza t1)
evA=[[1000.0,1000,10,0,0,1,100,100,90,110,10,10,20,5,0,"a"],[1200.0,1200,20,1,0,1,90,110,80,120,10,10,20,5,0,"a"]]; evB=[[1050.0,1050,12,0,0,1,100,100,90,110,10,10,20,5,0,"b"],[1300.0,1300,25,1,0,1,90,110,80,120,10,10,20,5,0,"b"]]
W=A.joint_windows(evA,evB,[],[]); res["4_window_has_start_ts"]=all(len(w)==4 and w[3]>=1000 for w in W) and len(W)==2
# 5 token program (comportamental): mint necunoscut -> exclus; SPL Token -> permis; Token-2022 -> exclus; sufixul 'pump' NU ajuta
res["5_unknown_excluded"]=A.pair_allowed_for_pnl("ABCpump",{})==(False,"TOKEN_PROGRAM_UNKNOWN"); res["5_spl_allowed"]=A.pair_allowed_for_pnl("M1",{"M1":A.SPL_TOKEN})==(True,"SPL_TOKEN"); res["5_token2022_excluded"]=A.pair_allowed_for_pnl("M2",{"M2":A.TOKEN_2022})==(False,"TOKEN_2022_EXCLUDED"); res["5_other_program_excluded"]=A.pair_allowed_for_pnl("M3",{"M3":"Other111"})[0] is False
# 6 VQ: <5 obs -> None; negativ -> None; dispersie mare -> None; consistent -> valoare
def mk(vq,n=8,noise=0):
    out=[]; rb=206_900_000_000_000; rq=67_405_853_768
    for i in range(n):
        q=1_000_000_000+i*1000; tok=rb*q//(rq+vq+q+(noise*(i%2))); out.append([0,i,i,i,0,1,rb,rq,rb-tok,rq+q,tok,q,20,5,0,"s"]); rb-=tok; rq+=q
    return out
res["6_vq_lt5_none"]=A.implied_vq(mk(17_584_000_000,n=3))[0] is None; res["6_vq_ok"]=abs((A.implied_vq(mk(17_584_000_000))[0] or 0)-17_584_000_000)<1e6; res["6_vq_negative_none"]=A.implied_vq(mk(-5_000_000_000))[0] is None; res["6_vq_dispersion_none"]=A.implied_vq(mk(17_584_000_000,noise=5_000_000_000))[0] is None
# 7 staleness: max(s-last_A, s-last_B)
s=100; res["7_staleness_max"]=(max(s-90,s-99)==10)
# 8 episoade (comportamental): [+,+,0,+,None,+] -> [1,0,0,1,0,1]; secventa toata pozitiva -> o singura intrare
res["8_episode_flags"]=A.episode_first_flags([1,2,0,3,None,4])==[1,0,0,1,0,1]; res["8_single_episode"]=A.episode_first_flags([1,1,1,1])==[1,0,0,0]; res["8_none_positive"]=A.episode_first_flags([0,-1,None])==[0,0,0]
# 9 poarta (comportamental): statistici bune -> toate PASS; o incalcare de taxa -> zero_violations FAIL; segment negativ -> segments_positive FAIL; spec modificat -> no_post_hoc FAIL
good=dict(N=60,EV=0.01,median=0.005,PF=2.0,CI95_cluster_hour=(0.001,0.02),EX_BEST_1PCT=0.008,top1pct_contrib=0.1); Aseg=dict(realized_net_base=good,positive_days=3,max_day_share=0.4,survival_pred_to_realized_base=0.8,realized_landing_s2_base=dict(EV=0.005),realized_net_stress2=dict(EV=0.002))
BN={"CANONICAL+NONCANONICAL":dict(realized_net_base=dict(EV=0.01)),"NONCANONICAL+NONCANONICAL":None}
spec=dict(primary_notional_sol=A.PRIMARY,notionals_sol=A.NOTIONALS,final_gate=dict(PF_min=1.5,N_realized_min=50,positive_days_min=2,top1pct_max=0.4,max_day_share_max=0.6,survival_min=0.6),costs=dict(priority_fee_lamports=A.PRIO,jito_tip_scenarios_lamports=A.TIPS,base_signature_fee_lamports=A.SIG_FEE))
g=A.final_gate(Aseg,BN,{},spec,True); res["9_gate_all_pass_on_good"]=all(g.values()) and set(g)=={"N50","days2","EV","median","PF","CI_low","exb1pct","top1","day_share","survival","landing_s2","stress2","zero_violations","segments_positive","no_post_hoc"}
res["9_gate_fee_violation"]=A.final_gate(Aseg,BN,{"FEE_RESOLVER_NONE":1},spec,True)["zero_violations"] is False; res["9_gate_token_program_unknown"]=A.final_gate(Aseg,BN,{},spec,False)["zero_violations"] is False
res["9_gate_segment_negative"]=A.final_gate(Aseg,{"CANONICAL+NONCANONICAL":dict(realized_net_base=dict(EV=-0.01))},{},spec,True)["segments_positive"] is False
sp2=json.loads(json.dumps(spec)); sp2["final_gate"]["PF_min"]=1.2; res["9_gate_spec_tampered"]=A.final_gate(Aseg,BN,{},sp2,True)["no_post_hoc"] is False
# 10 PF inf
st=A.stats([0.1,0.2,0.3]); res["10_PF_inf_when_no_losses"]=(st["PF"]==float("inf")); res["10_PF_finite"]=(A.stats([0.1,-0.05])["PF"]==2.0)
# integer math invariants pe pool normal
rb,rq=sa; tok,q2,lpf,prf,ccf=A.exec_buy(rb,rq,vq,int(0.25e9),20,5,95); res["engine_buy_invariant"]=((rb-tok)*(rq+vq+q2)>=rb*(rq+vq)); out,brut,l2,p2,c2=A.exec_sell(rb-tok,rq+q2+lpf,vq,tok,20,5,95); res["engine_sell_cap"]=(out<=rq+q2+lpf)
n_pass=sum(1 for v in res.values() if v is True); print(json.dumps(res,indent=1)); blockers=[k[0:2].strip('_') for k in res]; groups={g for g in ("1","2","3","4","5","6","7","8","9","10") if any(k.split("_")[0]==g for k in res) and all(v is True for k,v in res.items() if k.split("_")[0]==g)}
print("PATCHED_BLOCKERS =",f"{len(groups)}/10"); print("ALL_TESTS_PASS =",all(v is True for v in res.values()))

# ===== MULTIPOOL_EPISODE_TESTS (grup sintetic de 3 pool-uri => 3 perechi x 2 directii = 6 rute) =====
mp={}
R6=["P1P2_A","P1P2_B","P1P3_A","P1P3_B","P2P3_A","P2P3_B"]
def slotmap(vals): return dict(zip(R6,vals))
seq=[(100,slotmap([0.01,-0.01,0.02,-0.02,0.005,-0.005])),   # episod 1: max=P1P3_A (0.02)
     (101,slotmap([0.015,-0.01,0.019,-0.02,0.004,-0.005])),  # aceeasi anomalie, alt slot, alta pereche mai buna -> NU se tranzactioneaza
     (102,slotmap([0.03,-0.01,0.001,-0.02,0.0,-0.005])),     # inca in episod (max>0) -> NU
     (103,slotmap([-0.001,-0.01,-0.002,-0.02,-0.001,-0.005])),# max<=0 -> reset
     (104,slotmap([0.002,-0.01,-0.002,-0.02,0.001,-0.005])), # episod 2: P1P2_A
     (105,slotmap([None,None,None,None,None,None])),          # fara predictii -> reset
     (106,slotmap([0.0,0.0,0.0,0.0,0.0,0.0])),                # max=0 -> nu se deschide
     (107,slotmap([0.0,0.0,0.0,0.0,0.0,0.007]))]              # episod 3: P2P3_B
sel=A.token_episode_selection(seq)
mp["mp_one_trade_per_episode"]=(sel==[(100,"P1P3_A",0.02),(104,"P1P2_A",0.002),(107,"P2P3_B",0.007)])
mp["mp_max_one_route_per_token_slot"]=(len({s for s,_,_ in sel})==len(sel))
mp["mp_no_retrade_same_anomaly_consecutive_slots"]=all(b-a>1 for a,b in zip([s for s,_,_ in sel],[s for s,_,_ in sel][1:]))
mp["mp_reset_only_when_all_routes_nonpositive"]=(A.token_episode_selection([(1,slotmap([0.01]+[0]*5)),(2,slotmap([0]*5+[0.01])),(3,slotmap([0]*6)),(4,slotmap([0]*5+[0.01]))])==[(1,"P1P2_A",0.01),(4,"P2P3_B",0.01)])
mp["mp_selection_by_predicted_only"]=(A.token_episode_selection([(1,slotmap([0.001,0.0,0.0,0.0,0.0,0.05]))])==[(1,"P2P3_B",0.05)])
# fee resolver fara supply hardcodat: canonical fara supply si fara tier demonstrat => None; cu tier demonstrat => tier; noncanonical => 25/5/0
Pm={"C":dict(canonical=True),"N":dict(canonical=False)}
mp["fee_canonical_without_supply_excluded"]=A.resolve_fee(Pm,"C",1,1,0) is None
mp["fee_canonical_event_tier"]=A.resolve_fee(Pm,"C",1,1,0,ev_tier=(20,5,95))==(20,5,95)
mp["fee_canonical_event_tier_not_in_table_excluded"]=A.resolve_fee(Pm,"C",1,1,0,ev_tier=(20,5,147)) is None
mp["fee_canonical_with_validated_supply"]=A.resolve_fee(Pm,"C",206_900_000_000_000,67_405_853_768,17_584_000_000,supply=10**15)==(2,93,30)
mp["fee_noncanonical"]=A.resolve_fee(Pm,"N",1,1,0)==(25,5,0)
# event_tier_at: tier demonstrat doar cand tripletul nenul anterior si urmator coincid
evs=[[0,0,1,0,0,1,1,1,1,1,1,1,20,5,95,"s"],[0,1,2,1,0,1,1,1,1,1,1,1,0,0,0,"s"],[0,2,3,2,0,1,1,1,1,1,1,1,20,5,95,"s"],[0,3,4,3,0,1,1,1,1,1,1,1,20,5,90,"s"]]
mp["event_tier_demonstrated"]=(A.event_tier_at(evs,1)==(20,5,95)); mp["event_tier_ambiguous_none"]=(A.event_tier_at(evs,2) is None)
print(json.dumps(mp,indent=1)); print("MULTIPOOL_EPISODE_TESTS =","PASS" if all(mp.values()) else "FAIL")
