# REMEDIERE DUPĂ REVIZUIREA EXTERNĂ — taxe, timing, overlay (2026-09-04)

Artefacte: research/external_review_remediation.py, research/external_review_remediation.json. Nicio ieșire anterioară nu a fost modificată; rezultatele REGIME rămân așa cum au fost publicate, cu contaminarea cuantificată mai jos.

## A. entry_fee_bps = 0 în pool_outcomes (horizon 5, sursa prospectivă)
- Rânduri prospective: 973. Rânduri cu taxă de intrare 0: **102 (10,5 %)**.
- Cauză: motorul copia bps-urile ultimului Buy/SellEvent ≤ intrare; 2.322 de evenimente din bandă au lp = protocol = 0 (evenimente speciale legate de migrare/fee-exempt; niciunul nu este primul eveniment al pool-ului), iar când un astfel de eveniment preceda intrarea, taxa noastră ipotetică devenea zero.
- Taxa corectă din starea pool-ului (resolver, tabel de tiere după market cap) pe cele 102 rânduri: distribuție 30–125 bps (cel mai frecvent 120 bps: 25 rânduri; 115: 10; 90: 8; 60: 8; 30: 9).
- PnL agregat al rândurilor afectate: **înainte +$22.12 (medie +$0.22); corectat −$3.55 (medie −$0.03); impact −$25.66** pe TP100/SL30/300 s.

## B. Fee resolver corect
- Canonical PumpSwap (index 0, creator = PDA „pool-authority" al pump.fun pentru base_mint, quote WSOL): tabelul din pumpswap_fees.py, total 125 → 30 bps monoton descrescător după market cap; valorile fracționare (27,5 / 22,5 / 17,5 / 12,5 / 7,5 bps creator) rotunjite conservator în sus la bp întreg.
- Noncanonical: 25 lp + 5 protocol + 0 creator = 30 bps; confirmat de 21.935.354 evenimente observate în pool-urile noncanonice (unica valoare observată: 25/5/0).
- Identificarea pool-ului: exactă (inventar CreatePoolEvent: index, creator, mint-uri), nu prin lichiditate.
- Teste: toate tierele > 0, monotone; canonical_fee_total > 0 pentru toate stările executabile (200.000 stări); comparație cu 200.000 de swap-uri ordinare observate: **199.241 potriviri (99,6 %)**, 759 nepotriviri (exemple: creator 147 vs 95 bps la mcap ~570 SOL; 2/93/30 în loc de 20/5/95 la mcap ~421 SOL — praguri de tier la limită sau evenimente cu taxă specială); evenimentele cu taxă zero (2.322) raportate separat și niciodată copiate.
- FEE_RESOLVER_VALID = YES.

## C. Audit de existență și timing
- Shadow-uri: 1.559. Intrări înainte de crearea pool-ului (entry_ts < pool_creation_ts): **7** (09-01: 4, 09-02: 1, 09-03: 2; întârzieri 4–15 s între Complete și crearea pool-ului). ID-uri hash-uite: e043cd23370b660f80f7877edc5fb68d, 93566fa4cf242c8972c30cb91c5806f1, 33784bd55a70e0b24d664afdd856e726, 7b97399d184279e99af232810ce278d1, f8a8b55595b6ce614a6029906e37ab1d, b0d0e387742ee81a182113d4855d5106, 39339665ed2b519f93d0ebd59f52b308.
- Regulă: aceste simulări trebuie EXCLUSE, nu mutate. Nu au fost recalculate tacit.

## D. Contaminarea rezultatelor REGIME (raportată, nerecalculată)
- Shadow-uri prospective: 973; cu taxă de intrare 0: **106 (10,9 %)**; corecția medie a PnL-ului pe cele 106: −$0.25; suma −$26.33. Tranzacții ON afectate: 0 (cele 5 tranzacții ON nu au taxă zero). Verdictul REGIME_GATE_INSUFFICIENT_SAMPLE nu este afectat în direcție; baseline-ul necondiționat F ar fi mai negativ cu ~$26 pe 973 de rânduri.

## E. Overlay-ul static
Overlay-ul „rezerve viitoare observate + poziția noastră" nu este un counterfactual protocol-exact pentru strategiile direcționale: tranzacțiile ulterioare ale altora s-ar fi executat pe o stare modificată de poziția noastră și unele nu s-ar fi produs. Nu s-a încercat repararea strategiilor direcționale. Arbitrajul atomic nu are această problemă: ambele leg-uri se evaluează consecutiv pe starea de landing.
