# CURVE2X V2 — model card (HISTORICAL_REMEDIATION_NOT_SEALED)

Generat 2026-09-05 13:20 EEST. Remediere a ranker_2x V1 (pastrat in `research/ranker_2x/v1/`). Toate zilele fusesera inspectate anterior: VAL/CONF NU sunt sealed. Zero RPC, zero date noi, zero tranzactii.

## Definitie
- Unitate: (mint, landmark de progres [10, 20, 30, 40, 50, 60, 70, 80] %), o singura decizie per mint (primul landmark eligibil in banda [20, 60] ∩ [20,70]).
- Eticheta: first-passage pe valoarea neta a lichidarii propriei pozitii (overlay static, intregi, taxa curba 125 bp, cost retea 0,00021 SOL = PRESUPUNERE, intrare/iesire la +3 sloturi): TP_FIRST (>= 2x) / SL_FIRST (<= 0,5x; castiga la egalitate de slot) / TIMEOUT_OTHER; orizont primar 15 min; continuare in pool-ul canonic PumpSwap cu rezerve efective (raw + VQ implicit).
- Date: 11458 mint-uri cu >= 10 % progres in 31 min, 28818 randuri; split {'TRAIN': 10277, 'CAL': 6342, 'EMBARGO': 626, 'VAL': 9065, 'CONF': 2508}; randuri cu gap excluse 6084; migrate in fereastra 2739, splice OK 2620, CROSS_MIGRATION_LABEL_UNAVAILABLE 119.
- Status primar (0,25 SOL, 15M): {'SL_FIRST': 11287, 'TIMEOUT_OTHER': 6908, 'TP_FIRST': 4516, 'NO_FILL_MIGRATED': 6068, 'UNAVAILABLE': 39}
- Teste sintetice: 13/13 PASS; LABEL_AGREEMENT (a doua implementare, 600 cazuri, 173 straturi) = 1.0000.

## Selectia modelului (CAL; log loss -> Brier -> gap in top -> EV)
- Selectat: bloc **M4**, model **B** (GBM depth-2 multiclass); etape: {'stage1': [['M4', 'B']], 'stage2': [['M4', 'B']], 'stage3': [['M4', 'B']], 'selected': ['M4', 'B'], 'tolerance_rel': 0.005}
- Prior TRAIN pe CAL: log loss 1.0308; baseline M0 (B): log loss 0.8233, Brier 0.4845.

| ablatiune | model | CAL log loss | CAL Brier | CAL gap top | CAL n top | VAL+CONF log loss | VAL+CONF Brier |
|---|---|---|---|---|---|---|---|
| M4 | B | 0.7864 | 0.4626 | 0.0032 | 411 | 0.7951 | 0.4664 |
| M3 | B | 0.7904 | 0.4661 | 0.0106 | 393 | 0.7988 | 0.4701 |
| M2 | B | 0.7912 | 0.4661 | 0.0375 | 341 | 0.7965 | 0.4688 |
| M5 | B | 0.7934 | 0.4677 | 0.0253 | 346 | 0.8009 | 0.4710 |
| M1 | B | 0.8021 | 0.4744 | 0.0192 | 324 | 0.8047 | 0.4751 |
| M5 | C | 0.8102 | 0.4751 | 0.0719 | 208 | 0.8164 | 0.4773 |
| M4 | A | 0.8166 | 0.4815 | 0.0395 | 412 | 0.8263 | 0.4845 |
| M5 | A | 0.8208 | 0.4857 | 0.0401 | 401 | 0.8257 | 0.4845 |
| M0 | B | 0.8233 | 0.4845 | 0.0391 | 307 | 0.8270 | 0.4849 |
| M3 | A | 0.8248 | 0.4875 | 0.0201 | 259 | 0.8312 | 0.4886 |
| M2 | A | 0.8249 | 0.4867 | 0.0058 | 254 | 0.8332 | 0.4886 |
| M1 | A | 0.8322 | 0.4913 | 0.0182 | 183 | 0.8369 | 0.4909 |
| M0 | A | 0.8450 | 0.4975 | 0.0118 | 157 | 0.8474 | 0.4948 |

