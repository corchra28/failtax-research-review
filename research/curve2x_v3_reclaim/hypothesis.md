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
