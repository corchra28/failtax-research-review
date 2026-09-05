# Amendamente dupa inghetarea specificatiei (transparenta)

Specificatia a fost inghetata (`frozen_spec.json`, sha256 ed2725fc…) inainte de orice etichetare. Modificarile de cod de dupa inghetare, toate FARA a inspecta vreun rezultat de etichetare/model:

1. `curve2x_lib.py`: adaugate `gap_windows_from_create_times` si `known_gap` (garda de gap ceruta de FAZA 8, regula 31) — functie pura, folosita identic de batch si de watcher.
2. `model_stage.py`: `score_rows` calculeaza `gap_known` cu aceeasi functie (in loc de `False` constant), pentru ca deciziile batch si replay sa fie identice.
3. `test_curve2x.py`: nicio modificare de logica dupa inghetare (corectiile de constructie a cazurilor sintetice au fost facute inainte de inghetare).

Hash-urile finale ale codului sunt in `reproducibility_manifest.json`; hash-urile de la inghetare raman in `frozen_spec.json` (nu se rescrie).

4. `tape_pass.py`: constanta programului pentru PDA-ul `pool-authority` era programul PumpSwap in loc de pump.fun (`6EF8…`), astfel niciun pool nu era marcat canonic si splice-ul nu se putea demonstra (splice_ok=0/2739 la prima constructie). Corectat; trecerea peste banda si constructia au fost rerulate; flag-ul canonic derivat este comparat cu metadatele PHASE 1 (raportat in manifest). Nicio selectie de model nu fusese facuta.
5. `label_check.py` (a doua implementare): returna UNAVAILABLE pentru pozitiile rezolvate pe curba INAINTE de migrare cand splice-ul lipsea (bug al verificatorului, nu al etichetei; primul LABEL_AGREEMENT = 77,8 % din aceasta cauza). Corectat: UNAVAILABLE doar daca nu exista rezolvare inainte de slotul de completare.

## COMPLIANCE_ONLY (2026-09-05, dupa raport)
6. `model_artifact.json`: adaugate `policy_enabled=false`, `final_verdict="NO_VERIFIED_EDGE"` (parametri neschimbati; hash-ul artefactului se schimba, vezi `amendments_manifest.json`).
7. Watcher: `PAPER_CANDIDATE` numai daca `policy_enabled` AND `final_verdict=="PAPER_CANDIDATE"` AND `grid_feasible>0`; altfel randurile eligibile devin `WATCH` cu motivul `ELIGIBLE_POLICY_DISABLED`. Replay repetat: 0 candidati.
8. Cai efemere eliminate: `CURVE2X_DERIVED_DIR` (implicit `research/curve2x_v2/derived/`, negit-uit). Testele sintetice ruleaza din repo fara date private.
9. `frozen_spec.json` -> `frozen_spec_V1_REJECTED.json` (continut identic). Nu se pretinde sealed/preregistered. Manifest machine-readable: `amendments_manifest.json`.
10. `publish.sh`: token exclusiv din `GITHUB_TOKEN` sau `gh auth token`; SHA256SUMS doar pentru `published_files.txt`; validator public `validate_public.py`.
11. Poarta `beats_state_headroom_baseline` marcata N/A (baseline si politica au 0 semnale). Nicio cifra recalculata, niciun retraining, nicio cautare de praguri.
