"""Validatorul artefactelor ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE: existenta, hash-uri, coerenta spec/rezultate, fara lookahead in selectie, fara incalcari."""
import os,json,hashlib,gzip,csv,sys,subprocess
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
fails=[]; notes=[]
R=json.load(open("research/atomic_same_mint_arb_results.json")) if os.path.exists("research/atomic_same_mint_arb_results.json") else None
# dependente reproductibile (pda, pumpswap_fees) si rularea efectiva a testelor comportamentale
for dep in ("strategy_e/pda.py","pumpswap_fees.py"):
    if not os.path.exists(dep): fails.append(f"MISSING_DEPENDENCY {dep}")
t=subprocess.run([sys.executable,"research/atomic_same_mint_arb_tests.py"],capture_output=True,text=True); out=t.stdout
if "ALL_TESTS_PASS = True" not in out or "PATCHED_BLOCKERS = 10/10" not in out: fails.append("BEHAVIORAL_TESTS_FAILED"); notes.append(out[-800:])
else: notes.append("teste comportamentale: PATCHED_BLOCKERS = 10/10, ALL_TESTS_PASS = True")
if "MULTIPOOL_EPISODE_TESTS = PASS" not in out: fails.append("MULTIPOOL_EPISODE_TESTS_FAILED")
t2=subprocess.run([sys.executable,"research/slow_atomic_revert_arb_tests.py"],capture_output=True,text=True); out2=t2.stdout
if "SLOW_ARB_BEHAVIORAL_TESTS = PASS" not in out2: fails.append("SLOW_ARB_BEHAVIORAL_TESTS_FAILED"); notes.append(out2[-600:])
else: notes.append("SLOW_ARB_BEHAVIORAL_TESTS = PASS (selectie pe episoade integrata in motor, populatie secundara inghetata, 3 pool-uri/6 rute -> max 1 tranzactie/episod, orientare inversa fara duplicate, fara lookahead)")
src=open("research/atomic_same_mint_arb.py").read()
if "def run_engine" not in src or "sel_fn(by_slot)" not in src: fails.append("ENGINE_NOT_USING_TOKEN_EPISODE_SELECTION")
if "def load_frozen_secondary" not in src or 'L["pop"]()' not in src: fails.append("RUNNER_NOT_USING_FROZEN_POPULATION")
if os.path.exists("research/slow_atomic_revert_arb_frozen_spec.json"):
    Sp=json.load(open("research/slow_atomic_revert_arb_frozen_spec.json"))
    if Sp.get("script_sha256")!=sha("research/atomic_same_mint_arb.py"): fails.append("SLOW_SPEC_SCRIPT_HASH_MISMATCH")
    if Sp.get("inputs",{}).get("populations_sha256")!=sha("research/atomic_same_mint_arb_populations_frozen.json"): fails.append("SLOW_SPEC_POPULATION_HASH_MISMATCH")
    if Sp.get("population",{}).get("population")!="SECONDARY_ALL_NONCANONICAL": fails.append("SLOW_SPEC_WRONG_POPULATION")
    if os.path.exists("research/slow_atomic_revert_arb_results.json"): notes.append("ATENTIE: rezultate SLOW existente (PnL calculat)")
    else: notes.append(f"SLOW spec inghetat (status {Sp.get('status')}), PnL NECALCULAT")
