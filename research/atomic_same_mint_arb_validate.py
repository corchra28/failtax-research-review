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
