"""CURVE2X V3 — leakage_report.json: (1) future mutation pe date reale (motorul streaming; pentru mint-uri de decizie cu ferestre disjuncte >= 7300 s, evenimentele proprii de dupa
decizie sunt eliminate din flux => trasaturi identice), (2) etichetele nu depind de trasaturi (simularea nu citeste f), (3) same-slot ordering (test sintetic), (4) o decizie per mint
(unicitatea mint-urilor in randuri), (5) nicio trasatura identificator. Zero RPC."""
import os,sys,gzip,json,random,collections
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L; from watcher_v3 import Stream
D2=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(HERE),"curve2x_v2","derived")); D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(HERE,"derived_v3"))
rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt")]; order=sorted(rows,key=lambda r:r["ts"]); SP=7300; PASSES=4
def pick(seed):
    rr=random.Random(seed); c=order[:]; rr.shuffle(c); ch=[]; tk=[]
    for r in c:
        if all(abs(r["ts"]-t)>=SP for t in tk): ch.append(r); tk.append(r["ts"])
    return ch
tot=same=missing=0; diffs=collections.Counter()
for p in range(PASSES):
    sample=pick(300+p); cut={r["mint"]:(r["seq"],r["k"]) for r in sample}; ref={r["mint"]:r["f"] for r in sample}; E=Stream()
    for line in gzip.open(f"{D2}/curve2x_stream.jsonl.gz","rt"):
        e=json.loads(line)
        if e[0]=="C": E.create(e[1],e[2],e[3],e[4],e[5])
        elif e[0]=="T":
            if e[5] in cut and (e[3],e[4])>cut[e[5]]: continue
            E.trade(e[1],e[2],e[3],e[4],e[5],e[6],e[7],e[8],e[9],e[10],e[11],e[12],e[13])
        elif e[0]=="X":
            if e[4] in cut: continue
            E.complete(e[4])
    got={d["mint"]:d["f"] for d in E.decisions if d["mint"] in ref}
    for m,f in ref.items():
        g=got.get(m); tot+=1
        if g is None: missing+=1; continue
        d=[k for k in V.FEATS if f.get(k)!=g.get(k)]
        if not d: same+=1
        for k in d: diffs[k]+=1
    print("pass",p,len(ref),"identical",sum(1 for m in ref if m in got and not [k for k in V.FEATS if ref[m].get(k)!=got[m].get(k)]),flush=True)
uniq=len({r["mint"] for r in rows})==len(rows); ids=[k for k in V.FEATS if k in ("mint","pool","user","signature","ts","seq","slot")]
tr=json.load(open(os.path.join(HERE,"test_results.json")))["tests"]
rep=dict(label="HISTORICAL_DEV_NOT_SEALED",future_mutation=dict(sampled=tot,identical=same,missing=missing,diff_features=dict(diffs),PASS=(same==tot and tot>0)),label_independent_of_features=tr["label_independent_of_features"]["pass_"],same_slot_ordering=tr["same_slot_SL_wins"]["pass_"],one_decision_per_mint=bool(uniq and tr["one_decision_per_mint"]["pass_"]),no_identifier_features=(not ids),PASS=bool(same==tot and tot>0 and uniq and tr["label_independent_of_features"]["pass_"] and tr["same_slot_SL_wins"]["pass_"] and tr["one_decision_per_mint"]["pass_"] and not ids))
json.dump(rep,open(os.path.join(HERE,"leakage_report.json"),"w"),indent=1); print(json.dumps(rep))