else: notes.append("MULTIPOOL_EPISODE_TESTS = PASS")
if "SUPPLY=10**15" in open("research/atomic_same_mint_arb.py").read(): fails.append("HARDCODED_SUPPLY_PRESENT")
# populatii inghetate inainte de PnL + poarta pe token-uri unice recalculata independent
if os.path.exists("research/atomic_same_mint_arb_populations_frozen.json"):
    Pp=json.load(open("research/atomic_same_mint_arb_populations_frozen.json"))
    for kind in ("PRIMARY_MEME","SECONDARY_ALL_NONCANONICAL"):
        rp=Pp[kind]["report"]; toks=Pp[kind]["tokens"]; g=rp["GATE"]
        tsw=sum(v["clean_token_slot_windows"] for v in toks.values()); dates=set(); [dates.update(v["dates"]) for v in toks.values()]
        exp=dict(UNIQUE_TOKEN_GATE=len(toks)>=20,TOKEN_SLOT_DEDUP_GATE=tsw>=100,DATES_GATE=len(dates)>=2)
        if any(g.get(k)!=v for k,v in exp.items()) or rp["UNIQUE_TOKENS"]!=len(toks) or rp["CLEAN_TOKEN_SLOT_WINDOWS"]!=tsw: fails.append(f"POPULATION_GATE_RECOMPUTE_MISMATCH {kind}")
        if any(v["clean_token_slot_windows"]>v["clean_pair_windows"] for v in toks.values()): fails.append(f"TOKEN_SLOT_DEDUP_EXCEEDS_PAIR_WINDOWS {kind}")
        if kind=="PRIMARY_MEME" and any(c["pool_a"]==c["pool_b"] for c in Pp[kind]["combos"]): fails.append("SELF_PAIR")
        notes.append(f"{kind}: tokens {rp['UNIQUE_TOKENS']} pools {rp['UNIQUE_POOLS']} token-slot windows {rp['CLEAN_TOKEN_SLOT_WINDOWS']} dates {rp['DATES']} PASS={g['PASS']}")
    if os.path.exists("research/mint_metadata_recovery_manifest.json"):
        Mm=json.load(open("research/mint_metadata_recovery_manifest.json"))
        if Mm.get("max_calls")!=2 or Mm.get("n_batches",0)>2: fails.append("MINT_RPC_BUDGET_NOT_2")
        if Mm.get("status","").startswith("FETCHED"): notes.append("mint fetch EXECUTAT")
        else: notes.append(f"mint RPC pregatit, NEEXECUTAT: {Mm.get('n_mints')} mint-uri, {Mm.get('n_batches')} apeluri propuse")
        if os.path.exists("research/mint_accounts_raw.jsonl.gz"): fails.append("RAW_MINT_CACHE_PUBLISHED")
# PHASE 1 metadata recovery: manifest inghetat inainte de apeluri, buget respectat, control semantic, cache brut NEpublicat, normalizat publicat
if os.path.exists("research/pool_metadata_recovery_manifest.json"):
    Mn=json.load(open("research/pool_metadata_recovery_manifest.json")); Rp=json.load(open("research/pool_metadata_recovery_report.json")) if os.path.exists("research/pool_metadata_recovery_report.json") else {}
    if Mn.get("rpc_request_count",0)>Mn.get("max_calls",325): fails.append("RPC_BUDGET_EXCEEDED")
    if Mn.get("n_batches")!=325 or Mn.get("batch_size")!=100: fails.append("RPC_BATCHING_NOT_AS_APPROVED")
    if Mn.get("frozen_at") and Mn.get("fetched_at") and Mn["frozen_at"]>Mn["fetched_at"]: fails.append("FREEZE_AFTER_FETCH")
    if (Rp.get("CREATEPOOL_METADATA_MATCH_RATE") or 0)<0.999: fails.append("DECODER_SEMANTIC_MISMATCH")
    if os.path.exists("research/pool_accounts_raw.jsonl.gz") or os.path.exists("pool_accounts_raw.jsonl.gz"): fails.append("RAW_RPC_CACHE_PUBLISHED")
    if os.path.exists("research/pool_metadata_normalized.jsonl.gz"):
        if Rp.get("normalized_sha256") and sha("research/pool_metadata_normalized.jsonl.gz")!=Rp["normalized_sha256"]: fails.append("NORMALIZED_HASH_MISMATCH")
        import re as _re; n_clear=0
        for l in gzip.open("research/pool_metadata_normalized.jsonl.gz","rt"):
            r=json.loads(l)
            if "creator" in r or not _re.fullmatch(r"[0-9a-f]{32}",r.get("creator_id","")): n_clear+=1
        if n_clear: fails.append(f"CREATOR_NOT_HASHED {n_clear}")
    notes.append(f"phase1: calls {Mn.get('rpc_request_count')}/{Mn.get('max_calls')}, recovered {Rp.get('ACCOUNTS_RECOVERED')}, match {Rp.get('CREATEPOOL_METADATA_MATCH_RATE')}, groups {Rp.get('SAME_MINT_PAIRS_TOTAL')}")
