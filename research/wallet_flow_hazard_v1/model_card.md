# WALLET_FLOW_HAZARD_V1 — model card (HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED)

Generat 2026-09-05 17:02 EEST. Date deja inspectate; zero RPC; policy_enabled=false; nicio colectare forward.

## Date si graf cauzal
- Graf: {'wallets': 180192, 'positions': 1431371, 'creators': 14372}; randuri 14707 (5511 mint-uri), split {'TRAIN': 5156, 'CAL': 3401, 'EMBARGO': 317, 'VAL': 4457, 'CONF': 1376}, landmark-uri {'20': 5511, '30': 3327, '40': 2381, '50': 1885, '60': 1603}; status conservative {'SL_FIRST': 8324, 'TP_FIRST': 2090, 'NO_FILL_MIGRATED': 3790, 'TIMEOUT_OTHER': 438, 'CHAIN_BREAK': 56, 'UNAVAILABLE': 9}; gap 1588; cota randurilor cu istoric de portofel 0.778.
- Teste: 9/9 (graf cauzal, future mutation, permutare, fara identificatori, bin-uri de hazard, exit dinamic conservativ).

## Modele (selectie pe CAL)
- Prior TRAIN pe CAL log loss 0.6285; person-periods TRAIN 10245
| model | CAL log loss | Brier | ECE TP | gap top | n top |
|---|---|---|---|---|---|
| H | 0.6176 | 0.3599 | 0.004 | 0.015 | 57 |
| B | 0.6087 | 0.3550 | 0.010 | 0.052 | 244 |
| C | 0.6171 | 0.3582 | 0.004 | 0.169 | 77 |
- Selectat: **B**; politica (TRAIN/CAL): checkpoint >= 20 %, P_TP >= 0.25, EV prezis > 0; fezabila pe CAL: False

## Evaluare VAL/CONF (o singura data; PnL conservativ; exit static vs dinamic — fara alegere)
| segment | model | exit | semnale | TP | SL | EV SOL | mediana | PF | CI95 | EX_BEST_1% | p (EV>0) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| VAL | H | static | 4 | 0.250 | 0.500 | 0.0829 | 0.0726 | 2.64 | [-0.10099126, 0.266882684] | 0.0055 | 0.253 |
| VAL | H | dynamic | 4 | 0.250 | 0.500 | 0.0929 | 0.0925 | 3.29 | [-0.08110526950000001, 0.266882684] | 0.0187 | 0.144 |
| VAL | B | static | 70 | 0.300 | 0.600 | -0.0116 | -0.1021 | 0.87 | [-0.053499505542857144, 0.031904197685714286] | -0.0162 | 0.705 |
| VAL | B | dynamic | 70 | 0.300 | 0.600 | -0.0086 | -0.1017 | 0.90 | [-0.05005980734285714, 0.03443418512857142] | -0.0131 | 0.648 |
| VAL | C | static | 15 | 0.200 | 0.600 | -0.0301 | -0.0910 | 0.64 | [-0.10575806020000002, 0.05147279006666669] | -0.0504 | 0.768 |
| VAL | C | dynamic | 15 | 0.200 | 0.600 | -0.0301 | -0.0910 | 0.64 | [-0.10575806020000002, 0.05147279006666669] | -0.0504 | 0.768 |
| CONF | H | static | 23 | 0.261 | 0.696 | -0.0339 | -0.1227 | 0.65 | [-0.1001199573478261, 0.03762381521739131] | -0.0478 | 0.838 |
| CONF | H | dynamic | 23 | 0.261 | 0.696 | -0.0339 | -0.1227 | 0.65 | [-0.1001199573478261, 0.03762381521739131] | -0.0478 | 0.838 |
| CONF | B | static | 61 | 0.230 | 0.721 | -0.0498 | -0.1300 | 0.53 | [-0.08901447936065573, -0.007112385852459015] | -0.0561 | 0.989 |
| CONF | B | dynamic | 61 | 0.230 | 0.721 | -0.0548 | -0.1300 | 0.48 | [-0.092504173852459, -0.013940914409836063] | -0.0603 | 0.995 |
| CONF | C | static | 5 | 0.200 | 0.800 | -0.0731 | -0.1101 | 0.37 | [-0.177262508, 0.0767702794] | -0.1454 | 0.818 |
| CONF | C | dynamic | 5 | 0.200 | 0.800 | -0.0731 | -0.1101 | 0.37 | [-0.177262508, 0.0767702794] | -0.1454 | 0.818 |
| VAL+CONF | H | static | 27 | 0.259 | 0.667 | -0.0166 | -0.1128 | 0.82 | [-0.07817293048148148, 0.05218060462962963] | -0.0294 | 0.697 |
| VAL+CONF | H | dynamic | 27 | 0.259 | 0.667 | -0.0151 | -0.1128 | 0.83 | [-0.07673278081481481, 0.052783782407407415] | -0.0278 | 0.684 |
| VAL+CONF | B | static | 131 | 0.267 | 0.656 | -0.0294 | -0.1128 | 0.70 | [-0.058288780648854954, 0.00016137127480915769] | -0.0348 | 0.973 |
| VAL+CONF | B | dynamic | 131 | 0.267 | 0.656 | -0.0301 | -0.1128 | 0.68 | [-0.058452058954198464, -0.0004975347786259554] | -0.0352 | 0.978 |
| VAL+CONF | C | static | 20 | 0.200 | 0.650 | -0.0408 | -0.1014 | 0.56 | [-0.1050134402, 0.031403940100000007] | -0.0564 | 0.870 |
| VAL+CONF | C | dynamic | 20 | 0.200 | 0.650 | -0.0408 | -0.1014 | 0.56 | [-0.1050134402, 0.031403940100000007] | -0.0564 | 0.870 |

- Stres (model B, VAL+CONF): +5 sloturi conservative -0.0321; cost +25 % -0.0306; calibrare in regiune {'n': 131, 'gap_tp': 0.034247443696640956, 'pred_tp': 0.3014230162157249, 'obs_tp': 0.26717557251908397}; exit-uri dinamice declansate 4; delta EV dinamic-static -0.0007
- Holm (3 modele x 2 exit-uri): {'H/static': {'p': 0.697, 'p_holm': 1.0}, 'H/dynamic': {'p': 0.68425, 'p_holm': 1.0}, 'B/static': {'p': 0.973, 'p_holm': 1.0}, 'B/dynamic': {'p': 0.978, 'p_holm': 1.0}, 'C/static': {'p': 0.87025, 'p_holm': 1.0}, 'C/dynamic': {'p': 0.87025, 'p_holm': 1.0}}

## Porti
| poarta | rezultat |
|---|---|
| min_signals_val_conf_100 | PASS |
| min_conf_30 | PASS |
| ev_conservative_gt_0 | FAIL |
| ci95_lower_gt_0 | FAIL |
| pf_ge_1_30 | FAIL |
| val_and_conf_positive | FAIL |
| land5_gt_0 | FAIL |
| cost125_gt_0 | FAIL |
| ex_best_1pct_gt_0 | FAIL |
| beats_v3_conservative | FAIL |
| beats_state_headroom_baseline | PASS |
| no_entity_hour_day_gt_20pct | FAIL |
| holm_significant_primary | FAIL |

**FINAL_VERDICT = NO_VERIFIED_EDGE**. policy_enabled=false; READY_FOR_FORWARD_PAPER = NO; LIVE_TRADING_ENABLED = NO.