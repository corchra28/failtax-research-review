# CURVE2X_V3_RECLAIM_AFTER_ABSORBED_PULLBACK — model card (HISTORICAL_DEV_NOT_SEALED)

Generat 2026-09-05 15:18 EEST. Ipoteza unica; date deja inspectate (nimic sealed); zero RPC; policy_enabled=false; watcher-ul emite doar REJECT/WATCH.

## Date
- Mint-uri in cache 58648; N_ANCHORED 2381; N_PULLBACKS 1869; N_RECLAIMS (decizii, o per mint) 1268; split {'TRAIN': 492, 'CAL': 262, 'EMBARGO': 28, 'VAL': 385, 'CONF': 101}; zile {'2026-09-02': 492, '2026-09-03': 675, '2026-09-04': 101}; gap 136; migrate 284 (splice OK 275, indisponibil 9).
- Status etichete (0,25 SOL, 15M, base): {'SL_FIRST': 900, 'TP_FIRST': 293, 'TIMEOUT_OTHER': 70, 'NO_FILL_MIGRATED': 5}
- Split efectiv: 09-01 NU exista local; pentru a pastra ordinea stricta cronologica si patru roluri: TRAIN = 09-02 (de la inceputul benzii), CAL = 09-03 00:00-12:00 UTC, VAL = 09-03 12:00-24:00 UTC, CONF = 09-04 (pana la oprirea colectorului). Niciun rand nu este mutat intre zile; ziua 09-03 este subdivizata dupa ora UTC (nu aleator). Un singur rand per mint.
- Teste sintetice 11/11; leakage_report PASS=True (future mutation 65/65); replay agreement 1.0 (1268/1268), PAPER_CANDIDATE emise 0.

## Modele (selectie pe CAL: log loss -> calibrare -> EV)
- Prior TRAIN pe CAL: log loss 0.7745; rate de baza {'TRAIN': {'TP_FIRST': 0.22482435597189696, 'SL_FIRST': 0.711943793911007, 'TIMEOUT_OTHER': 0.06323185011709602}, 'CAL': {'TP_FIRST': 0.2102803738317757, 'SL_FIRST': 0.7102803738317757, 'TIMEOUT_OTHER': 0.0794392523364486}}
| model | trasaturi | CAL log loss | CAL Brier | ECE TP | gap top | n top | EV realizat top |
|---|---|---|---|---|---|---|---|
| A | full | 0.7253 | 0.4223 | 0.020 | 0.016 | 55 | -0.0168 |
| B | full | 0.7349 | 0.4282 | 0.014 | 0.035 | 12 | -0.0141 |
| C | state | 0.7347 | 0.4289 | 0.004 | 0.097 | 11 | 0.0363 |
- Selectat: **A**; etape {'stage1': ['A'], 'stage2': ['A'], 'selected': 'A', 'tolerance_rel': 0.005}
- Politica (prag pe CAL, grila [0.25, 0.3, 0.35, 0.4, 0.45, 0.5]): {'p_tp_min': 0.25}; fezabila pe CAL: False; NOTA: nicio valoare din grila nu are >= 30 mint-uri cu EV>0 pe CAL; prag raportat doar diagnostic

