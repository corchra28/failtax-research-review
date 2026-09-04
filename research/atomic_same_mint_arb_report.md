# ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE — RAPORT (2026-09-04, PHASE 1 POOL METADATA RECOVERY) — POST_HOC_HISTORICAL

STATUS = STOP OBLIGATORIU DUPĂ FEZABILITATE. FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM = **PASS**. Fără spread, fără PnL, fără freeze de motor. Următorul pas cere aprobare separată: citirea owner-ului (programului token) pentru mint-urile candidate.

## 1. Recuperarea metadatelor (aprobare explicită; research/pool_metadata_recovery.py)
Înghețat înainte de apeluri (research/pool_metadata_recovery_manifest.json): lista ordonată a 32.491 pool-uri (sha256 3c496bc0…), 325 batch-uri × 100, getMultipleAccounts, commitment finalized, base64, dataSlice 0..107, discriminator sha256("account:Pool")[:8] = f19a6d0411b16dbc, timestamp 17:10:27 EEST, commit sursă 8460a117.
| Câmp | Valoare |
|---|---|
| TOTAL_ACCOUNTS_REQUESTED | 32.491 |
| RPC_REQUEST_COUNT | 325 (0 erori, 0 retry, 98 s) |
| ACCOUNTS_RECOVERED | 32.491 |
| NULL_ACCOUNTS / INVALID_OWNER / INVALID_DISCRIMINATOR / SHORT_DATA / DUPLICATES | 0 / 0 / 0 / 0 / 0 |
| CREATEPOOL_METADATA_MATCH_RATE | 1.000 (6.752 pool-uri comparate pe index, creator, base_mint, quote_mint; 0 nepotriviri) |
| UNIQUE_TOKEN_MINTS | 30.028 (pool-uri cu WSOL pe o parte; 2.015 pool-uri fără WSOL) |
| SAME_MINT_PAIRS_TOTAL (grupuri cu ≥ 2 pool-uri) | 123 (85 grupuri de 2 pool-uri; cele mai mari: 51, 49, 46, 35, 28, 20 pool-uri) |
| STRICT_STRICT_PAIRS (combinații) | 5.152 |
| STRICT_REVERSED_PAIRS | 131 |
| REVERSED_REVERSED_PAIRS | 1 |
| CANONICAL_NONCANONICAL_PAIRS | 115 |
| NONCANONICAL_NONCANONICAL_PAIRS | 5.169 (5.037 între pool-uri stricte) |
| CANONICAL_CANONICAL_PAIRS | 0 |
Orientări: STRICT 25.061, REVERSED 5.415, NO_WSOL 2.015; pool-uri canonice 24.267. Artefact public: research/pool_metadata_normalized.jsonl.gz (pool și mint în clar, creatorii hash-uiți cu namespace external-review-v1, flag creator_is_pump_authority; sha256 6daeaaf4…). Cache-ul brut rămâne local (sha256 30b66cd0…, nepublicat).