Prior TRAIN pe VAL+CONF: log loss 1.0377.

## Politica inghetata (grila fixa pe CAL, max LCB90 al EV per mint, >= 100 mint-uri)
- Selectata: {'band': [20, 60], 'p_tp_min': 0.3, 'p_sl_max': 0.4}; CAL: {'signals': 1, 'usable': 1, 'unavailable': 0, 'TP_FIRST_rate': 1.0, 'SL_FIRST_rate': 0.0, 'timeout_rate': 0.0, 'EV': 0.273015068, 'median': 0.273015068, 'PF': inf, 'win_rate': 1.0, 'EX_BEST_1PCT': 0.273015068, 'max_mint_share': 1.0, 'max_creator_share': 1.0, 'max_hour_share': 1.0, 'CI95': [0.273015068, 0.273015068], 'LCB90': 0.273015068, 'clusters': 1, 'by_landmark': {'30': 1}}; combinatii fezabile pe CAL: 0/48. NOTA: NICIO combinatie nu indeplineste >=100 mint-uri pe CAL cu EV>0; se raporteaza cea mai buna dupa LCB90 doar pentru diagnostic; semnalele raman WATCH/REJECT

## Evaluare (o singura data; nivel de mint; CI95 bootstrap pe clustere = ore)
| segment | notional | varianta | mint-uri | TP_FIRST | SL_FIRST | timeout | EV SOL | mediana | PF | CI95 | EX_BEST_1% | max cota mint/creator/ora |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VAL | 0.25 | base | 6 | 0.167 | 0.167 | 0.667 | 0.0738 | 0.1041 | 3.09 | [-0.0008605365000000018, 0.22320735949999998] | 0.0393 | 0.376/0.376/0.376 |
| VAL | 0.25 | stress_land5 | 6 | 0.167 | 0.167 | 0.667 | 0.0738 | 0.1041 | 3.09 | [-0.0008605365000000018, 0.22320735949999998] | 0.0393 | 0.376/0.376/0.376 |
| VAL | 0.25 | stress_cost125 | 6 | 0.167 | 0.167 | 0.667 | 0.0734 | 0.1018 | 3.06 | [-0.0024543402500000026, 0.225082434] | 0.0375 | 0.387/0.387/0.387 |
| VAL | 0.5 | base | 3 | 0.333 | 0.000 | 0.667 | 0.3725 | 0.3997 | inf | [0.226116108, 0.491632595] | 0.3129 | 0.440/0.440/0.440 |
| VAL | 0.5 | stress_land5 | 3 | 0.333 | 0.000 | 0.667 | 0.3725 | 0.3997 | inf | [0.226116108, 0.491632595] | 0.3129 | 0.440/0.440/0.440 |
| VAL | 0.5 | stress_cost125 | 3 | 0.333 | 0.000 | 0.667 | 0.3735 | 0.3941 | inf | [0.221577503, 0.504819311] | 0.3078 | 0.451/0.451/0.451 |
| VAL | 1.0 | base | 3 | 0.333 | 0.000 | 0.667 | 0.7547 | 0.7964 | inf | [0.449784228, 1.017866442] | 0.6231 | 0.450/0.450/0.450 |
| VAL | 1.0 | stress_land5 | 3 | 0.333 | 0.000 | 0.667 | 0.7552 | 0.7964 | inf | [0.449784228, 1.01949044] | 0.6231 | 0.450/0.450/0.450 |
| VAL | 1.0 | stress_cost125 | 3 | 0.333 | 0.000 | 0.667 | 0.7438 | 0.7853 | inf | [0.440783768, 1.005365676] | 0.6130 | 0.451/0.451/0.451 |
| CONF | 0.25 | base | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 0.25 | stress_land5 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 0.25 | stress_cost125 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 0.5 | base | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 0.5 | stress_land5 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 0.5 | stress_cost125 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 1.0 | base | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 1.0 | stress_land5 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| CONF | 1.0 | stress_cost125 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | None | n/a | n/a/n/a/n/a |
| VAL+CONF | 0.25 | base | 6 | 0.167 | 0.167 | 0.667 | 0.0738 | 0.1041 | 3.09 | [-0.0008605365000000018, 0.22320735949999998] | 0.0393 | 0.376/0.376/0.376 |
| VAL+CONF | 0.25 | stress_land5 | 6 | 0.167 | 0.167 | 0.667 | 0.0738 | 0.1041 | 3.09 | [-0.0008605365000000018, 0.22320735949999998] | 0.0393 | 0.376/0.376/0.376 |
| VAL+CONF | 0.25 | stress_cost125 | 6 | 0.167 | 0.167 | 0.667 | 0.0734 | 0.1018 | 3.06 | [-0.0024543402500000026, 0.225082434] | 0.0375 | 0.387/0.387/0.387 |
| VAL+CONF | 0.5 | base | 3 | 0.333 | 0.000 | 0.667 | 0.3725 | 0.3997 | inf | [0.226116108, 0.491632595] | 0.3129 | 0.440/0.440/0.440 |
| VAL+CONF | 0.5 | stress_land5 | 3 | 0.333 | 0.000 | 0.667 | 0.3725 | 0.3997 | inf | [0.226116108, 0.491632595] | 0.3129 | 0.440/0.440/0.440 |
| VAL+CONF | 0.5 | stress_cost125 | 3 | 0.333 | 0.000 | 0.667 | 0.3735 | 0.3941 | inf | [0.221577503, 0.504819311] | 0.3078 | 0.451/0.451/0.451 |
| VAL+CONF | 1.0 | base | 3 | 0.333 | 0.000 | 0.667 | 0.7547 | 0.7964 | inf | [0.449784228, 1.017866442] | 0.6231 | 0.450/0.450/0.450 |
| VAL+CONF | 1.0 | stress_land5 | 3 | 0.333 | 0.000 | 0.667 | 0.7552 | 0.7964 | inf | [0.449784228, 1.01949044] | 0.6231 | 0.450/0.450/0.450 |
| VAL+CONF | 1.0 | stress_cost125 | 3 | 0.333 | 0.000 | 0.667 | 0.7438 | 0.7853 | inf | [0.440783768, 1.005365676] | 0.6130 | 0.451/0.451/0.451 |

