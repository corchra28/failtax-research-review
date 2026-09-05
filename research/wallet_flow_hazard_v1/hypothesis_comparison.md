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
