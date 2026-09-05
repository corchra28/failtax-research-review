# FAZA 0 — AUDITUL ranker_2x V1 (HISTORICAL_REMEDIATION_NOT_SEALED)

Sursa auditata: commit-urile `1bf946a4a882a1405ad978cde9d3efcd3b9b21fb` (2026-09-05 11:04:13 +0300, 15 fisiere) si
`dd1493716d78bfeb8c4e8ff4ba2bba0630719330` (11:04:57 +0300, EXPECTED_NET din medii conditionate pe validation).
Copie nemodificata a starii `dd14937` in `research/ranker_2x/v1/` (16 fisiere + `SHA256SUMS_v1.txt`); verificare `git diff --quiet dd14937` pe fiecare fisier: niciunul modificat.
Manifestul V1 reconstruit: `audit_v1.json` (blob-uri git per fisier, hash-urile din `reproducibility_manifest.json`).

| Intrebare | Constatare V1 | Consecinta pentru V2 |
|---|---|---|
| Definitia P_2X | `p2x_{5M,15M,30M}` = 1 daca lichidarea executabila (overlay static, taxa 125 bp, plafon rezerva reala) atinge >= 2 x notional la ORICE stare din orizont (`labels()`, `first2x`), independent de ce s-a intamplat inainte | eticheta de tip "maxim atins", nu first-passage |
| Definitia P_LOSS_50 | `loss50` = 1 daca lichidarea la SFARSITUL orizontului de 30 min <= 0,5 x notional (`end<=0.5*gross`); nu este un stop-loss, ci starea terminala | nu masoara drawdown-ul intermediar |
| Independente sau first-passage? | independente: un rand poate avea simultan `p2x_30M=1` si `loss50=1`; probabilitatile nu insumeaza 1 si nu descriu o politica cu SL | V2: trei stari mutual exclusive TP_FIRST / SL_FIRST / TIMEOUT_OTHER |
| Traiectorie -50 % apoi 2x | etichetata `p2x=1` (eticheta gresita pentru orice politica cu SL); `policy_pnl` V1 nu are SL deloc (TP la 2x, altfel iesire la 30 min) | V2: SL_FIRST, niciodata TP_FIRST |
| Checkpoint-uri | varsta fixa 5/15/30/60 s dupa CreateEvent (`CHK=[5,15,30,60]`), NU praguri de progres | V2: landmark-uri de progres 10..80 % |
| Deduplicare per mint | randuri per (mint, checkpoint); evaluarea principala pe randuri (1.276 randuri = 896 mint-uri); nivelul de mint (primul checkpoint PAPER_BUY) adaugat DUPA vederea rezultatelor | V2: exact o decizie per mint, by construction |
| Pragul 0,3421 | ales pe RANDURI de validation (cel mai mic prag cu EV stresat > 0 si >= 30 randuri; la 0,3421: 1.039 randuri, EV stresat +0,0081) | V2: grila fixa de politica pe CAL, LCB90 la nivel de mint |
| top-1/5/10 % | row-level (`lift_at` pe randurile de test) | V2: mint-level |
| Splice curba -> PumpSwap | NU: la CompleteEvent bucla se opreste (`censored=1`, 1,3 % din randuri) si pozitia este marcata la ultima stare de curba (neexecutabila dupa migrare) | V2: continuare in pool-ul canonic cu rezerve efective; altfel CROSS_MIGRATION_LABEL_UNAVAILABLE |
| EXPECTED_NET per semnal | 1bf946a: euristica `p*N - (1-p)*0.3N - cost`; dd14937: `p*E_val[pnl|2x] + (1-p)*E_val[pnl|nu 2x]` cu medii conditionate GLOBALE pe validation per notional; probabilitatea modelului 0,25 SOL extrapolata la 0,50/1,00 SOL | V2: regressor cross-fitted pe PnL exact, per notional, cu LCB90 |
| Calibrarea in regiunea p >= 0,3421 | bin 0,30-0,40: pred 0,336 / obs 0,367 (n=2.683); 0,40-0,50: 0,443 / 0,529 (n=189); 0,50-0,60: 0,524 / 0,622 (n=45) => subestimare de 3-10 pp in zona tranzactionata, mascata de ECE global 0,007 | V2: ECE si gap raportate exclusiv in regiunea eligibila |
| Rezultate per zi dupa dedup per mint | 09-03: 567 mint-uri, EV +0,0083 SOL, PF 1,08; 09-04: 329 mint-uri, EV -0,0042 SOL, PF 0,96 => "STABLE_ACROSS_DAYS = YES" din V1 era valabil doar la nivel de rand | V2: stabilitate judecata pe VAL si CONF la nivel de mint |

Alte constatari: RF-lite a avut un defect de semn in prima rulare (corectat inainte de rularea finala V1); notional-urile 0,50/1,00 SOL au EV negativ la nivel de mint
(-0,036 / -0,210 SOL); testul V1 nu este sealed (toate zilele fusesera inspectate anterior). Concluzia auditului: V1 este un ranker de probabilitate
"maxim atins", nu o politica executabila cu SL; V2 reformuleaza complet eticheta si unitatea de decizie.
