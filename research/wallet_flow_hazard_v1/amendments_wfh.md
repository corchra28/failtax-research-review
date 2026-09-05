# Amendamente dupa inghetare (WALLET_FLOW_HAZARD_V1) — transparenta

1. **Scurgere in modelul de hazard, detectata de testele obligatorii** (future-mutation pe date reale 1408/5833 si permutarea istoricului portofelelor fara prabusire): (a) probabilitatea de intrare folosea `bins[0].value_ratio` = raportul executabil la 60 s DUPA decizie; (b) covariatele person-period ale bin-ului b erau contemporane cu evenimentul din bin-ul b. Prima rulare (EV +0,113, PF 3,5, 77 semnale) este INVALIDA si nu este raportata ca rezultat.
   Corectie: raportul la intrare (fara nicio stare ulterioara) si covariate lagate (cunoscute la inceputul bin-ului); hazardul folosit de exitul dinamic la sfarsitul bin-ului b prezice bin-ul b+1. Rebuild + refit fara schimbarea grilei, pragurilor sau a portilor.
