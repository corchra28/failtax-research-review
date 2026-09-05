#!/usr/bin/env python3
"""CURVE2X V2 status (read-only): starea SQLite, jurnalul de semnale, checkpoint, model hash, stop file."""
import sqlite3,os,sys,json,hashlib,collections
HERE=os.path.dirname(os.path.abspath(__file__)); state=sys.argv[1] if len(sys.argv)>1 else os.path.join(HERE,"state.sqlite"); log=sys.argv[2] if len(sys.argv)>2 else os.path.join(HERE,"signals.jsonl")
print("MODE = replay (paper-only) | LIVE_TRADING_ENABLED = NO | RPC = none")
if os.path.exists(os.path.join(HERE,"model_artifact.json")): print("MODEL_HASH =",hashlib.sha256(open(os.path.join(HERE,"model_artifact.json"),"rb").read()).hexdigest())
print("STOP_FILE_PRESENT =",os.path.exists(os.path.join(HERE,"STOP")))
if os.path.exists(state):
    db=sqlite3.connect(state); print("CHECKPOINT =",db.execute("select file,seq from checkpoint where id=1").fetchone()); print("SIGNALS_BY_ACTION =",dict(db.execute("select action,count(*) from signals group by action").fetchall())); print("UNIQUE_MINTS_PAPER_CANDIDATE =",db.execute("select count(distinct mint) from signals where action='PAPER_CANDIDATE'").fetchone()[0])
else: print("STATE = absent")
if os.path.exists(log):
    c=collections.Counter(); n=0
    for l in open(log): n+=1; c[json.loads(l)["action"]]+=1
    print("SIGNAL_LOG_LINES =",n,dict(c))
