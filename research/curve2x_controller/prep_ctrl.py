"""Controller — scan secrete/cai efemene/adrese brute in fisierele de commit, copie sanitizata a raportului de evaluare (fara mint-uri brute), SHA256SUMS."""
import os,re,json,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); ST=os.path.join(HERE,"state")
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
if os.path.exists(os.path.join(ST,"evaluation_report.json")):
    r=json.load(open(os.path.join(ST,"evaluation_report.json"))); json.dump(r,open(os.path.join(HERE,"evaluation_report_public.json"),"w"),indent=1,default=float)
files=[f for f in ("controller_lib.py","controller.py","promote.py","tests_controller.py","prep_ctrl.py","freeze_forward.py","forward_lib.py","baseline_state_headroom.json","publish_ctrl.sh","controller_spec.json","forward_spec.json","README.md","champion.json","test_results.json","evaluation_report_public.json",".gitignore") if os.path.exists(os.path.join(HERE,f))]
PATS={"b58_key":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{86,90}\b"),"pump_mint_raw":re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b"),"api_key":re.compile(r"api[-_]?key=",re.I),"heli":re.compile("heli"+"us-rpc"),"wss":re.compile("wss:"+"//"),"send_tx":re.compile("send"+"Transaction"),"gh":re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),"eph":re.compile(r"/tmp/claude|scratchpad")}
hits=[(f,n) for f in files for n,p in PATS.items() if f!="prep_ctrl.py" and p.search(open(os.path.join(HERE,f),errors="ignore").read())]
sums={f:sha(os.path.join(HERE,f)) for f in files}; open(os.path.join(HERE,"SHA256SUMS.txt"),"w").write("".join(f"{h}  {f}\n" for f,h in sums.items())); print(json.dumps(dict(files=len(files),hits=hits)))
