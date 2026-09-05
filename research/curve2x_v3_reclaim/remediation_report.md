# V3 RECLAIM — remediere (HISTORICAL_DEV_NOT_SEALED; fara reantrenare, fara cautare de prag)

Model identic (hash 5fc8dfc4486afbdb…), p_tp_min = 0,25. Corectii: (1) `migrated_in_window` = CompleteEvent exista SI complete_ts <= decizie + 900 s, altfel eticheta este CURVE_ONLY; (2) limite de ordine in slotul de aterizare fara transactionIndex: rezultatul pentru toate pozitiile plauzibile ale tranzactiei in slotul de intrare si in slotul de iesire; primar = conservative (worst-case), raportate midpoint si optimistic; cazurile cu ruptura a lantului de rezerve sunt excluse (CHAIN_BREAK).

## Reparari
- splice-unavailable: original 9 -> remediat 6 => **3 din 9 reparate** (CompleteEvent dupa orizont, acum CURVE_ONLY); migrate in orizont: 284 -> 243.
- limite de ordine: {'OK': 1260, 'NO_FILL_MIGRATED': 5, 'CHAIN_BREAK': 3}; distributia numarului de pozitii plauzibile de intrare: {'1': 428, '3': 159, '6': 54, '2': 256, '5': 76, '4': 107, '7': 44, '13': 8, '8': 32, '11': 20, '9': 23, '16': 4, '22': 2, '15': 10, '18': 3, '10': 11, '19': 1, '17': 2, '14': 7, '12': 10, '30': 1, '31': 1, '20': 1}.
- teste sintetice: 11 -> 14 (adaugate: CompleteEvent la orizont+100 s fara pool => TIMEOUT_OTHER/unavailable=false/migrated=false; ordinea conservative <= midpoint <= optimistic; excluderea rupturii de lant).

## VAL+CONF, 0,25 SOL, semnale P_TP >= 0,25 & EV > 0
| estimare | mint-uri | TP | SL | EV SOL | PF | CI95 | EX_BEST_1% |
|---|---|---|---|---|---|---|---|
| V3-original (dupa toate trade-urile din slot) | 62 | 0.339 | 0.629 | 0.0044 | 1.05 | [-0.043066311951612896, 0.05256934335483871] | -0.0015 |
| remediat: conservative (PRIMAR) | 62 | 0.306 | 0.661 | -0.0183 | 0.81 | [-0.06427832625806451, 0.0274338259032258] | -0.0230 |
| remediat: midpoint | 62 | 0.323 | 0.645 | 0.0044 | 1.05 | [-0.04256493024193547, 0.05221057758064517] | -0.0011 |
| remediat: optimistic | 62 | 0.339 | 0.629 | 0.0361 | 1.58 | [-0.008720210435483874, 0.08124962116129032] | 0.0307 |
| remediat: +5 sloturi, conservative | 62 | 0.306 | 0.661 | -0.0247 | 0.75 | [-0.06941171775806453, 0.021421871516129034] | -0.0300 |
| remediat: cost +25 %, conservative | 62 | 0.306 | 0.677 | -0.0178 | 0.81 | [-0.06374196070967743, 0.02762969330645162] | -0.0225 |

Calibrare in regiunea selectata (conservative): {'n': 62, 'gap_tp': 0.002967107602452723, 'pred_tp': 0.3034845053007731, 'obs_tp': 0.3064516129032258, 'gap_sl': 0.041554944748631306, 'ece_tp': 0.011970680790850187}

Constatare: presupunerea V3-original (tranzactia noastra dupa toate trade-urile din slotul de aterizare) coincide cu estimarea midpoint; worst-case-ul ordinii in slot scade EV-ul de la +0,004 la -0,018 SOL. Stresul +5 sloturi nu inlocuieste aceasta analiza (este raportat separat, tot conservative).

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