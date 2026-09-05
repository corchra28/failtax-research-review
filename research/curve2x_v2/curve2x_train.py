#!/usr/bin/env python3
"""CURVE2X V2 train (batch, offline): build_dataset -> label_check -> model_stage; afiseaza hash-urile. Fara RPC. Nu porneste procese persistente."""
import subprocess,sys,os,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE)); PY=sys.executable
for step in ("build_dataset.py","label_check.py","model_stage.py"):
    print(f"TRAIN | {step}",flush=True); rc=subprocess.call([PY,os.path.join(HERE,step)],cwd=ROOT)
    if rc!=0: print(f"TRAIN | {step} rc={rc}; oprire"); sys.exit(rc)
print("MODEL_HASH =",hashlib.sha256(open(os.path.join(HERE,"model_artifact.json"),"rb").read()).hexdigest())
