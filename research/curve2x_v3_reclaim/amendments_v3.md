# Amendamente dupa inghetare (V3) — transparenta

Spec inghetat: `frozen_spec.json` (sha a097ae32…), inainte de orice outcome. Modificari de cod ulterioare, toate corectii de bug fara legatura cu rezultatele (nicio selectie, niciun prag, nicio eticheta schimbata):

1. `watcher_v3.py`: `prune()` cadea pe un deque gol (IndexError) — garda `not d`; docstring-ul continea literal un token interzis de propriul self-check — reformulat.
2. `make_docs_v3.py` / `freeze_v3.py`: erori de sintaxa corectate inainte de rulare (fara impact pe rezultate).

Hash-urile finale ale codului sunt in `reproducibility_manifest.json`; hash-urile de la inghetare raman in `frozen_spec.json` (nu se rescrie).
3. `watcher_v3.py` / `v3_lib.py`: indexul de reutilizare a portofelelor acoperea in watcher si trade-urile pe lansari vechi/necunoscute (absente din fluxul batch), dand `wallet_reuse_share` mai mare in 139/1268 decizii (acord 89 %). Definitia clarificata: reutilizare doar peste lansari tinere (CreateEvent vazut, varsta <= 3720 s), identic in batch si streaming. Nicio alta trasatura nu diferea.
4. REMEDIERE (dupa raport): `simulate_v3` — migrarea conteaza doar daca CompleteEvent <= decizie + orizont (altfel CURVE_ONLY); `simulate_v3_bounds` — limite de ordine in slotul de aterizare (conservative/midpoint/optimistic, excludere CHAIN_BREAK); reevaluare FARA reantrenare si fara cautare de prag (`reevaluate_v3.py`, `results_remediated.json`); originalele pastrate in `original/` si `results_original.json`.
