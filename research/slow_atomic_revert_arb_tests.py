"""Teste comportamentale SLOW_ATOMIC_REVERT_ARB pe date SINTETICE (fara date reale, fara PnL istoric): motorul apeleaza selectia pe episoade la nivel de token,
consuma populatia secundara inghetata, un token cu 3 pool-uri / 6 rute produce cel mult o tranzactie per episod, orientarea inversa nu creeaza duplicate, nicio stare viitoare nu participa la selectie."""
import sys,json,copy,os,tempfile; sys.path.insert(0,'research'); import atomic_same_mint_arb as A
WSOL=A.WSOL; res={}
SPEC=dict(status="FROZEN_NOT_EXECUTED",notional_sol=0.25,landing=dict(primary_slots=3,stress_slots=5),costs=dict(base_signature_fee_lamports=5000,priority_fee_lamports=100000),gates=dict(episodes_min=50,tokens_min=5,PF_min=1.5,positive_days_min=2,token_share_max=0.4))
def pool_events(rq_path,rb0=10**12,slot0=100,t0=1788400000.0):
    """genereaza evenimente consistente CP (vq=0, taxe 25/5/0): la fiecare slot o cumparare mica, apoi rezerva de quote 'setata' prin evenimente de vanzare/cumparare consistente cu lantul."""
    ev=[]; rb=rb0; rq=rq_path[0]; seq=0
    for i,target in enumerate(rq_path):
        # aducem rq la target printr-un eveniment consistent (buy daca target>rq, sell altfel), pastrand lantul post==pre urmator
        s=slot0+i; t=t0+0.4*i
        if target>=rq:
            q3=target-rq; lpf=q3*25//10000; cp=q3-lpf; tok=rb*cp//(rq+cp) if cp>0 else 0
            ev.append([t,int(t),s,seq,0,1,rb,rq,rb-tok,target,tok,cp,25,5,0,"sig"]); rb-=tok; rq=target
        else:
            q3=rq-target; lpf=q3*25//10000; cp=q3+lpf; b=cp*rb//(rq-cp) if rq>cp else 1
            ev.append([t,int(t),s,seq,0,0,rb,rq,rb+b,target,b,cp,25,5,0,"sig"]); rb+=b; rq=target
        seq+=1
    return ev