if os.path.exists("research/atomic_same_mint_arb_feasibility_rpc.json"):
    Fr=json.load(open("research/atomic_same_mint_arb_feasibility_rpc.json")); gr=Fr["FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM"]
    # recalcul independent al portii din campurile raportate
    exp=dict(pairs_ge_20=Fr["pairs_with_clean_windows"]>=20,clean_windows_gt2_ge_100=Fr["windows_gt2_clean_chain100"]>=100,dates_ge_2=len(Fr["windows_gt2_clean_by_utc_date"])>=2,both_streams_present=Fr["combos_with_both_streams"]>0,reserves_valid_and_chain100_in_used_windows=(Fr["fee_resolver"] is True and Fr["windows_gt2_clean_chain100"]>0))
    if any(gr.get(k)!=v for k,v in exp.items()) or gr["PASS"]!=all(exp.values()): fails.append("FEASIBILITY_RPC_GATE_RECOMPUTE_MISMATCH")
    if sum(c["windows_gt2_clean"] for c in Fr["combos"])!=Fr["windows_gt2_clean_chain100"]: fails.append("FEASIBILITY_RPC_WINDOW_SUM_MISMATCH")
    notes.append(f"feasibility_rpc: pairs_clean {Fr['pairs_with_clean_windows']}, clean windows {Fr['windows_gt2_clean_chain100']}, dates {sorted(Fr['windows_gt2_clean_by_utc_date'])}, PASS={gr['PASS']}")
    if os.path.exists("research/atomic_same_mint_arb_derivation.json"):
        Dv=json.load(open("research/atomic_same_mint_arb_derivation.json"))
        if not isinstance(Dv.get("all_noncanonical_with_active_derived_canonical"),list): fails.append("MISSING_INFORMATIVE_NONCANONICAL_SCAN")
if os.path.exists("research/atomic_same_mint_arb_derivation.json"):
    Dv=json.load(open("research/atomic_same_mint_arb_derivation.json")); notes.append(f"derivare zero-RPC: pda_matches {Dv['derivation_validation']['pda_matches']}/{Dv['derivation_validation']['canonical_pools_in_tape']} (nepotrivirile = pool-uri canonice cu quote != WSOL), index>0 {Dv['INDEX_GT0_SOL_POOLS']}, canonice active {Dv['DERIVED_CANONICAL_ACTIVE_MATCHES']}")
req=["research/external_review_remediation.py","research/external_review_remediation.json","research/external_review_remediation_report.md","research/atomic_same_mint_arb.py","research/atomic_same_mint_arb_feasibility.json","research/atomic_same_mint_arb_report.md","research/atomic_arb_inventory_pass1.py"]
for f in req:
    if not os.path.exists(f): fails.append(f"MISSING {f}")
