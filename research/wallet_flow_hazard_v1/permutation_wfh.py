"""Test de permutare pe date reale: istoricul portofelelor este permutat INTRE portofele (fiecare portofel primeste lista de pozitii a altui portofel, aleator), trasaturile A/B sunt
recalculate pentru randurile VAL+CONF si rescorate cu artefactul inghetat (fara reantrenare); daca EV-ul selectat se prabuseste, semnalul provine din track record-ul cauzal al portofelelor.
Plus: future-mutation pe date reale — adaugarea de pozitii cu maturitate DUPA decizie nu schimba trasaturile."""
import os,sys,gzip,json,random,collections,bisect,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import wfh_lib as W, build_wfh as B, model_wfh as M; V=W.V; L=W.L
D2=B.D2; DW=B.DW; art=json.load(open(os.path.join(HERE,"model_artifact.json"))); pol=art["policy"]; sel=art["model"]
rows=[json.loads(l) for l in gzip.open(f"{DW}/wfh_rows.jsonl.gz","rt")]; target={(r["mint"],r["landmark"]) for r in rows if r["split"] in ("VAL","CONF")}
G=W.WalletGraph(); CG=W.CreatorGraph(); creates=[]
with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
    for line in f:
        r=json.loads(line); creates.append(r["create_ts"])
        if r["trades"]: G.add(W.wallet_positions_for_mint(r)); CG.add(W.creator_history_for_mint(r))
G.finalize(); CG.finalize(); creates.sort()
# permutare: listele de pozitii permutate intre portofele (first_seen permutat impreuna)
rng=random.Random(20260905); keys=list(G.P.keys()); perm=keys[:]; rng.shuffle(perm); Gp=W.WalletGraph(); Gp.P={a:G.P[b] for a,b in zip(keys,perm)}; Gp.first_seen={a:G.first_seen[b] for a,b in zip(keys,perm)}
# future mutation: graf cu pozitii suplimentare cu maturitate dupa decizie (nu trebuie sa schimbe trasaturile)
mints={m for m,_ in target}; recs={}
with gzip.open(f"{D2}/curve2x_curves.jsonl.gz","rt") as f:
    for line in f:
        m=line[9:60].split('"')[0]
        if m in mints: recs[m]=json.loads(line)
idx={(r["mint"],r["landmark"]):r for r in rows}
def feats_with(Gx,extra=None):
    out={}
    for (m,lm) in target:
        r=idx[(m,lm)]; rec=recs[m]; lr=(bisect.bisect_right(creates,r["ts"])-bisect.bisect_left(creates,r["ts"]-600))/10.0; out[(m,lm)]=W.features(rec,r["i"],r["ts"],lm,Gx,CG,lr)
    return out
Fp=feats_with(Gp)
# future-mutation PER RAND: pentru fiecare rand, pozitii 'castigatoare' cu maturitate DUPA decizia acelui rand sunt adaugate temporar cumparatorilor sai; trasaturile randului trebuie sa ramana identice
same=0; tot=0
for (m,lm) in sorted(target)[:600]:
    r=idx[(m,lm)]; T=recs[m]["trades"][:r["i"]+1]; added=[]
    for t in T[-20:]:
        if t[7]: G.P.setdefault(t[4],[]).append((r["ts"]+1,1,0.5,1,0.25)); added.append(t[4])
        if t[4] not in G.first_seen: G.first_seen[t[4]]=r["ts"]+1
    lr=(bisect.bisect_right(creates,r["ts"])-bisect.bisect_left(creates,r["ts"]-600))/10.0; f=W.features(recs[m],r["i"],r["ts"],lm,G,CG,lr); tot+=1; same+=all(f.get(x)==r["f"].get(x) for x in W.FEATS)
    for u in added: G.P[u].pop()
print("future_mutation identical",same,"/",tot,flush=True); target_n=tot
def evaluate(fmap,tag):
    rr=[dict(idx[k],f=fmap[k]) for k in target if idx[k]["lab"]["bounds"].get("status")=="OK"]
    raw=np.array([[r["f"].get(k) if r["f"].get(k) is not None else np.nan for k in W.FEATS] for r in rr],float); med=np.array(art["train_median_raw"]); raw=np.where(np.isnan(raw),med,raw); X,_=L.X_of(rr,W.FEATS,np.array(art["fill"]))
    if sel=="H": P=np.array([M.hazard_probs(art["hazard"],x,(r["bins"][0]["value_ratio"] if r["bins"] else 0.97)) for r,x in zip(rr,raw)]); P=P/P.sum(1,keepdims=True)
    else: P=L.predict(art["gbm"],X)
    Pc=L.apply_cal(art["cal"][sel],P); ev=L.pred_gbm_reg(art["reg"],X); by=collections.defaultdict(list)
    for k,r in enumerate(rr): by[r["mint"]].append((r["landmark"],k))
    ks=[]
    for m,lst in by.items():
        for lm,k in sorted(lst):
            if lm>=pol["Lmin"] and Pc[k,0]>=pol["p_tp_min"] and ev[k]>0: ks.append(k); break
    ks=[k for k in ks if M.usable(rr[k])]; v=[rr[k]["lab"]["bounds"]["conservative"]["pnl"] for k in ks]; st=M.stats(v); print(tag,{k:(round(x,4) if isinstance(x,float) else x) for k,x in st.items() if k in ("usable","EV","PF","CI95")},flush=True); return st
orig=evaluate({k:idx[k]["f"] for k in target},"ORIGINAL"); perm_=evaluate(Fp,"PERMUTED_WALLET_HISTORY")
json.dump(dict(label="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED",future_mutation=dict(identical=same,total=target_n,PASS=(same==target_n)),permutation=dict(original=orig,permuted=perm_,collapse=bool((perm_.get("EV") or 0)<0.5*(orig.get("EV") or 0) or (perm_.get("usable") or 0)<0.5*(orig.get("usable") or 1)))),open(os.path.join(HERE,"leakage_report.json"),"w"),indent=1,default=float); print("PERM_DONE")