- Orizonturi secundare (0,25 SOL, VAL+CONF): 5M {'signals': 6, 'usable': 6, 'unavailable': 0, 'TP_FIRST_rate': 0.16666666666666666, 'SL_FIRST_rate': 0.16666666666666666, 'timeout_rate': 0.6666666666666666, 'EV': 0.0258081535, 'median': 0.0079565285, 'PF': 1.6735260337872415, 'win_rate': 0.6666666666666666, 'EX_BEST_1PCT': -0.018283444, 'max_mint_share': 0.6400566821476765, 'max_creator_share': 0.6400566821476765, 'max_hour_share': 0.6400566821476765, 'CI95': [-0.033507679166666665, 0.17161758575], 'LCB90': -0.023957549999999998, 'clusters': 4, 'by_landmark': {'50': 2, '40': 2, '20': 1, '30': 1}}; 30M {'signals': 6, 'usable': 6, 'unavailable': 0, 'TP_FIRST_rate': 0.3333333333333333, 'SL_FIRST_rate': 0.3333333333333333, 'timeout_rate': 0.3333333333333333, 'EV': 0.008553644333333332, 'median': -0.0478231335, 'PF': 1.111316457781944, 'win_rate': 0.3333333333333333, 'EX_BEST_1PCT': -0.0429557174, 'max_mint_share': 0.5193555866368603, 'max_creator_share': 0.5193555866368603, 'max_hour_share': 0.5193555866368603, 'CI95': [-0.11526118200000002, 0.256183297], 'LCB90': -0.07365707025000001, 'clusters': 4, 'by_landmark': {'50': 2, '40': 2, '20': 1, '30': 1}}
- Calibrare in regiunea tranzactionata (VAL+CONF, 0,25): {'n': 6, 'gap_tp': 0.3027234287153606, 'ece_tp': 0.4082698224996203, 'gap_sl': 0.15635237649876135, 'pred_tp': 0.4693900953820273, 'obs_tp': 0.16666666666666666}
- Baseline STATE_HEADROOM (M0) cu aceeasi politica (VAL+CONF, 0,25): {'signals': 0, 'usable': 0, 'unavailable': 0}
- Metrici pe toate randurile VAL+CONF (0,25): {'n': 7966, 'log_loss': 0.7951101714209764, 'brier': 0.4664082939621159, 'ece_tp': 0.011306790268821176, 'ece_sl': 0.02046755924838627, 'base_rates': {'TP_FIRST': 0.19708762239517952, 'SL_FIRST': 0.48204870700477026, 'TIMEOUT_OTHER': 0.3208636706000502}}

