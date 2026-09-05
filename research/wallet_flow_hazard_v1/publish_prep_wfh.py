"""WFH — scan + SHA256SUMS (doar fisierele publicate) + reproducibility_manifest.json."""
import os,re,json,hashlib,subprocess,time,sys
HERE=os.path.dirname(os.path.abspath(__file__))
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
files=[l.strip() for l in open(os.path.join(HERE,"published_files.txt")) if l.strip() and l.strip() not in ("SHA256SUMS.txt","reproducibility_manifest.json","validate_public.py")]
EPH=re.compile(r"/tmp/claude|scratchpad"); RAW=re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b"); hits=[f for f in files if os.path.exists(os.path.join(HERE,f)) and f!="publish_prep_wfh.py" and (EPH.search(open(os.path.join(HERE,f),errors="ignore").read()) or RAW.search(open(os.path.join(HERE,f),errors="ignore").read()))]
sums={f:sha(os.path.join(HERE,f)) for f in sorted(files) if os.path.exists(os.path.join(HERE,f))}; open(os.path.join(HERE,"SHA256SUMS.txt"),"w").write("".join(f"{h}  {f}\n" for f,h in sums.items()))
commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=HERE).stdout.strip(); json.dump(dict(label="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED",built=time.strftime("%Y-%m-%d %H:%M:%S %Z"),source_commit_at_build=commit,files_sha256=sums,hits=hits,rpc_calls=0,new_data=False,live=False,python=sys.version.split()[0]),open(os.path.join(HERE,"reproducibility_manifest.json"),"w"),indent=1); print(json.dumps(dict(files=len(sums),hits=hits)))