## 2. Ferestre din tape-ul existent (Buy/Sell; research/atomic_same_mint_arb_feasibility_rpc.json)
Pool-uri extrase: 571 (toate pool-urile din cele 123 de grupuri). Combinații de 2 pool-uri stricte cu ambele fluxuri prezente: 5.152 (canonical+noncanonical 115, noncanonical+noncanonical 5.037).
| Câmp | Valoare |
|---|---|
| ferestre de stare comună (dedup pereche × slot) | 335.074 |
| ferestre > 2 sloturi | 273.398 |
| ferestre > 2 sloturi CURATE (fără deconectare/trunchiere până la landing s+2, lanț de rezerve 100 % în fereastră) | **259.543** |
| pe zile UTC (curate) | 09-02: 59.163; 09-03: 173.191; 09-04: 27.189 |
| combinații cu ≥ 1 fereastră curată | 3.883 (105 token-uri) |
| rupturi de lanț (Deposit/Withdraw neobservate) | 904 din 83.093 perechi de evenimente; excluse din ferestre |
| VQ implicit calculabil (≥ 5 obs., nenegativ, IQR mic) | 138 din 567 pool-uri (restul vor fi excluse din motor) |
Observație structurală (fără PnL): ferestrele sunt dominate de token-uri majore cu multe pool-uri noncanonice (USDC ca „token" cu 51 de pool-uri SOL/USDC: 128.363 ferestre; alte 5 token-uri non-pump; PUMP), nu de lansări pump.fun; combinațiile canonical+noncanonical cu ferestre curate sunt puține și se concentrează pe câteva mint-uri pump.

## 3. FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM
| Criteriu | Rezultat |
|---|---|
| ≥ 20 perechi | 3.883 combinații / 105 token-uri → PASS |
| ≥ 100 ferestre curate > 2 sloturi | 259.543 → PASS |
| ≥ 2 zile UTC | 3 → PASS |
| ambele fluxuri prezente | 5.152 combinații → PASS |
| rezerve valide și lanț 100 % în fiecare fereastră folosită | fee resolver valid; ferestrele cu rupturi eliminate → PASS |
PASS. Conform protocolului (punctul 8): STOP.

## 4. Derivarea zero-RPC (revizuirea 2; research/atomic_same_mint_arb_derivation.json)
PDA validat 1.839/1.839 pe pool-urile canonice cu quote WSOL; 67 pool-uri index 1 → 0 canonice active; scanarea informativă a tuturor celor 4.786 pool-uri noncanonice cu SOL → 1 pereche cu canonicalul activ (CUHY8GEX… / CBVYy5xB… pentru 25NtaXA4…pump), inclusă ca artefact verificabil; consistentă cu recuperarea RPC (grupul respectiv apare printre cele 123).

## 5. Prerechizite rămase înainte de orice PnL (aprobare separată necesară)
- owner-ul mint-ului (program token) pentru cele 105 mint-uri candidate (o citire getMultipleAccounts pe ≤ 2 batch-uri) — necesar pentru excluderea Token-2022; NU s-a executat;
- apoi înghețarea motorului (spec + hash-uri) și abia apoi calculul spread/PnL.
Verdictul ramurii rămâne deschis: nu există încă niciun rezultat economic.

## 6. Prefiltrare înainte de mint RPC (revizuirea 3; research/atomic_same_mint_arb_populations_frozen.json, înghețat înainte de orice PnL)
Criterii ELIGIBLE_BEFORE_TOKEN_PROGRAM: ambele pool-uri STRICT, ambele fluxuri, VQ valid separat (≥ 5 obs., nenegativ, IQR ≤ max(0,02 SOL, 2 %)), schema de taxe observată compatibilă (canonical: triplete lp/protocol/creator în tabelul de tiere; noncanonical: 25/5/0), ≥ 1 fereastră curată > 2 sloturi cu lanț 100 % și fără outage/trunchiere. Din 571 pool-uri în grupuri: 567 stricte, 571 cu flux, 141 cu VQ valid, 548 cu schemă de taxe validă, **127 trec toate filtrele**. Poarta pe token-uri unice și ferestre deduplicate (token_mint, start_slot):
| Populație | UNIQUE_TOKENS | UNIQUE_POOLS | PAIR_COMBINATIONS | CLEAN_PAIR_WINDOWS | CLEAN_TOKEN_SLOT_WINDOWS | DATES | VQ_VALID_POOLS | FEE_VALID_POOLS | TOP1 | TOP3 | GATE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PRIMARY_MEME (canonical+noncanonical) | 3 | 6 | 3 | 148 | 148 (09-02: 73, 09-03: 71, 09-04: 4) | 3 | 6 | 6 | 75 % | 100 % | FAIL (token-uri 3 < 20; ferestre și zile PASS) |
| SECONDARY_ALL_NONCANONICAL | 13 | 80 | 477 | 27.124 | 3.807 (09-02: 1.327, 09-03: 2.256, 09-04: 224) | 3 | 80 | 80 | 52 % (USDC) | 77 % | FAIL (token-uri 13 < 20; ferestre și zile PASS) |
Dedup-ul economic la nivel de token (max o rută per token și slot; un trade per episod de dislocare la nivel de token; reset doar când max predicted între toate rutele ≤ 0) este implementat în token_episode_selection și testat pe un grup sintetic de 3 pool-uri (6 rute). Supply-ul hardcodat a fost eliminat: canonical folosește tierul demonstrat din evenimente (triplet nenul identic înainte și după stare) sau supply validat per mint; altfel starea este exclusă. Observație: tripletele de creator derivate din sume pentru tranzacții minuscule sunt zgomotoase (ex. 20/5/66 lângă 20/5/65), ceea ce a exclus 23 de pool-uri ca „schemă incompatibilă"; excluderea este conservatoare.
Mint RPC: pregătit, NEEXECUTAT — 16 mint-uri eligibile (3 primary + 13 secondary), 1 apel getMultipleAccounts (dataSlice 0..82: owner, mint_authority, supply, decimals, initialized, freeze_authority); fetch-ul cere aprobare explicită (gardă MINT_RPC_APPROVED). Deoarece ambele populații pică poarta pe token-uri unice, ramura atomică rămâne pe datele actuale la **ATOMIC_ARB_INSUFFICIENT_EXISTING_DATA**; populația secundară nu poate salva populația primară.