## Porti PAPER_CANDIDATE (regula 28)
| poarta | rezultat |
|---|---|

## Diagnostic post-hoc: funnel-ul conditiilor (nu modifica politica)
| segment | randuri | in banda | headroom>=2 | fara gap | P_TP>=min | P_SL<=max | EV>0 | EV_LCB90>0 | mint-uri finale |
|---|---|---|---|---|---|---|---|---|---|
| CAL | 6342 | 3401 | 2305 | 2002 | 450 | 4 | 3 | 3 | 3 |
| VAL | 9065 | 4457 | 3331 | 3222 | 687 | 11 | 9 | 7 | 6 |
| CONF | 2508 | 1376 | 913 | 878 | 158 | 0 | 0 | 0 | 0 |

Constatare structurala: in banda de intrare, mediana P(SL_FIRST) este ~0,65 si decila 10 ~0,50 (VAL: {'n': 4457, 'ev_mean': -0.02594241442872152, 'ev_pos_share': 0.2961633385685439, 'ev_lcb_pos_share': 0.18375588961184652, 'p_tp_q50': 0.25055938080545176, 'p_tp_q90': 0.3531712941285401, 'p_sl_q10': 0.4975999808946586, 'p_sl_q50': 0.6838320211039822, 'share_p_tp_ge_030_and_p_sl_le_040': 0.003141126318151223}); conditia P_SL_FIRST <= 0,40 este indeplinita de < 0,5 % din randuri, iar EV prezis mediu in banda este negativ. Politica 2x / -50 % pe curba nu este fezabila la nivelul cerut, indiferent de pragul P_TP.

| min_mints_total_100 | FAIL |
| min_mints_val_30 | FAIL |
| min_mints_conf_30 | FAIL |
| ev_positive_val | PASS |
| ev_positive_conf | FAIL |
| ci95_lower_positive | FAIL |
| pf_ge_1_5 | PASS |
| ex_best_1pct_positive | PASS |
| no_concentration_gt_20pct | FAIL |
| stress_land5_ev_positive | PASS |
| stress_cost125_ev_positive | PASS |
| calibration_gap_le_5pp | FAIL |
| beats_state_headroom_baseline | PASS |
| positive_after_mint_dedup | FAIL |
| policy_feasible_on_cal | FAIL |

**FINAL_VERDICT = NO_VERIFIED_EDGE**; READY_FOR_REAL_MONEY = NO; LIVE_TRADING_ENABLED = NO.

## Limitari
- VAL/CONF nu sunt sealed (post-hoc); un singur regim de 2 zile; 09-01 lipseste local; costul de retea este o presupunere; taxa curbei mostenita din V1; overlay static (fara reactia altor participanti la propria pozitie); latenta +3 sloturi presupusa; VQ implicit din evenimente; probabilitatile pentru 0,50/1,00 SOL vin din modele separate (fara extrapolare).
- Automatizare: replay-only; AUTOMATION_REPLAY_AGREEMENT = 1.0 (batch 13 vs replay 13).