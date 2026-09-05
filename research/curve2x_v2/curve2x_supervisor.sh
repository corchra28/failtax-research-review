#!/usr/bin/env bash
# CURVE2X V2 supervisor — PAPER-ONLY, replay pe banda existenta. Nu porneste colectoare, nu deschide RPC/WSS, nu trimite tranzactii.
# Utilizare: curve2x_supervisor.sh <tape_dir> <model_hash> <stop_file> [state.sqlite] [signals.jsonl]
set -u; HERE="$(cd "$(dirname "$0")" && pwd)"; SRC="${1:?tape_dir}"; MH="${2:?model_hash}"; STOP="${3:?stop_file}"; STATE="${4:-$HERE/state.sqlite}"; LOG="${5:-$HERE/signals.jsonl}"
PY="${CURVE2X_PYTHON:-python3}"; ulimit -v 3500000; MAX_RESTARTS=5; n=0
while [ ! -f "$STOP" ] && [ $n -lt $MAX_RESTARTS ]; do
  echo "SUPERVISOR | start #$n $(date -u +%FT%TZ) paper-only replay"
  nice -n 10 "$PY" "$HERE/curve2x_paper_watcher.py" --mode replay --source "$SRC" --paper-only --model-hash "$MH" --stop-file "$STOP" --state "$STATE" --signal-log "$LOG" --quiet
  rc=$?; echo "SUPERVISOR | exit rc=$rc"
  [ $rc -eq 0 ] && break
  [ $rc -eq 2 ] && { echo "SUPERVISOR | eroare fatala de garda (hash/schema/mod); nu se reporneste"; break; }
  n=$((n+1)); sleep 5
done
echo "SUPERVISOR | oprit; LIVE_TRADING_ENABLED=NO"
