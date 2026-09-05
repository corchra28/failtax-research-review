# CURVE2X V2 — automatizare PAPER-ONLY (HISTORICAL_REMEDIATION_NOT_SEALED)

Ce este: un watcher care ruleaza motorul de decizie CURVE2X (acelasi cod ca evaluatorul batch, `curve2x_lib.py`) peste o banda EXISTENTA
de evenimente pump.fun si emite exclusiv `REJECT` / `WATCH` / `PAPER_CANDIDATE`. Nu exista mod live: nu deschide RPC/WSS, nu semneaza,
nu trimite tranzactii, nu are chei. Singurul mod implementat este `--mode replay`.

Fisiere: `curve2x_train.py` (batch: build -> label check -> model), `curve2x_replay.py` (verifica AUTOMATION_REPLAY_AGREEMENT),
`curve2x_paper_watcher.py` (watcher), `curve2x_status.py` (stare read-only), `curve2x_supervisor.sh` (bucla de repornire cu stop file),
`curve2x-paper.service.example` (unit systemd EXEMPLU, neinstalat; `PrivateNetwork=true`), `schema.sql` (SQLite), `config.example.json`.

Rulare (replay pe banda existenta):
```
python research/curve2x_v2/curve2x_paper_watcher.py --mode replay --source strategy_m/data/tape --paper-only \
  --model-hash <sha256 model_artifact.json> --stop-file research/curve2x_v2/STOP
```
Garzi: `--paper-only` obligatoriu; `--mode` diferit de `replay` => FATAL; hash-ul artefactului trebuie sa coincida cu `--model-hash` (altfel procesul moare);
self-check pe cod (fara sendTransaction/chei/endpoint-uri) si pe mediu (fara variabile de chei); schema necunoscuta => contorizata, prag => FATAL;
gap (deconectari din `collector.log` + discontinuitati > 120 s intre CreateEvent-uri) => `DATA_GAP` => REJECT timp de 600 s; maximum un `PAPER_CANDIDATE` per mint
(index unic in SQLite + set in memorie); jurnal `signals.jsonl` append-only; checkpoint (fisier, seq) in SQLite => restart fara duplicate; stop file verificat la fiecare heartbeat;
`RLIMIT_AS` 3 GB si `nice`. Toate mesajele sunt linii `SIGNAL | ... | PAPER_ONLY` usor de copiat.

Ce NU face: nu porneste colectorul, nu citeste date noi, nu executa nimic pe blockchain. `READY_FOR_REAL_MONEY = NO`, `LIVE_TRADING_ENABLED = NO`.