base=[50_000_000_000]*12                            # pret constant (B este dimensionat EXACT la bugetul Q din starea de decizie: orice scumpire a pool-ului de cumparare => REVERTED_MAX_QUOTE)
high=[62_000_000_000]*12                            # pool "scump": +24 %
warm=[50_000_000_000+i*10_000 for i in range(5)]+[50_000_000_000]   # 6 evenimente de incalzire (VQ cere >=5 observatii INAINTE de decizie): sloturi 100..105; scenariul incepe la 106
tail=[50_000_000_000]*8                              # coada de ancorare: starile de landing (pana la s+5) trebuie urmate de un eveniment cu pre==post
meta={"P1":dict(orientation="STRICT",canonical=False,base_mint="TOK",quote_mint=WSOL),"P2":dict(orientation="STRICT",canonical=False,base_mint="TOK",quote_mint=WSOL),"P3":dict(orientation="STRICT",canonical=False,base_mint="TOK",quote_mint=WSOL),"PR":dict(orientation="REVERSED",canonical=False,base_mint=WSOL,quote_mint="TOK")}
events={"P1":pool_events(warm+base+tail),"P2":pool_events(warm+high+tail),"P3":pool_events(warm+[55_000_000_000+i*10_000 for i in range(12)]+tail),"PR":pool_events(warm+high+tail)}   # dislocare persistenta 106..117, apoi coada
# (a) selectia pe episoade e apelata de motor (spy) si primeste rute pentru fiecare slot
calls=[]
def spy(by_slot): calls.append(copy.deepcopy(by_slot)); return A.token_episode_selection(by_slot)
r=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),events,SPEC,selector=spy)
res["engine_invokes_token_episode_selection"]=(len(calls)==1 and len(calls[0])>0 and all(len(x[1])<=6 for x in calls[0]))
res["routes_are_6_for_3_pools"]=max(len(x[1]) for x in calls[0])==6
# (b) dislocare persistenta pe 12 sloturi => cel mult o tranzactie per episod (nu 12, nu 6 rute x 12 sloturi)
res["at_most_one_trade_per_episode"]=(len(r["rows"])==1 and r["episodes"]==1)
# (c) dupa ce toate rutele revin la <=0 si dislocarea reapare => al doilea episod
ev2={"P1":pool_events(warm+base+base+base),"P2":pool_events(warm+high[:6]+base[:6]+high[:6]+tail+tail),"P3":pool_events(warm+base+base+base)}   # in faza de mijloc TOATE rutele revin la <=0
r2=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev2,SPEC); res["second_episode_after_reset"]=(r2["episodes"]==2 and len({x["episode_id"] for x in r2["rows"]})==2)
# (d) orientarea inversa nu creeaza duplicate: adaugarea pool-ului PR (reversed) nu schimba numarul de tranzactii si este marcata ca incalcare
r3=A.run_engine({"TOK":["P1","P2","P3","PR"]},copy.deepcopy(meta),events,SPEC); res["reversed_pool_excluded_no_duplicates"]=(len(r3["rows"])==len(r["rows"]) and r3["violations"].get("ORIENTATION_VIOLATION")==1)
# (e) fara lookahead: decizia nu vede starea viitoare. P2 devine scump doar de la slotul 104 (landing), la decizie (<=103) nu exista dislocare => nicio tranzactie pana la 104
ev4={"P1":pool_events(warm+base+tail),"P2":pool_events(warm+base[:4]+high[4:]+tail),"P3":pool_events(warm+base+tail)}   # P2 devine scump doar de la slotul 110
r4=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev4,SPEC); res["no_lookahead_first_trade_at_or_after_dislocation_slot"]=(all(x["decision_slot"]>=110 for x in r4["rows"]) and len(r4["rows"])>=1)
# predicted-ul vine doar din starea de decizie: reconstruim manual pentru tranzactia din (b)
row=r["rows"][0]; s=row["decision_slot"]; a,b=row["route"].split(">"); st=A.state_after_slot(events[a],s); sb=A.state_after_slot(events[b],s); m=copy.deepcopy(meta); vqa=int(A.implied_vq(events[a][:st[2]+1])[0]); vqb=int(A.implied_vq(events[b][:sb[2]+1])[0])   # VQ doar din evenimentele <= decizie, ca in motor
pr=A.arb(m,a,st[:2],vqa,b,sb[:2],vqb,int(0.25e9)); res["predicted_from_decision_state_only"]=abs(pr["out"]-int(0.25e9)-105000-round(row["predicted_net_sol"]*1e9))<=2
# starea viitoare (s+3) modificata artificial NU schimba predicted-ul: rulam din nou cu P2 prabusit dupa decizie si comparam predicted
ev6={"P1":events["P1"],"P2":pool_events(warm+high[:1]+base[1:]+tail),"P3":events["P3"]}; r6=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev6,SPEC)   # identic pana la decizia 106, diferit dupa
res["future_state_does_not_change_predicted"]=(len(r6["rows"])==1 and abs(r6["rows"][0]["predicted_net_sol"]-row["predicted_net_sol"])<1e-12 and r6["rows"][0]["decision_slot"]==row["decision_slot"])
# realized-ul vine din landing (s+3), nu din decizie: cu preturi constante dupa decizie, realized ~ predicted; cu P2 prabusit la s+3, realized = revert
ev5={"P1":pool_events(warm+base+tail),"P2":pool_events(warm+high[:1]+base[1:]+tail),"P3":pool_events(warm+base+tail)}
r5=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev5,SPEC); res["revert_model_applied_when_landing_fails_guard"]=(len(r5["rows"])==1 and r5["rows"][0]["landing_primary_status"]=="REVERTED_MIN_OUT" and abs(r5["rows"][0]["realized_primary_sol"]+0.000105)<1e-9)
# (f) motorul consuma populatia secundara inghetata: loader-ul citeste SECONDARY din fisierul inghetat; pool-urile din afara populatiei nu sunt tranzactionate
tmp=tempfile.mkdtemp(); popf=os.path.join(tmp,"pop.json"); json.dump(dict(frozen_at="x",inputs={},rule="r",PRIMARY_MEME=dict(tokens={"TOK":dict(pools=["P1","P2"])},combos=[]),SECONDARY_ALL_NONCANONICAL=dict(tokens={"TOK":dict(pools=["P1","P2","P3"])},combos=[])),open(popf,"w"))
pop=A.load_frozen_secondary(popf); res["loader_reads_secondary_not_primary"]=(pop["tokens"]=={"TOK":["P1","P2","P3"]})
loaders=dict(pop=lambda:A.load_frozen_secondary(popf),meta=lambda:copy.deepcopy(meta),events=lambda:events,spec=lambda:dict(SPEC,status="FROZEN_NOT_EXECUTED"),outages=lambda:[],truncated=lambda:[],mints=lambda:{"TOK":dict(status="SPL_TOKEN",initialized=True)})
rr,ev_=A.stage_run_slow(dry_run=True,_loaders=loaders); res["stage_run_slow_uses_frozen_population_and_engine"]=(len(rr["rows"])==1 and rr["selector_calls"]==1)
# ===== V2: semantica standard PumpSwap, mint map, ancore, landing worst-case =====
row=r["rows"][0]
res["v2_exact_B_bought_equals_B_sold"]=(row["base_amount_exact"]>0 and row["residual_inventory"]==0 and row["primary_quote_spent"] is not None and row["primary_quote_spent"]<=row["max_quote_in"])
body=open("research/atomic_same_mint_arb.py").read().split("def run_engine(")[1].split("\ndef ")[0]
res["v2_no_variable_output_router"]=("exec_buy(" not in body and "buy_exact_out(" in body and "max_base_for_budget(" in body and "min_quote_out" in body)
# max_quote insuficient => revert atomic: P1 (pool de cumparare) se scumpeste cu 40 % de la slotul 107 (landing 109)
ev7={"P1":pool_events(warm+base[:1]+[70_000_000_000]*11+tail),"P2":pool_events(warm+high+tail),"P3":pool_events(warm+high+tail)}   # singurul pool ieftin la decizie este P1; la landing P1 s-a scumpit => quote necesar > Q
r7=A.run_engine({"TOK":["TOK"] and {"TOK":["P1","P2","P3"]}}["TOK"] if False else {"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev7,SPEC)
res["v2_insufficient_max_quote_reverts"]=(len(r7["rows"])>=1 and r7["rows"][0]["landing_primary_status"]=="REVERTED_MAX_QUOTE" and abs(r7["rows"][0]["realized_primary_sol"]+0.000105)<1e-9)
res["v2_min_quote_failure_reverts"]=res["revert_model_applied_when_landing_fails_guard"]
# landing pre/post worst-case: P2 inca scump la s+2 (pre-landing) dar prabusit exact la s+3 => primar = revert (cazul mai defavorabil)
ev8={"P1":pool_events(warm+base+tail),"P2":pool_events(warm+high[:3]+base[3:]+tail),"P3":pool_events(warm+base+tail)}
r8=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev8,SPEC)
res["v2_landing_slot_worst_case_used"]=(len(r8["rows"])>=1 and r8["rows"][0]["decision_slot"]==106 and r8["rows"][0]["landing_primary_status"]=="REVERTED_MIN_OUT")
# ruptura de lant ascunsa (Deposit/Withdraw neobservat) la P2 imediat dupa decizie => nicio candidatura la 106 (starea de decizie nu e ancorata)
ev9=copy.deepcopy(events); ev9["P2"][7][6]+=10**9   # pre-starea evenimentului 7 (slot 107) nu mai coincide cu post-starea lui 6 => ev[6] neancorat
r9=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev9,SPEC)
res["v2_hidden_liquidity_change_no_candidate_at_break"]=all(not (x["decision_slot"]==106 and "P2" in x["route"]) for x in r9["rows"]) and any("P2" in x["route"] and x["decision_slot"]==106 for x in r["rows"])   # fara ruptura P2 era selectat la 106; cu ruptura ascunsa nu mai poate fi candidat
# coada neancorata: decizia la ultimul eveniment al unui pool nu este candidat; pool cu doar warm+high fara coada => ultimul slot exclus
ev10={"P1":pool_events(warm+base),"P2":pool_events(warm+high),"P3":pool_events(warm+base)}
r10=A.run_engine({"TOK":["P1","P2","P3"]},copy.deepcopy(meta),ev10,SPEC)
res["v2_unanchored_tail_excluded"]=all(x["decision_slot"]<117 for x in r10["rows"])
# mint map consumat de runner: TOKEN_2022 / owner necunoscut / neinitializat NU ajung in run_engine; SPL_TOKEN initializat ajunge; harta lipsa => SystemExit
seen=[]; orig=A.run_engine
def spy_engine(population,*a,**k): seen.append(dict(population)); return orig(population,*a,**k)
A.run_engine=spy_engine
def mk_loaders(mm): return dict(pop=lambda:A.load_frozen_secondary(popf),meta=lambda:copy.deepcopy(meta),events=lambda:events,spec=lambda:dict(SPEC,status="FROZEN_NOT_EXECUTED"),outages=lambda:[],truncated=lambda:[],mints=lambda:mm)
A.stage_run_slow(dry_run=True,_loaders=mk_loaders({"TOK":dict(status="TOKEN_2022_EXCLUDED",initialized=True)})); A.stage_run_slow(dry_run=True,_loaders=mk_loaders({"TOK":dict(status="UNKNOWN_OWNER_EXCLUDED",initialized=True)})); A.stage_run_slow(dry_run=True,_loaders=mk_loaders({"TOK":dict(status="SPL_TOKEN",initialized=False)})); A.stage_run_slow(dry_run=True,_loaders=mk_loaders({}))
rr2,_=A.stage_run_slow(dry_run=True,_loaders=mk_loaders({"TOK":dict(status="SPL_TOKEN",initialized=True,mint_authority_present=False,freeze_authority_present=False,decimals=6,supply=10**15)}))
res["v2_excluded_mints_never_reach_engine"]=(seen[0]=={} and seen[1]=={} and seen[2]=={} and seen[3]=={} and "TOK" in seen[4] and rr2["executable_input_manifest"]["tokens_allowed"]==1 and rr2["executable_input_manifest"]["tokens_excluded"]=={} )
try: A.stage_run_slow(dry_run=True,_loaders=dict(mk_loaders({}),mints=lambda:None)); res["v2_missing_mint_map_stops"]=False
except SystemExit: res["v2_missing_mint_map_stops"]=True
A.run_engine=orig
res["v2_n_routes_available_actual"]=(row["n_routes_available"]>=2)
res["old_stage_run_closed"]=True
try: A.stage_run(); res["old_stage_run_closed"]=False
except SystemExit: pass
res["pair_combinations_not_independent_observations"]=(r["episodes"]==1)
print(json.dumps(res,indent=1)); print("SLOW_ARB_BEHAVIORAL_TESTS =","PASS" if all(res.values()) else "FAIL")
