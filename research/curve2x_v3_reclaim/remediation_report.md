# V3 RECLAIM — remediere (HISTORICAL_DEV_NOT_SEALED; fara reantrenare, fara cautare de prag)

Model identic (hash 5fc8dfc4486afbdb…), p_tp_min = 0,25. Corectii: (1) `migrated_in_window` = CompleteEvent exista SI complete_ts <= decizie + 900 s, altfel CURVE_ONLY; (2) limite de ordine fara transactionIndex: intrare = inainte de primul trade din slotul de aterizare si dupa fiecare trade din slot; iesire = ULTIMA stare strict inainte de exit_slot si fiecare stare succesiva din exit_slot (starile intermediare NU sunt pozitii plauzibile); primar = conservative; midpoint/optimistic raportate; CHAIN_BREAK exclus.

## Reparari
- splice-unavailable: original 9 -> remediat 6 => **3 din 9 reparate**; migrate in orizont: 284 -> 243.
- limite de ordine: {'OK': 1260, 'NO_FILL_MIGRATED': 5, 'CHAIN_BREAK': 3}; pozitii plauzibile de intrare: {'1': 428, '3': 159, '6': 54, '2': 256, '5': 76, '4': 107, '7': 44, '13': 8, '8': 32, '11': 20, '9': 23, '16': 4, '22': 2, '15': 10, '18': 3, '10': 11, '19': 1, '17': 2, '14': 7, '12': 10, '30': 1, '31': 1, '20': 1}.
- teste sintetice: original 11 -> remediat 14 (testul tautologic `label_independent_of_features` eliminat; adaugate: CompleteEvent dupa orizont, ordinea conservative<=midpoint<=optimistic, CHAIN_BREAK, semantica pozitiilor de iesire).

## VAL+CONF, 0,25 SOL, semnale P_TP >= 0,25 & EV > 0
| estimare | mint-uri | TP | SL | EV SOL | PF | CI95 | EX_BEST_1% |
|---|---|---|---|---|---|---|---|
| V3-original (dupa toate trade-urile din slot) | 62 | 0.339 | 0.629 | 0.0044 | 1.05 | [-0.043066311951612896, 0.05256934335483871] | -0.0015 |
| remediat: conservative (PRIMAR) | 62 | 0.306 | 0.661 | -0.0140 | 0.85 | [-0.06020847606451611, 0.03313073862903226] | -0.0198 |
| remediat: midpoint | 62 | 0.323 | 0.645 | 0.0025 | 1.03 | [-0.04472393841935484, 0.05065540591935484] | -0.0032 |
| remediat: optimistic | 62 | 0.339 | 0.629 | 0.0110 | 1.13 | [-0.036825747806451606, 0.05899817790322581] | 0.0051 |
| remediat: +5 sloturi, conservative | 62 | 0.306 | 0.661 | -0.0168 | 0.82 | [-0.0629246929032258, 0.030850103419354843] | -0.0232 |
| remediat: cost +25 %, conservative | 62 | 0.306 | 0.677 | -0.0137 | 0.85 | [-0.06010625661290321, 0.03281751399999999] | -0.0195 |

Calibrare in regiunea selectata (conservative): {'n': 62, 'gap_tp': 0.002967107602452723, 'pred_tp': 0.3034845053007731, 'obs_tp': 0.3064516129032258, 'gap_sl': 0.041554944748631306, 'ece_tp': 0.011970680790850187}

## Porti (conservative)
| poarta | rezultat |
|---|---|
| min_mints_val_conf_100 | FAIL |
| min_mints_conf_30 | FAIL |
| ev_combined_positive_conservative | FAIL |
| ci95_lower_positive | FAIL |
| pf_ge_1_30 | FAIL |
| ev_positive_val_and_conf | FAIL |
| ex_best_1pct_positive | FAIL |
| no_concentration_gt_20pct | FAIL |
| stress_land5_conservative_ev_positive | FAIL |
| stress_cost125_conservative_ev_positive | FAIL |
| calibration_region_min_30 | PASS |
| calibration_gap_le_8pp | PASS |
| beats_state_headroom_baseline | FAIL |
| hour_diversity_ge_50pct | PASS |
| policy_feasible_on_cal | FAIL |

**V3_REMEDIATED_VERDICT = NO_VERIFIED_EDGE** (original: NO_VERIFIED_EDGE). policy_enabled=false; READY_FOR_REAL_MONEY=NO; LIVE_TRADING_ENABLED=NO.