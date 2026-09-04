# EXTERNAL DEEP-ANALYSIS PACKAGE — PumpSwap BOOST migrations, 2026-09-01..04 (generated 2026-09-04 12:22 UTC)

Label: POST_HOC_HISTORICAL_EXPLORATION. Nothing here is prospective. No live trading. Regime verdict: **REGIME_GATE_INSUFFICIENT_SAMPLE**.

## Source data (not included; hashes in code/regime_gate_frozen_spec.json and integrity_checks.json)
- SEP01: Helius backfill of pump.fun (full day, exact slot/txIndex ordering) + 735 PumpSwap pool tapes from vault balances (post-tx reserves). No wallet identity in pools. Fees = tier table by market cap (code/pumpswap_fees.py).
- SEP02 13:18 → SEP04 08:01 (local, UTC+3): one WebSocket logsSubscribe on pump.fun + PumpSwap. Buy/SellEvent carry PRE-trade reserves (post = next pre validated on 99.98 % of pairs), on-chain ts (1 s), slot, no transactionIndex. Wallets present. Fees = observed lp/protocol/creator bps per event.
- Coverage: {"2026-09-01": 586, "2026-09-02": 283, "2026-09-03": 571, "2026-09-04": 119} eligible pools by UTC day; 22 WebSocket disconnection windows (longest 09-03 02:13–02:51 local) and 2 truncated gz tails; pools whose required interval [Complete, creation+420 s] intersects them are excluded (see pool_master.exclusion_reason).
- SOL/USD fixed at 100 (no price series for 09-02..04; PnL % invariant). Priority fee 0.0001 SOL/tx (2 tx). NOT modeled: failed transactions, Jito/MEV, fill probability (FRICTION = INCOMPLETE_UPPER_BOUND).

## Population
Canonical BOOST_PROXY_17_58 migrations: initial state 206,900,000 tokens + 84.99 SOL total (67.41 real + 17.58 virtual), implied virtual quote 17.58±0.3 SOL, quote = SOL. Eligible: 1559 ({"SEP01_HIST24_VAULT_BALANCES": 586, "PROSPECTIVE_TAPE_EVENTS": 973}). Excluded pools are listed with reasons (SEP02-04); SEP01 exclusions are counts only (integrity_checks.json → source_hashes.regime_cache.exclusions).

## Identifiers
pool_id / mint_id / wallet_id = sha256("external-review-v1:" + base58_address).hexdigest()[:32]. Deterministic, joinable across files, not invertible. For the 14 completions without an observed pool creation, pool_id = sha256("external-review-v1:NOPOOL:" + mint)[:32]. No raw addresses, keys, tokens or environment values are included (validate_bundle.py scans for them).

## Execution model (protocol-exact, integer math)
Buy: q_net = q·10000/(10000+lp+protocol+creator); tokens = rb·q_net/(rq+vq+q_net); pool gets q_net + lp_fee. Sell: gross = (rq+vq)·b/(rb+b); user gets gross − lp − protocol − creator (bps of gross), capped by real quote reserve. Position overlay: subsequent states use (rb − tokens, rq + q_in). CONSERVATIVE ordering = state after ALL events with ts ≤ X (events in the same second are assumed before us; our tx lands in a later slot); TP/SL evaluated at end-of-slot states; SL first when both hit in one slot. OPTIMISTIC = state after events with ts < X, TP first.

