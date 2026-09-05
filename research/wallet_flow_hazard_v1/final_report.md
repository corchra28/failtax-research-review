# WALLET_FLOW_HAZARD_V1 — raport final (HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED)

# WALLET_FLOW_HAZARD_V1 — comparatie cu H3, ranker_2x si V3 (HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED)

| Sursa anterioara | Ce a testat (informatia folosita) | Rezultat |
|---|---|---|
| H3 SELECTIVE_BUYER_QUALITY_V1 (overnight 09-05) | quality = media rangurilor (+breadth cumparatori noi, -mediana NUMARULUI de mint-uri anterioare ale cumparatorilor post-only, -concentrarea fluxului top wallet), pe pool-uri PumpSwap post-migrare ($25, R100) | FAIL (EV +0,005, PF 1,28, CI include zero) |
| ranker_2x V1 | wallet_history: mediana mint-urilor anterioare, cota cumparatorilor cu istoric; creator: numar lansari anterioare, rata de migrare; checkpoint-uri de varsta; eticheta "maxim atins" | NO (EV per mint ~0) |
| CURVE2X V2 / V3 | reutilizarea portofelelor in ultimele 60 min (coordonare), inventarul creatorului, blocuri de stare/flux; first-passage 2x/-50 % (V2) si reclaim 2x/-35 % (V3) | NO_VERIFIED_EDGE |

**Informatia NOUA testata de WALLET_FLOW_HAZARD_V1** (niciuna dintre sursele de mai sus nu a folosit-o):
1. **Track record pe OUTCOME-uri maturizate per portofel** (A): pentru fiecare cumparator, pozitiile anterioare complet maturizate (prima cumparare + 960 s <= momentul deciziei): rata TP (pret x2 in 15 min de la intrarea lui), EV realizat (vanzari + marcarea inventarului ramas la valoare executabila), supravietuire (nu a ramas cu pierdere > 35 %), scor repeat-winner, varsta in banda. H3/ranker foloseau doar NUMARUL de mint-uri anterioare (activitate), nu rezultatele lor.
2. **Cumparatori noi PROFITABILI** (B): breadth-ul cumparatorilor noi ponderat cu istoricul lor de outcome-uri.
3. **Hazardul inventarului cohortelor timpurii** (C): inventarul estimat ramas al cumparatorilor timpurii, procentul vandut, decay-ul intensitatii vanzarilor, numarul vanzatorilor ramasi, absorbtia dupa vanzari mari (V2/V3 aveau doar epuizarea agregata a vanzatorilor).
4. **Istoricul de OUTCOME-uri al creatorului** (D): lansari anterioare maturizate cu rezultatul lor executabil si comportamentul de vanzare (ranker avea doar numar + rata de migrare).
5. **Model de hazarde concurente** (TP vs SL) cu covariate variabile in timp si **exit dinamic** (iesire cand hazardul TP scade si hazardul SL creste), comparat cu exitul static 2x / -35 % — niciun experiment anterior nu a modelat timpul pana la eveniment.

Concluzie Faza 0: ipoteza NU este echivalenta cu H3 / ranker_2x / V3 => se continua (nu ALREADY_TESTED). Toate datele au fost deja inspectate de experimentele anterioare: nimic nu este sealed.


## Rezultat
FINAL_VERDICT = NO_VERIFIED_EDGE
Model B, politica {'Lmin': 20, 'p_tp_min': 0.25}; VAL+CONF static conservativ: {'usable': 131, 'EV': -0.029393897679389318, 'median': -0.112838075, 'PF': 0.6955862421416704, 'win_rate': 0.2748091603053435, 'EX_BEST_1PCT': -0.03476361024806201, 'max_mint_share': 0.0370362680960009, 'CI95': [-0.058288780648854954, 0.00016137127480915769], 'LCB90': -0.0485482073129771, 'p_one_sided': 0.973, 'max_hour_share': 0.16150275442517484, 'max_signal_share_same_hour': 0.19083969465648856}; dinamic: {'usable': 131, 'EV': -0.03010002905343512, 'median': -0.112838075, 'PF': 0.6829130621914566, 'win_rate': 0.2748091603053435, 'EX_BEST_1PCT': -0.03522135527906976, 'max_mint_share': 0.036272464131980466, 'CI95': [-0.058452058954198464, -0.0004975347786259554], 'LCB90': -0.04882956494656489, 'p_one_sided': 0.978}; CONF: {'usable': 61, 'EV': -0.04979614508196721, 'median': -0.129985771, 'PF': 0.5310270469365346, 'win_rate': 0.22950819672131148, 'EX_BEST_1PCT': -0.05605722273333334, 'max_mint_share': 0.09474318849081537, 'CI95': [-0.08901447936065573, -0.007112385852459015], 'LCB90': -0.07640151636065572, 'p_one_sided': 0.98925, 'max_hour_share': 0.413143296852374, 'max_signal_share_same_hour': 0.4098360655737705}
Porti: {'min_signals_val_conf_100': True, 'min_conf_30': True, 'ev_conservative_gt_0': False, 'ci95_lower_gt_0': False, 'pf_ge_1_30': False, 'val_and_conf_positive': False, 'land5_gt_0': False, 'cost125_gt_0': False, 'ex_best_1pct_gt_0': False, 'beats_v3_conservative': False, 'beats_state_headroom_baseline': True, 'no_entity_hour_day_gt_20pct': False, 'holm_significant_primary': False}
Vezi model_card.md. policy_enabled=false; nicio colectare forward; LIVE_TRADING_ENABLED=NO.