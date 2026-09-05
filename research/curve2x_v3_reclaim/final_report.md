# CURVE2X_V3_RECLAIM — raport final (HISTORICAL_DEV_NOT_SEALED)

# CURVE2X_V3_RECLAIM_AFTER_ABSORBED_PULLBACK — ipoteza unica (HISTORICAL_DEV_NOT_SEALED)

**Ipoteza.** O moneda pump.fun care (1) avanseaza pe curba pana la progres >= 40 % (anchor), (2) sufera primul pullback semnificativ (scadere >= 10 % a valorii
executabile a unei pozitii de referinta de 0,25 SOL cumparate la anchor, fata de maximul curent), (3) apoi recupereaza >= 75 % din pullback in maximum 120 s
(reclaim), pe fondul absorbtiei vanzatorilor (volum de vanzare in scadere, inventarul vanzatorilor epuizat) si al mentinerii breadth-ului cumparatorilor
(cumparatori noi, retentie), are o probabilitate si o valoare economica mai bune de a face 2x net (TP_FIRST inainte de SL -35 %, in 15 min) decat intrarea V2
la primul landmark de progres.

**Nul.** P(TP_FIRST | reclaim) si EV-ul net nu depasesc semnificativ valorile V2 si nu trec portile economice.

**Unitate de decizie.** Exact o decizie per mint, la primul reclaim valid (decizie in fereastra create+1860 s, inainte de CompleteEvent); intrare executabila
la decision_slot + 3 (stres +5), pozitie proprie de 0,25 SOL suprapusa in rezerve, taxe exacte (curba 125 bp; pool: lp+protocol+creator observate), cost de retea
0,00021 SOL declarat separat ca PRESUPUNERE. Continuare prin migrare doar cu splice PumpSwap demonstrabil (pool canonic, quote WSOL, VQ implicit consistent);
altfel CROSS_MIGRATION_LABEL_UNAVAILABLE.

**Date.** Exclusiv cache-urile locale derivate din banda existenta (V2: curve + evenimente de pool + flux), zero RPC. **09-01 NU exista local** (banda incepe
2026-09-02 10:18 UTC); vezi `frozen_spec.json` pentru split-ul efectiv si abaterea declarata. Toate zilele au fost deja inspectate de V1/V2: NIMIC nu este sealed.

**Verdict maxim permis.** HISTORICAL_PAPER_CANDIDATE_REQUIRES_FRESH_FORWARD. policy_enabled ramane false; watcher-ul emite doar REJECT/WATCH.


## Rezultat
FINAL_VERDICT = NO_VERIFIED_EDGE

Decizii: 1268 mint-uri cu reclaim valid din 2381 ancorate (1869 pullback-uri). Model A, politica {'p_tp_min': 0.25}.
VAL: {'signals': 52, 'usable': 52, 'TP_FIRST_rate': 0.34615384615384615, 'SL_FIRST_rate': 0.6153846153846154, 'timeout_rate': 0.038461538461538464, 'EV': 0.010048203615384613, 'median': -0.0878901065, 'PF': 1.1212208486938502, 'win_rate': 0.36538461538461536, 'EX_BEST_1PCT': 0.0030724733137254914, 'max_mint_share': 0.07569208901950245, 'max_creator_share': 0.07569208901950245, 'max_hour_share': 0.23415696123284335, 'CI95': [-0.04440720323076923, 0.06137156571153846], 'LCB90': -0.02391214632692308, 'max_signal_share_same_hour': 0.17307692307692307, 'by_day': {'2026-09-03': 52}}
CONF: {'signals': 10, 'usable': 10, 'TP_FIRST_rate': 0.3, 'SL_FIRST_rate': 0.7, 'timeout_rate': 0.0, 'EV': -0.024661109999999997, 'median': -0.0950183985, 'PF': 0.758092080068906, 'win_rate': 0.3, 'EX_BEST_1PCT': -0.05645355733333335, 'max_mint_share': 0.3383287433298186, 'max_creator_share': 0.3383287433298186, 'max_hour_share': 1.0, 'CI95': [-0.1363263606, 0.10126785319999998], 'LCB90': -0.1013894148, 'max_signal_share_same_hour': 0.6, 'by_day': {'2026-09-04': 10}}
VAL+CONF base: {'signals': 62, 'usable': 62, 'TP_FIRST_rate': 0.3387096774193548, 'SL_FIRST_rate': 0.6290322580645161, 'timeout_rate': 0.03225806451612903, 'EV': 0.0044499272258064475, 'median': -0.09046166950000001, 'PF': 1.0517645910538693, 'win_rate': 0.3548387096774194, 'EX_BEST_1PCT': -0.0014740157540983623, 'max_mint_share': 0.0652567964951742, 'max_creator_share': 0.0652567964951742, 'max_hour_share': 0.20187490350759107, 'CI95': [-0.043066311951612896, 0.05256934335483871], 'LCB90': -0.0271593655967742, 'max_signal_share_same_hour': 0.14516129032258066, 'by_day': {'2026-09-03': 52, '2026-09-04': 10}}
Stres +5 sloturi: -0.008240663693548384; cost +25 %: 0.004153487096774193
Porti: {'min_mints_val_conf_100': False, 'min_mints_conf_30': False, 'ev_combined_positive': True, 'ci95_lower_positive': False, 'pf_ge_1_30': False, 'ev_positive_val_and_conf': False, 'ex_best_1pct_positive': False, 'no_concentration_gt_20pct': False, 'stress_land5_ev_positive': False, 'stress_cost125_ev_positive': True, 'calibration_region_min_30': True, 'calibration_gap_le_8pp': True, 'beats_state_headroom_baseline': False, 'hour_diversity_ge_50pct': True, 'policy_feasible_on_cal': False}

## Comparatie cu V2 (prima intrare la landmark)
V2 (0,25 SOL, 15M, landmark 20-60 %): TP_FIRST ~19,7 %, SL_FIRST ~48,2 % pe toate randurile VAL+CONF; politica infezabila. V3 vezi tabelul de mai sus.

Vezi model_card.md pentru detalii; toate cifrele sunt istorice, pe date deja inspectate. policy_enabled=false; READY_FOR_REAL_MONEY=NO; LIVE_TRADING_ENABLED=NO.