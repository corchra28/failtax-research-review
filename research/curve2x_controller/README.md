# PROSPECTIVE_SELF_LEARNING_CONTROLLER (CURVE2X) — paper/shadow only

Comenzi (zero RPC, replay pe banda existenta; nu exista mod live):
```
python research/curve2x_controller/controller.py init
python research/curve2x_controller/controller.py run-cycle --mode replay --source strategy_m/data/tape --cutoff "2026-09-03 12:00" --paper-only
python research/curve2x_controller/controller.py evaluate | status | verify-journal
python research/curve2x_controller/promote.py --human-approval-file <json> --i-am-a-human   # refuza fara porti PASS + aprobare umana
```
Fluxul unui ciclu: Champion imuabil prezice in flux (jurnal append-only, lant de hash-uri) -> la cutoff labeler-ul separat eticheteaza predictiile maturizate ->
un singur Challenger antrenat doar pe outcome-uri maturizate cu embargo -> Champion + Challenger in shadow -> labeler la final -> evaluare prequentiala, drift, porti.
Nicio promovare automata, nicio schimbare de target/praguri. Drift sever => POLICY_ENABLED=false, ACTION=WATCH, REASON=MODEL_DRIFT.
Chiar cu toate portile PASS: READY_FOR_TINY_CAPITAL_REVIEW=YES, LIVE_TRADING_ENABLED=NO. Starea (`state/`) este locala si negit-uita (contine mint-uri brute in jurnal pentru labeler; publicarea foloseste doar mint_hash).
Rularea demonstrativa de aici este un REPLAY pe banda istorica deja inspectata, nu un forward real; forward-ul real cere date noi (neaccesate).
