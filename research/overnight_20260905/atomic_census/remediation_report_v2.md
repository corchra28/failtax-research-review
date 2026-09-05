# REMEDIERE FINALĂ DE CONFORMITATE — V2 (diff față de V1) — 2026-09-05 10:27 EEST

Proveniență: V1 = review commit 209317a04212ca541d9386a85d7527a59004f154 / source commit 3111f43da121a36d8b6aa767ffbd79c1764d8fc9; V2 = commit-urile de remediere de după (curent 3111f43da121a36d8b6aa767ffbd79c1764d8fc9, plus commit-ul de publicare). V1 este păstrat neschimbat în `atomic_census/v1/` și `strategies/v1/`.

## 1. Excluderea multi-user per token (spec census_frozen_spec.json)
V1 înregistra `users_in_tx` agregat pe toți tokenii tranzacției și NU aplica excluderea. V2 numără utilizatorii distincți per (tranzacție, token) și exclude ciclul doar când același token implică > 1 utilizator (motiv `MULTI_USER_SAME_TOKEN_IN_TX`). Teste sintetice (census_multiuser_tests.py): un utilizator → păstrat; doi utilizatori pe același token → exclus; utilizatori diferiți pe tokeni diferiți → păstrat. Predicatul tautologic `not all(d["is_buy"] or True ...)` a fost eliminat din scanner.

| Metrica | V1 | V2 |
|---|---|---|
| N | 500 | 500 |
| users | 52 | 52 |
| tokens | 63 | 63 |
| total_net_sol | 12.58839 | 12.58839 |
| EV | 0.02518 | 0.02518 |
| median | -0.00010 | -0.00010 |
| PF | 295.11745 | 295.11745 |
| win_rate | 0.08200 | 0.08200 |
| by_day | {"2026-09-02": 0.04300021950170648, "2026-09-03": -4.908534920634921e-05, "2026-09-04": -7.770461111111111e-05} | {"2026-09-02": 0.04300021950170648, "2026-09-03": -4.908534920634921e-05, "2026-09-04": -7.770461111111111e-05} |
| by_day_N | {"2026-09-02": 293, "2026-09-03": 189, "2026-09-04": 18} | {"2026-09-02": 293, "2026-09-03": 189, "2026-09-04": 18} |
| top_user_share | 0.84170 | 0.84170 |
| top_token_share | 0.84170 | 0.84170 |
| CI_user_day | [0.0008926936100746268, 0.10275245418879056] | [0.0008926936100746268, 0.10275245418879056] |
| CI_token_day | [-7.879957958477509e-05, 0.10417562987254901] | [-7.879957958477509e-05, 0.10417562987254901] |
| verdict | EXECUTED_ARB_MECHANISM_NOT_CONFIRMED | EXECUTED_ARB_MECHANISM_NOT_CONFIRMED |

Cicluri eliminate de regula multi-user: 0 (total net 0.0000 SOL); adăugate: 0. Exemple (hash): []
Ciclul dominant: net 10.6317 SOL (brut 10.6318; plătit 0.3159, primit 10.9477; 2 swap-uri; ziua 2026-09-02); users_in_tx (V1) = 1, users_for_token (V2) = 1; RETAINED_IN_V2 = True — retinut: un singur utilizator distinct pe tokenul ciclului in tranzactie (users_for_token=1), base conservat exact, orientare stricta, invariante valide.
FINAL_VERDICT_CHANGED = False (V1: EXECUTED_ARB_MECHANISM_NOT_CONFIRMED; V2: EXECUTED_ARB_MECHANISM_NOT_CONFIRMED).

## 2. Poarta de integritate a rezervelor (slow_capture.py)
Expresia `... or True` a fost eliminată; poarta cere acum zero încălcări (rupturi de lanț decizie→landing, stări de landing neprobabile, stări în outage/trunchiere). Test: slow_capture_gate_tests.py eșuează la orice încălcare (PASS).

## 3. Reconcilierea 127 / 86 / 16
```
{
 "pools_passing_all_four_prefilters": 127,
 "pools_listed_in_frozen_populations": {
  "PRIMARY_MEME": 6,
  "SECONDARY": 80,
  "total": 86
 },
 "pools_loaded_into_engine": 86,
 "pools_with_pass2_events": 86,
 "pools_noncanonical_strict_eligible_in_engine": 83,
 "canonical_pools_excluded_by_engine": 3,
 "tokens_listed": 16,
 "tokens_with_2plus_eligible_pools": 13,
 "explanation": "127 = pool-uri care au trecut cele patru prefiltre (strict, flux, VQ, schema de taxe) in toate grupurile; 86 = pool-urile efectiv listate in cele doua populatii inghetate (6 PRIMARY_MEME + 80 SECONDARY) \u2014 diferenta 41 = pool-uri eligibile individual dar fara o a doua pereche eligibila cu ferestre curate in grupul lor; 16 = token-uri listate (3 + 13); motorul V2 a evaluat efectiv doar pool-urile noncanonice stricte, excluzand cele 3 canonice, deci PRIMARY_MEME nu a fost evaluat"
}
```

## 4. Canonical
Motorul V2 exclude necondiționat pool-urile canonice (3 excluse). Prin urmare evaluarea slow-capture este o evaluare SECONDARY/NONCANONICAL; populația înghețată nu a fost modificată și nu s-au improvizat tiere de taxe. CANONICAL_POPULATION_ACTUALLY_EVALUATED = NO. Rezultatul rămâne 0 episoade / SLOW_CAPTURE_NO_VERIFIED_EDGE.

## 5. Etichetări
- Costul de rețea (0,000105 SOL per tranzacție; 0,00021 SOL dus-întors) este o PRESUPUNERE de model (semnătură 5.000 + prioritate 100.000 lamports), nu o taxă on-chain observată; scenariile de stres rămân presupuneri.
- „Boți” se înlocuiește cu „conturi executante compatibile cu activitate automatizată”; dovada directă există doar pentru atomicitate (evenimente în aceeași semnătură), nu pentru identitatea operatorului.
- Pentru testele sub pragul minim (S2, S3 cu N=2, S4, S5) p-value și CI sunt n/a în V2 (`*_results_v2.json`); `common.boot` returnează None sub prag.

## 6. Teste și validatoare
MULTIUSER_TESTS PASS; RESERVE_GATE_TESTS PASS; property/fuzz True (3000 cazuri); vezi ALL_TESTS_PASS în rezumat.