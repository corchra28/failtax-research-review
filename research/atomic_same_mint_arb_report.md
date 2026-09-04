# ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE — RAPORT (2026-09-04) — POST_HOC_HISTORICAL

FINAL_VERDICT = ATOMIC_ARB_INSUFFICIENT_EXISTING_DATA (poarta de fezabilitate a picat; niciun spread, profit sau outcome nu a fost calculat)

## 0. Protocol
Ipoteza înregistrată în research/hypothesis_ledger.md ca NEW_STRUCTURAL_LANE înainte de orice calcul. Auditul de taxe și de timing (research/external_review_remediation_report.md) a fost executat primul. Cele 10 blocante din revizuirea externă au fost corectate și testate sintetic înainte de fezabilitate (PATCHED_BLOCKERS = 10/10; research/atomic_same_mint_arb_tests.py). Nu s-a executat freeze și nici stage_run. Fără date noi, fără API/RPC/WSS, fără modificarea benzii.

## 1. Inventar (trecerea 1, fără PnL) — strategy_m/data/tape, 2026-09-02 13:18 → 09-04 08:01
- Tipuri de evenimente PumpSwap în bandă: BuyEvent 20.978.631, SellEvent 21.291.584, CreatePoolEvent 6.763. DepositEvent/WithdrawEvent: **absente** (colectorul nu le-a decodat) ⇒ modificările de lichiditate sunt observabile doar ca rupturi ale lanțului de rezerve (tratate prin excludere per pool în intervalul decizie → landing s+2).
- Pool-uri create în bandă: 6.763 (canonical 1.947 = index 0 și creator = PDA pool-authority pump.fun; noncanonical 4.816). Pool-uri active (cu Buy/Sell): 32.491, dintre care ~25.700 create înainte de bandă, fără mint-uri observabile (Buy/SellEvent nu conțin mint-urile) ⇒ nejoinabile pe perechi.
- Orientare: 4.714 pool-uri au base_mint = WSOL (orientare inversă) și sunt excluse din populația primară (blocant 1; fără normalizare tacită); 1.911 au quote = WSOL.

## 2. Perechi duplicate
- Perechi stricte (base_mint = token, quote_mint = WSOL) cu ≥ 2 pool-uri: **0**.
- Informativ, neordonat {SOL, token} cu ≥ 2 pool-uri: **0**.
- Pool-uri cu index = 1: 67, toate cu SOL pe o parte, niciunul cu contrapartea index 0 creată în bandă (creată înainte de 09-02 13:18 ⇒ mint necunoscut din evenimente).
- Tipuri canonical+noncanonical / noncanonical+noncanonical: 0 / 0. Zile acoperite cu perechi: niciuna. Ferestre de suprapunere (dedup pe pereche și slot, > 2 sloturi, fără deconectări/trunchieri până la landing s+2): 0. Chain consistency pe perechi: n/a. VQ calculabil: n/a. Fee resolver: valid (vezi remediere).
- Program token: **neobservabil în evenimente** (owner-ul mint-ului nu este capturat) ⇒ PREREQUISITE_MISSING = token_program_per_mint; MINIMAL_RECOVERY_REQUIRED = o citire getAccountInfo per mint (sau captura owner-ului la CreatePool) — interzisă acum, neexecutată.

## 3. FEASIBILITY_GATE
| Criteriu | Rezultat |
|---|---|
| ≥ 20 perechi duplicate | 0 → FAIL |
| ≥ 100 ferestre de suprapunere > 2 sloturi | 0 → FAIL |
| ≥ 2 date UTC | 0 → FAIL |
| rezerve + fee resolver valide | resolver valid, chain n/a → FAIL |
| fără gap/corupție în intervalul necesar (boolean) | fără ferestre → FAIL |
| program token observabil | FALSE → FAIL |
FEASIBILITY_GATE = FAIL ⇒ STOP conform protocolului (secțiunea 3): fără spec înghețată, fără motor, fără PnL, fără optimizare.

## 4. Ce ar fi necesar (nu se execută fără aprobare)
Perechile duplicate există probabil (67 pool-uri index 1 dovedesc pool-uri secundare), dar identificarea contrapartei cere maparea pool → mint pentru pool-urile create înainte de bandă (o citire de cont per pool) și owner-ul mint-ului pentru excluderea Token-2022. Ambele sunt apeluri RPC, interzise în acest experiment.

## 5. Corecțiile celor 10 blocante (implementate în research/atomic_same_mint_arb.py, testate în research/atomic_same_mint_arb_tests.py)
1 orientare strictă (base = token, quote = WSOL; pool inversat respins prin assert și exclus din populație); 2 rupturi de lanț per pool, consistență 100 % cerută în (decizie, landing s+2]; 3 gap/trunchiere ca criteriu boolean, ferestrele care intersectează deconectări sau segmente trunchiate (2 detectate) eliminate până la landing s+2; 4 data ferestrei din timestamp-ul slotului de început; 5 program token nepresupus (PREREQUISITE_MISSING); 6 VQ: ≥ 5 observații, mediană nenegativă, IQR ≤ max(0,02 SOL, 2 %), altfel exclus (fără max(0, ·)); 7 staleness = max(s − last_A, s − last_B), raportat și separat; 8 o singură tranzacție per episod de dislocare (prima stare cu predicted > 0 până la închiderea spread-ului), replay-ul counterfactual de portofoliu nu este implementat și este declarat; 9 poarta completă: segments_positive, zero_violations acoperă invarianți, fee, timing, gap, VQ, program token; no_post_hoc verificat programatic față de spec; 10 PF = +inf fără pierderi.

## 6. Constrângeri
LIVE_TRADING = FORBIDDEN respectat; fără acțiuni de portofel; fără date noi; artefacte noi, separate; rezultatele REGIME nemodificate.
