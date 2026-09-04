# EXTERNAL REVIEW REPORT — overnight 2026-09-05 (POST_HOC_HISTORICAL_RESEARCH)

Commit: a900f9cc6ba3636110609df212452917348b4ef8. RPC 0, date noi 0, colectoare 0, live 0.

## Clasificare finala
| # | Strategie | Realism executie | Dovezi | Categorie |
|---|---|---|---|---|
| 1 | EXECUTED bot cycles (observed, not accessible) | observat real; necesita infrastructura de bot (aceeasi tranzactie, competitie in acelasi slot 100 %) | "N=500, EV 0.02518 SOL, PF 295.1, concentrare 84 %" | actual bot profits observed |
| 2 | SLOW_CAPTURE_V1 | ordinar +3 sloturi | "0 stari profitabile in populatia inghetata" | inaccessible / no verified edge |
| 3 | S6 router | executie | "EXECUTION_COST_REDUCTION_NOT_CONFIRMED" | execution-cost improvement (not confirmed) |
| 4 | S7 toxicity filter | filtru | "TOXICITY_FILTER_NO_VALUE" | loss-avoidance filter (no value) |
| 5 | S1 | directional, +3 sloturi | {"verdict": "FAIL", "N": 33638, "EV": -0.0067156819696771505, "PF": 0.5663254184637458} | failed / insufficient |
| 6 | S2 | directional, +3 sloturi | {"verdict": "INSUFFICIENT_CLEAN_SAMPLE", "N": null, "EV": null, "PF": null} | failed / insufficient |
| 7 | S3 | directional, +3 sloturi | {"verdict": "INSUFFICIENT_CLEAN_SAMPLE", "N": 2, "EV": 0.0011463575, "PF": Infinity} | failed / insufficient |
| 8 | S4 | directional, +3 sloturi | {"verdict": "INSUFFICIENT_CLEAN_SAMPLE", "N": 23, "EV": 0.00010120378260869534, "PF": 1.013436995606545} | failed / insufficient |
| 9 | S5 | directional, +3 sloturi | {"verdict": "INSUFFICIENT_CLEAN_SAMPLE", "N": 16, "EV": -0.00570685225, "PF": 0.4398229747654796} | failed / insufficient |
| 10 | H1 | directional (intrare la D) | "FAIL" | failed / insufficient |
| 11 | H2 | directional (intrare la D) | "INSUFFICIENT_CLEAN_SAMPLE" | failed / insufficient |
| 12 | H3 | directional (intrare la D) | "FAIL" | failed / insufficient |

## Corectie globala
Holm-Bonferroni pe toate testele primare ale noptii (m = 13: H1-H3, EXECUTED_ARB_MECHANISM, ARBER_PERSISTENCE, SLOW_CAPTURE, S1-S7); niciun test primar nu trece dupa corectie: True.

## Distinctii cerute
- profituri reale ale botilor observate: 500 cicluri, +12,59 SOL net total, 84 % de la un singur executor/token, castig in 8,2 % din cicluri; competitie in acelasi slot in 100 % din cazuri;
- profituri istorice teoretic executabile cu infrastructura obisnuita: niciunul verificat (slow capture 0 stari; S2 0 reziduuri; S1/S3/S4/S5 FAIL/INSUFFICIENT);
- profituri inaccesibile fara infrastructura premium: ciclurile executate (aceeasi tranzactie, primul slot);
- candidati directionali paper: niciunul;
- imbunatatiri de cost de executie: niciuna confirmata (pool-ul implicit este deja cel mai bun in >99 % din decizii; impartirea costa mai mult decat economiseste);
- filtre de conservare a capitalului: niciunul cu valoare (S7 NO_VALUE);
- strategii esuate: H1, H3, S1 (FAIL); H2, S2, S3, S4, S5 (INSUFFICIENT_CLEAN_SAMPLE); ARBER_PERSISTENCE (INSUFFICIENT); SLOW_CAPTURE (NO_VERIFIED_EDGE); EXECUTED_ARB_MECHANISM (NOT_CONFIRMED by concentration).

## Blocante nerezolvate
- programul token al mint-urilor (owner) neverificat (fara RPC);
- Deposit/Withdraw nedecodate de colector (ancore folosite in loc);
- transactionIndex absent (worst-of pre/post);
- istoricul creatorilor limitat la 43 h de banda;
- populatia slow-capture exclude pool-urile cu orientare inversa (unde s-au executat majoritatea ciclurilor reale).

READY_FOR_FRESH_FORWARD_TEST = NO; READY_FOR_LIVE_TRADING = NO.