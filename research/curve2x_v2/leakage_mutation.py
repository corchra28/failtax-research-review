"""CURVE2X V2 — test de scurgere pe date reale: pentru randuri esantionate cu ferestre DISJUNCTE in timp (>= 7300 s intre decizii, ca viitorul unui mint mutat sa nu intre
in contextul trailing de regim/portofele/viteza al altui rand esantionat), toate evenimentele proprii de DUPA trade-ul declansator sunt eliminate din flux; motorul trebuie sa
emita trasaturi identice (58/58) pentru randul respectiv. 15 treceri x ~21 randuri. Zero RPC."""
import gzip,json,sys,os,random,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L
D=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(os.path.abspath(__file__)),"derived")); OUT="research/curve2x_v2"; SPACING=7300; PASSES=15
rows=[json.loads(l) for l in gzip.open(f"{D}/curve2x_rows.jsonl.gz","rt")]; rng=random.Random(7); order=sorted(rows,key=lambda r:r["ts"])
def pick(seed):
    rr=random.Random(seed); cand=order[:]; rr.shuffle(cand); chosen=[]; taken=[]
    for r in cand:
        if all(abs(r["ts"]-t)>=SPACING for t in taken): chosen.append(r); taken.append(r["ts"])
    return chosen
total=0; same=0; missing=0; diffs=collections.Counter(); per_pass=[]
for p in range(PASSES):
    sample=pick(100+p); cut={r["mint"]:(r["seq"],r["k"]) for r in sample}; ref={(r["mint"],r["landmark"]):r["f"] for r in sample}; E=L.Engine()
    for line in gzip.open(f"{D}/curve2x_stream.jsonl.gz","rt"):
        e=json.loads(line); m=e[4] if e[0]!="T" else e[5]
        if m in cut:
            if e[0]=="T" and (e[3],e[4])>cut[m]: continue
            if e[0]=="X": continue
        E.on_event(e)
    got={(r["mint"],r["landmark"]):r["f"] for r in E.rows if (r["mint"],r["landmark"]) in ref}; s=0
    for k,f in ref.items():
        g=got.get(k)
        if g is None: missing+=1; continue
        d=[x for x in L.FEATS if f.get(x)!=g.get(x)]
        if not d: s+=1
        for x in d: diffs[x]+=1
    total+=len(ref); same+=s; per_pass.append((len(ref),s)); print("pass",p,len(ref),"identical",s,flush=True)
res=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",spacing_s=SPACING,passes=PASSES,sampled=total,identical=same,missing=missing,diff_features=dict(diffs),per_pass=per_pass,PASS=(same==total),note="prima versiune a testului muta 300 de mint-uri simultan si detecta diferente in trasaturile de REGIM ale altor randuri (context, nu viitor propriu); refacut cu ferestre disjuncte")
json.dump(res,open(f"{OUT}/leakage_mutation.json","w"),indent=1); print(json.dumps({k:v for k,v in res.items() if k!="per_pass"}))
