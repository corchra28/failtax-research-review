# OVERNIGHT RESEARCH 2026-09-05 — RAPORT FINAL (POST_HOC_HISTORICAL_RESEARCH)

Commit: acabf9b655b10d438273242b5efaa264154e12e3. Fara Helius/RPC/API/WSS, fara colectoare, fara date noi, fara live. Partitie imutabila: DEV 09-02 / VAL 09-03 / CONF 09-04 (zile UTC ale CompleteEvent).

## Date
Panou: 946 migrari cu istoric pre-migrare complet (cache m_pools, manifest sigilat), pe zile {'2026-09-02': 235, '2026-09-03': 531, '2026-09-04': 180}; istoricul portofelelor: 126783 portofele relevante cu 12773966 evenimente anterioare deciziei. Outcome-uri executabile: 888 din 946 ({"OK": 888, "CHAIN_BREAK_IN_HOLD": 52, "ENTRY_STATE_UNANCHORED": 2, "FEE_UNRESOLVED_EXIT": 2, "FEE_UNRESOLVED_ENTRY": 2}).

## Regula primara
Decizie T0+60 s; intrare la starea ancorata de dupa toate evenimentele cu ts <= D; 0,25 SOL, cumparare exact-B sub buget; iesire +60 s (vanzare exact B, overlay static); taxe observate (taxa 0 => tier demonstrat); retea 0,00021 SOL; stari neancorate/rupturi excluse. Neconditionat VAL+CONF: {"2026-09-02": -0.007283198403669725, "2026-09-03": -0.006739368955911824, "2026-09-04": -0.006308175777777778}.

## Rezultate (semnale pe VAL+CONF; praguri DEV inghetate)
| Ipoteza | Verdict | N | mint-uri | EV SOL | PF | CI95 corectat | p Bonf. | EV 09-03 / 09-04 | matched | complement |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 COHORT_ROTATION_V2 | FAIL | 54 | 54 | -0.01364 | 0.536 | [-0.03270863672222221, 0.006237918222222218] | 1.0 | -0.01288 / -0.01743 | -0.01347 | -0.00601 |
| H2 SELLER_OVERHANG_DECAY_V2 | INSUFFICIENT_CLEAN_SAMPLE | 18 | 18 | 0.01376 | 1.559 | [-0.03479239516666667, 0.07296064144444445] | 0.8439 | 0.01376 / n/a | -0.00988 | -0.00712 |
| H3 SELECTIVE_BUYER_QUALITY_V1 | FAIL | 57 | 57 | 0.00484 | 1.282 | [-0.013710104017543861, 0.022694704350877185] | 0.7910999999999999 | 0.00378 / 0.01583 | -0.00283 | -0.00770 |

Corectie multipla: Bonferroni x3 (p si CI la alpha/3). Teste de scurgere: {'pools_tested': 200, 'identical_after_future_mutation': 200, 'violations': 0, 'violation_examples': [], 'PASS': True}.

## Revizuire adversariala
Determinism: {'H1': {'rerun_equal': True}, 'H2': {'rerun_equal': True}, 'H3': {'rerun_equal': True}}; praguri identice cu cele inghetate: True; portofele repetate: {'distinct_post_buyers': 48217, 'buyer_appearances': 156834, 'share_appearances_from_wallets_in_gt5_pools': 0.5871175892982389, 'wallets_in_gt5_pools': 4703, 'max_pools_per_wallet': 817}; amestecare portofele: {'H1': {'perm_mean_EV': -0.006177724275509058, 'observed_EV': -0.013639445407407406, 'p_perm_ge_observed': 0.895}, 'H3': {'perm_mean_EV': -0.008284535545881246, 'observed_EV': 0.00483749896491228, 'p_perm_ge_observed': 0.07}}; placebo +180 s: {'H1': {'N': 71, 'EV': -0.005836229394366197, 'unconditional_EV': -0.0070153530659824055}, 'H2': {'N': 21, 'EV': 0.007740891476190476, 'unconditional_EV': -0.0070153530659824055}, 'H3': {'N': 64, 'EV': -0.0076242472500000005, 'unconditional_EV': -0.0070153530659824055}}; scanare lookahead: {'features_reference_outcomes': False, 'features_use_strict_lt_D': True, 'build_signals_uses_outcomes': False}; reconciliere: {'m_cache_pools': 946, 'panel_rows': 946, 'outcome_rows': 946, 'executable_rows': 888, 'status_counts': {'OK': 888, 'CHAIN_BREAK_IN_HOLD': 52, 'ENTRY_STATE_UNANCHORED': 2, 'FEE_UNRESOLVED_EXIT': 2, 'FEE_UNRESOLVED_ENTRY': 2}, 'signals_val_conf': {'H1': 54, 'H2': 18, 'H3': 57}, 'reported': {'H1': 54, 'H2': 18, 'H3': 57}}; discrepante: [].

## Concluzie
BEST_HISTORICAL_CANDIDATE = NONE. Nicio regula nu a fost modificata dupa vederea rezultatelor; regulile ramase in ledger ca esuate sunt pastrate. READY_FOR_LIVE_TRADING = NO.