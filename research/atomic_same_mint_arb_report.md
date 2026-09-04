# ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE — RAPORT (2026-09-04, revizuit după review-ul commit-ului 6dfce002) — POST_HOC_HISTORICAL

FINAL_VERDICT = ATOMIC_ARB_INSUFFICIENT_EXISTING_DATA (poarta de fezabilitate picată și înainte de cerința de token program; niciun spread, profit sau outcome calculat)

## 0. Protocol
Ipoteza înregistrată ca NEW_STRUCTURAL_LANE înainte de orice calcul; auditul de taxe și timing executat primul (research/external_review_remediation_report.md). Cele 10 blocante ale primei revizuiri și cele 7 defecte ale celei de-a doua (TR nedefinit în stage_run, excludere necondiționată, canonical+canonical, regula populației din spec, ordinea încărcării în validator, dependențele pda/pumpswap_fees în pachet, validatorul rulează efectiv testele) sunt corectate. Testele 5, 8 și 9 sunt comportamentale (apelează pair_allowed_for_pnl, episode_first_flags, final_gate și eșuează dacă logica este eliminată). Fără RPC/API/WSS, fără date noi, fără PnL, fără live.

## 1. Inventar (trecerea 1) — banda 2026-09-02 13:18 → 09-04 08:01
BuyEvent 20.978.631, SellEvent 21.291.584, CreatePoolEvent 6.763; Deposit/Withdraw absente (nedecodate de colector) ⇒ lichiditatea se observă doar ca rupturi de lanț (excludere per pool în (decizie, landing s+2]). Pool-uri create în bandă 6.763: canonical 1.947 (index 0 + creator = PDA pool-authority pump.fun; 1.839 cu quote WSOL, 108 cu quote USDC), noncanonical 4.816 (4.714 cu base = WSOL, orientare inversă). Pool-uri active 32.491, dintre care ~25.700 create înainte de bandă.

## 2. Derivare locală zero-RPC (research/atomic_same_mint_arb_derivation.json)
Validare: PDA ["pool", u16_le(0), pool-authority(token), token, WSOL] sub PumpSwap reproduce adresa reală pentru **1.839/1.839** pool-uri canonice cu quote WSOL create în bandă (cele 108 nepotriviri sunt exact pool-urile canonice cu quote USDC, în afara regulii).
| Câmp | Valoare |
|---|---|
| INDEX_GT0_SOL_POOLS | 67 (toate index 1, toate active, 66 cu mint sufix „pump", 1 cu orientare strictă) |
| DERIVED_CANONICAL_ADDRESSES | 67 |
| DERIVED_CANONICAL_ACTIVE_MATCHES | 0 (niciun pool canonical derivat nu are Buy/Sell în bandă) |
| STRICT_ORIENTATION_MATCHES | 0 |
| REVERSED_ORIENTATION_MATCHES | 0 |
| PAIRS_WITH_BOTH_EVENT_STREAMS | 0 |
| OVERLAP_WINDOWS_GT2 | 0 |
| DATES_WITH_OVERLAP | 0 |
Extindere informativă (în afara regulii index > 0): pentru toate cele 4.786 pool-uri noncanonice cu WSOL pe o parte, pool-ul canonical derivat este activ în bandă pentru **1** (orientare strictă, ambele active) ⇒ cel mult o pereche recuperabilă zero-RPC.

## 3. FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM
| Criteriu | Rezultat |
|---|---|
| ≥ 20 perechi duplicate stricte | 0 → FAIL |
| ≥ 100 ferestre de suprapunere > 2 sloturi | 0 → FAIL |
| ≥ 2 date UTC | 0 → FAIL |
| rezerve + fee resolver valide | resolver valid, chain n/a → FAIL |
| fără gap/corupție (boolean, până la landing s+2) | fără ferestre → FAIL |
FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM = FAIL ⇒ STOP fără spec înghețată, motor sau PnL. Token program: neobservabil în evenimente; maparea explicită research/token_program_map.json este goală ⇒ rămâne prerechizit doar pentru PnL (PREREQUISITE_MISSING_FOR_PNL = token_program_per_mint), nu pentru numărarea perechilor.

## 4. Prerechizite rămase (nu se execută fără aprobare)
- maparea pool → mint pentru pool-urile create înainte de bandă (o citire de cont per pool) sau o bandă mai lungă în care pool-urile canonice ale celor 67 mint-uri cu pool secundar sunt active;
- owner-ul mint-ului (program token) pentru mint-urile din perechile recuperate;
- decodarea Deposit/Withdraw în colector pentru consistență 100 % a lanțului fără excluderi.

## 5. Corecțiile implementate (research/atomic_same_mint_arb.py, teste în research/atomic_same_mint_arb_tests.py, validator în research/atomic_same_mint_arb_validate.py)
Orientare strictă cu assert în motor; rupturi de lanț per pool; gap/trunchiere boolean până la landing s+2; data ferestrei din slotul de început; token program prin mapare explicită (SPL Token permis, Token-2022 exclus, necunoscut exclus); VQ ≥ 5 observații, nenegativ, IQR ≤ max(0,02 SOL, 2 %); staleness = max(s − last_A, s − last_B) plus separat; o tranzacție per episod (episode_first_flags); poarta completă (final_gate) cu segments_positive, zero_violations extins și no_post_hoc verificat față de spec; PF = +inf fără pierderi; TR definit în stage_run; canonical+canonical exclus explicit; regula populației din spec aliniată cu implementarea; validatorul încarcă rezultatele înaintea utilizării, cere dependențele pda/pumpswap_fees și rulează efectiv testele.