## Evaluare (o singura data; nivel de mint; bootstrap mint x zi)
| segment | varianta | mint-uri | TP | SL | timeout | EV SOL | mediana | PF | CI95 | EX_BEST_1% | max cota mint/creator/ora |
|---|---|---|---|---|---|---|---|---|---|---|---|
| VAL | base | 52 | 0.346 | 0.615 | 0.038 | 0.0100 | -0.0879 | 1.12 | [-0.04440720323076923, 0.06137156571153846] | 0.0031 | 0.076/0.076/0.234 |
| VAL | land5 | 52 | 0.308 | 0.654 | 0.038 | -0.0065 | -0.0885 | 0.93 | [-0.05994360817307693, 0.046152327980769216] | -0.0141 | 0.087/0.087/0.261 |
| VAL | cost125 | 52 | 0.346 | 0.635 | 0.019 | 0.0100 | -0.0862 | 1.12 | [-0.04370578561538462, 0.06123171253846154] | 0.0031 | 0.076/0.076/0.234 |
| CONF | base | 10 | 0.300 | 0.700 | 0.000 | -0.0247 | -0.0950 | 0.76 | [-0.1363263606, 0.10126785319999998] | -0.0565 | 0.338/0.338/1.000 |
| CONF | land5 | 10 | 0.300 | 0.700 | 0.000 | -0.0174 | -0.0914 | 0.83 | [-0.13252784920000002, 0.11439157290000002] | -0.0539 | 0.373/0.373/1.000 |
| CONF | cost125 | 10 | 0.300 | 0.700 | 0.000 | -0.0261 | -0.0960 | 0.75 | [-0.1370834242, 0.09904336049999998] | -0.0577 | 0.338/0.338/1.000 |
| VAL+CONF | base | 62 | 0.339 | 0.629 | 0.032 | 0.0044 | -0.0905 | 1.05 | [-0.043066311951612896, 0.05256934335483871] | -0.0015 | 0.065/0.065/0.202 |
| VAL+CONF | land5 | 62 | 0.306 | 0.661 | 0.032 | -0.0082 | -0.0908 | 0.91 | [-0.05606054753225805, 0.04068012338709678] | -0.0146 | 0.073/0.073/0.220 |
| VAL+CONF | cost125 | 62 | 0.339 | 0.645 | 0.016 | 0.0042 | -0.0887 | 1.05 | [-0.04258253762903226, 0.05158242274193548] | -0.0017 | 0.065/0.065/0.202 |

- Calibrare in regiunea selectata (VAL+CONF): {'n': 62, 'gap_tp': 0.03522517211858173, 'pred_tp': 0.3034845053007731, 'obs_tp': 0.3387096774193548, 'gap_sl': 0.009296880232502303, 'ece_tp': 0.03522517211858176}
- Toate randurile VAL+CONF: {'n': 459, 'log_loss': 0.690866472191423, 'brier': 0.41552815442682817, 'ece_tp': 0.042197677947980704, 'base_rates': {'TP_FIRST': 0.24618736383442266, 'SL_FIRST': 0.7058823529411765, 'TIMEOUT_OTHER': 0.04793028322440087}}
- Baseline C (state/headroom) cu aceeasi politica: {'signals': 13, 'usable': 13, 'TP_FIRST_rate': 0.3076923076923077, 'SL_FIRST_rate': 0.6923076923076923, 'timeout_rate': 0.0, 'EV': 0.009521264384615384, 'median': -0.076144349, 'PF': 1.1442386041064707, 'win_rate': 0.38461538461538464, 'EX_BEST_1PCT': -0.011448096916666676, 'max_mint_share': 0.2659640605799504, 'max_creator_share': 0.2659640605799504, 'max_hour_share': 0.48789788039067633, 'CI95': [-0.07409335030769232, 0.10442624523076922], 'LCB90': -0.045751308769230774, 'max_signal_share_same_hour': 0.3076923076923077, 'by_day': {'2026-09-03': 11, '2026-09-04': 2}}; log loss C pe toate randurile 0.7013

## Porti
| poarta | rezultat |
|---|---|
| min_mints_val_conf_100 | FAIL |
| min_mints_conf_30 | FAIL |
| ev_combined_positive | PASS |
| ci95_lower_positive | FAIL |
| pf_ge_1_30 | FAIL |
| ev_positive_val_and_conf | FAIL |
| ex_best_1pct_positive | FAIL |
| no_concentration_gt_20pct | FAIL |
| stress_land5_ev_positive | FAIL |
| stress_cost125_ev_positive | PASS |
| calibration_region_min_30 | PASS |
| calibration_gap_le_8pp | PASS |
| beats_state_headroom_baseline | FAIL |
| hour_diversity_ge_50pct | PASS |
| policy_feasible_on_cal | FAIL |

**FINAL_VERDICT = NO_VERIFIED_EDGE** (maxim permis: HISTORICAL_PAPER_CANDIDATE_REQUIRES_FRESH_FORWARD). policy_enabled=false. READY_FOR_REAL_MONEY=NO. LIVE_TRADING_ENABLED=NO.

## Limitari
- Date deja inspectate; 09-01 absent; un regim de ~2 zile; cost de retea presupus; overlay static; latenta presupusa; VQ implicit; taxa curbei mostenita din V2.