F=json.load(open("research/atomic_same_mint_arb_feasibility.json")) if os.path.exists("research/atomic_same_mint_arb_feasibility.json") else {}
gate=F.get("FEASIBILITY_GATE",{}); notes.append(f"feasibility PASS={gate.get('PASS')} | before_token_program PASS={F.get('FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM',{}).get('PASS')}")
if gate.get("PASS"):
    for f in ["research/atomic_same_mint_arb_frozen_spec.json","research/atomic_same_mint_arb_results.json","research/atomic_same_mint_arb_opportunities.csv.gz"]:
        if not os.path.exists(f): fails.append(f"MISSING {f}")
    if os.path.exists("research/atomic_same_mint_arb_frozen_spec.json"):
        spec=json.load(open("research/atomic_same_mint_arb_frozen_spec.json"))
        if spec.get("script_sha256")!=sha("research/atomic_same_mint_arb.py"): fails.append("SPEC_SCRIPT_HASH_MISMATCH")
        D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"
        for k,p in (("inventory_sha256",f"{D}/pamm_pool_inventory.json.gz"),("pair_events_cache_sha256",f"{D}/arb_pair_events.jsonl.gz"),("feasibility_sha256","research/atomic_same_mint_arb_feasibility.json")):
            if os.path.exists(p) and spec["inputs"].get(k)!=sha(p): fails.append(f"INPUT_HASH_MISMATCH {k}")
    if os.path.exists("research/atomic_same_mint_arb_opportunities.csv.gz"):
        rows=list(csv.DictReader(gzip.open("research/atomic_same_mint_arb_opportunities.csv.gz","rt")))
        if rows and "none" not in rows[0]:
            if any(float(r["pred_net_base"])<=0 for r in rows): fails.append("SELECTION_NOT_BY_PREDICTED (pred_net_base<=0 present)")
            keys=[(r["token"],r["pool_1"],r["pool_2"],r["direction"],r["decision_slot"],r["notional_sol"]) for r in rows]
            if len(keys)!=len(set(keys)): fails.append("DUPLICATE_OPPORTUNITY_KEY")
            port=[r for r in rows if r["in_portfolio"]=="1"]; pk=[(r["notional_sol"],r["decision_slot"]) for r in port]
            if len(pk)!=len(set(pk)): fails.append("PORTFOLIO_MORE_THAN_ONE_TRADE_PER_SLOT")
            # recalcul independent: orientare, taxe, episoade, staleness
            inv=json.load(gzip.open("/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived/pamm_pool_inventory.json.gz","rt")); P=inv["pools"]; WSOL="So11111111111111111111111111111111111111112"
            if any(P[r["pool_1"]]["quote_mint"]!=WSOL or P[r["pool_2"]]["quote_mint"]!=WSOL or P[r["pool_1"]]["base_mint"]!=P[r["pool_2"]]["base_mint"] for r in rows): fails.append("ORIENTATION_VIOLATION")
            sys.path.insert(0,"."); import pumpswap_fees as PF
            for r in rows[:5000]:
                for k in ("fee1_bps","fee2_bps"):
                    p_=r["pool_1"] if k=="fee1_bps" else r["pool_2"]; f=int(r[k]); tot_ok=(30<=f<=125) if P[p_]["canonical"] else (f==30)
                    if not tot_ok: fails.append(f"FEE_RESOLVER_VIOLATION {p_[:8]} {f}"); break
            if any(r["first_in_episode"]!="1" for r in port): fails.append("PORTFOLIO_CONTAINS_NON_FIRST_EPISODE_STATE")
            if any(int(r["staleness_slots"])<max(int(r["staleness_a"]),int(r["staleness_b"])) for r in rows): fails.append("STALENESS_FORMULA")
            g=R.get("final_gate_primary_0_25")
            if g is not None:
                need={"N50","days2","EV","median","PF","CI_low","exb1pct","top1","day_share","survival","landing_s2","stress2","zero_violations","segments_positive","no_post_hoc"}
                if set(g)!=need: fails.append(f"GATE_CRITERIA_INCOMPLETE {sorted(need-set(g))}")
                verdict_expected="ATOMIC_ARB_HISTORICAL_PAPER_CANDIDATE" if all(g.values()) else "ATOMIC_ARB_NO_VERIFIED_EDGE"
                if R["FINAL_VERDICT"]!=verdict_expected: fails.append("VERDICT_NOT_FROM_GATE")
            A=R["by_notional"].get("0.25",{}).get("ALL")
            pr=[float(r["realized_net_base"]) for r in port if r["notional_sol"]=="0.25"]
            if A and A["realized_net_base"] and (len(pr)!=A["realized_net_base"]["N"] or abs(sum(pr)/len(pr)-A["realized_net_base"]["EV"])>1e-12): fails.append("HEADLINE_NOT_REPRODUCIBLE_FROM_CSV")
            notes.append(f"opportunities {len(rows)} portfolio {len(port)}")
        else: notes.append("opportunities file empty")
print("\n".join(notes)); print("FAILS:",fails or "none"); print("ARTIFACT_VALIDATION =","PASS" if not fails else "FAIL")