## Files
| file | rows | key | content |
|---|---|---|---|
| pool_master.csv.gz | 2514 (1559 eligible + 955 excluded) | pool_id | one row per migration (SEP01 eligible + SEP02-04 all observed completions with pool) |
| pool_feature_panel.csv.gz | 6236 | pool_id × horizon_s | point-in-time features at decision = creation + h (5/10/20/30 s); features exist only for the 946 pools of the master population (CreateEvent in tape + wallets); others have features_available = 0 with reason |
| pool_outcomes.csv.gz | 6236 | pool_id × horizon_s | exact outcomes at entry = decision + 2 s for TP100/SL30/300, TP50/SL20/300, FIX60, FIX180 (+ cost, ordering, latency stress). All OUT_* columns are FUTURE OUTCOMES |
| shadow_trade_ledger.csv.gz | 1559 | pool_id | frozen shadow policy (Complete+7 s, $25, TP $50 / SL $17.50 / 300 s) with SHADOW_RESOLUTION_TIME |
| regime_blocks.csv | 308 | decision_ts | 15-min UTC blocks: gate inputs (only resolved shadows entered in [B−60 min, B)), ON/OFF, selection, separated OUTCOME_ columns |
| regime_executed_trades.csv | 5 | block | paper trades in ON blocks, with bankroll 100/500/2000 ledgers |
| hourly_daily_summary.csv | – | utc | shadow metrics per UTC hour and day, regime state, coverage |
| model_and_rule_trials.csv | 16 | – | complete master trial ledger (incl. losing trials) |
| casebook.jsonl.gz | 110 | – | deterministic cases with compact event paths (rel_ts, slot, side, quote, tokens, reserves, exact liquidation of a $25 position, wallet_id, cohort label at that time) |
| integrity_checks.json | – | – | counts, duplicates, missingness, timestamp violations, joins, reserve consistency, exclusions, source hashes, leakage tests |
| headline_metrics.json | – | – | headline numbers reproduced by validate_bundle.py |
| data_dictionary.csv | – | – | every exported column |
| code/ | – | – | regime_gate.py, regime_cache_build.py, regime_exclusions_pass.py, master_edge_build_m_cache.py, master_edge_discovery.py (feature definitions + engine), master_leakage_tests.py, build_external_bundle.py, pumpswap_fees.py, frozen spec, results, feature registry |
| validate_bundle.py | – | – | run: `python validate_bundle.py .` → BUNDLE_VALIDATION = PASS |

Row-count differences: pool_master = eligibile + excluse (cu motiv); feature_panel/outcomes = eligibile x 4 orizonturi; trasaturile exista doar pentru pool-urile din populatia master (946: cu CreateEvent in banda si portofele); SEP01 nu are portofele in pool tapes => fara trasaturi de cohorta; shadow_ledger = eligibile cu shadow executabil

## Headline (reproducible from exported data)
- Unconditional shadow (F): N 1559, EV $-0.343, PF 0.910, median $0.41.
- Regime: 308 blocks, 5 ON (1.6%), ON trades 5, ON EV $-3.203, OFF EV $-0.404, every-block EV $-0.458.
- Bankroll $100 end: $97.78.

## Reproduction
1. `python validate_bundle.py .` (schemas, joins, timestamps, secrets scan, headline reproduction, gate recomputation from exported inputs).
2. Recompute the regime: from shadow_trade_ledger.csv.gz build 15-min UTC blocks; for each block use rows with shadow_entry_ts in [B−3600, B) and SHADOW_RESOLUTION_TIME < B; apply the 7 gate conditions (spec in code/regime_gate_frozen_spec.json); compare with regime_blocks.csv.
3. Alternative rules: join pool_feature_panel (features, PIT) with pool_outcomes (OUT_*) on (pool_id, horizon_s); respect partition_master for any model fitting; never use OUT_* or SHADOW_* columns as features.
4. Exact PnL: casebook paths contain reserves per event; the formulas above (code/regime_gate.py exec_buy/exec_sell) reproduce liquidation values bit-exactly.

## Limitations
Single 4-day regime; no transactionIndex on SEP02-04 (conservative ordering); SEP01 has no wallet identity; raw wallet addresses (hashed) are not independent entities (coordination blind); fee tiers on SEP01 are modeled, not observed; no failed-tx / MEV / fill modeling; +60 s outcomes of the 946-pool population were seen in aggregate in an earlier sealed evaluation.
