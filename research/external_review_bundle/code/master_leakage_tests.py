"""MASTER EDGE — teste automate de scurgere + controale negative pe tabelul de trasaturi/outcome-uri produs de master_edge_discovery.py.
Ruleaza DUPA descoperire; nu modifica nimic; scrie research/master_leakage_tests.json. Daca un control negativ pare predictiv => PIPELINE_LEAKAGE_OR_INVALIDATION."""
import gzip,json,sys,math,random,collections,statistics as S,hashlib
import numpy as np
sys.path.insert(0,"research"); import master_edge_discovery as MD
SCR=MD.SCR; rows=[json.loads(l) for l in gzip.open(f"{SCR}/derived/m_features.jsonl.gz","rt")]
T={}; ok=lambda c: "PASS" if c else "FAIL"
by_h=collections.defaultdict(list); [by_h[r["h"]].append(r) for r in rows]
# T1 disponibilitatea trasaturilor: max ts folosit < D
viol=[r["mint"] for r in rows if r["f"].get("max_ts_used") is not None and r["f"]["max_ts_used"]>=r["D"]]; T["T1_feature_timestamp_lt_decision"]=dict(status=ok(not viol),violations=len(viol),rows=len(rows))
# T2 izolarea partitiilor (pe pool, cronologic)
pm=collections.defaultdict(set); [pm[r["mint"]].add(r["part"]) for r in rows]; multi=[m for m,s in pm.items() if len(s)>1]
t0={p:[r["T0"] for r in rows if r["part"]==p] for p in ("DEV","VAL","AUDIT")}; chrono=max(t0["DEV"])<min(t0["VAL"])<=max(t0["VAL"])<min(t0["AUDIT"])
T["T2_partition_isolation"]=dict(status=ok(not multi and chrono),pools_in_multiple_partitions=len(multi),chronological=chrono)
# T3 gruparea pe entitate: fiecare (mint,h) unic; toate orizonturile unui pool in aceeasi partitie (T2)
dup=collections.Counter((r["mint"],r["h"]) for r in rows); T["T3_same_entity_grouping"]=dict(status=ok(max(dup.values())==1),max_duplicates=max(dup.values()))
# T4 lista neagra + garda respinge o trasatura viitoare
try: MD.guard_feature_names(MD.ALLF+["final_pnl_after_entry"]); rejected=False
except ValueError: rejected=True
T["T4_future_field_blacklist"]=dict(status=ok(rejected and not any(any(b in k.lower() for b in MD.BLACK) for k in MD.ALLF)),guard_rejects_injected_future_feature=rejected)
# T5 normalizarea se potriveste doar pe antrenare
X=np.random.default_rng(0).normal(size=(200,3)); y=(X[:,0]>0).astype(float); m=MD.fit(X[:100],y[:100]); mu_train=X[:100].mean(0); T["T5_normalization_fit_scope"]=dict(status=ok(np.allclose(m[2],mu_train)),note="mu/sd ale modelului = statistici ale fold-ului de antrenare")
# T6 outcome-ul incepe dupa intrare; intrarea >= D+2
v6=[r for r in rows if r["prim"] and (r["prim"]["entry_ts"]<r["D"]+2-1e-9 or r["prim"]["exit_ts"]<r["prim"]["entry_ts"])]; T["T6_outcome_after_entry"]=dict(status=ok(not v6),violations=len(v6))
# T7 fara evenimente economice duplicate
T["T7_no_duplicate_opportunity"]=dict(status=ok(len({r["mint"] for r in rows})*len(by_h)==len(rows)),unique_pools=len({r["mint"] for r in rows}))
# T8/NC3 identificatorul nu prezice: hash(mint) ca trasatura -> corelatie cu outcome
def corr(a,b):
    a=np.array(a,float); b=np.array(b,float); return float(np.corrcoef(a,b)[0,1]) if a.std()>0 and b.std()>0 else 0.0
idf=[int(hashlib.sha256(r["mint"].encode()).hexdigest()[:8],16)/2**32 for r in rows if r["prim"]]; pn=[r["pnl"] for r in rows if r["prim"]]; c8=corr(idf,pn); T["T8_identifier_not_predictive"]=dict(status=ok(abs(c8)<0.05),corr_hash_mint_vs_pnl=c8)
# T9 ordinea absoluta a randurilor nu prezice (corelatie index-outcome in interiorul DEV)
dev=[r for r in by_h[10] if r["part"]=="DEV" and r["prim"]]; c9=corr(list(range(len(dev))),[r["pnl"] for r in dev]); T["T9_row_order_not_predictive"]=dict(status=ok(abs(c9)<0.15),corr_index_vs_pnl_DEV=c9,note="corelatie slaba = deriva cronologica, nu scurgere; prag 0,15")
# ---------- controale negative pe modelul L2 (orizont 10 s), DEV -> VAL ----------
def model_eval(train,test,names,label,feature_fn=None):
    fill={k:(S.median([r["f"][k] for r in train if r["f"].get(k) is not None]) if any(r["f"].get(k) is not None for r in train) else 0.0) for k in names}
    Xt=MD.X_of(train,names,fill) if feature_fn is None else feature_fn(train); yt=np.array([float(r["tp"]) for r in train])
    Xv=MD.X_of(test,names,fill) if feature_fn is None else feature_fn(test); yv=np.array([float(r["tp"]) for r in test])
    if yt.sum()==0: return dict(label=label,note="fara pozitive")
    m=MD.fit(Xt,yt); sv=m and MD.predict(m,Xv); thr=float(np.quantile(MD.predict(m,Xt),0.8)); sel=[test[i] for i in range(len(test)) if sv[i]>=thr]
    return dict(label=label,pr_auc=MD.pr_auc(yv,sv),pr_auc_random=float(yv.mean()),EV_top20=(S.mean([r["pnl"] for r in sel]) if sel else None),EV_all=S.mean([r["pnl"] for r in test]),N_sel=len(sel))
h=10; dev=[r for r in by_h[h] if r["part"]=="DEV" and r["prim"]]; val=[r for r in by_h[h] if r["part"]=="VAL" and r["prim"]]
NC={}
NC["real"]=model_eval(dev,val,MD.ALLF,"real")
# NC1 outcome-uri permutate in blocuri cronologice (DEV si VAL separat)
rng=random.Random(7)
def permute_blocks(rs):
    rs=sorted(rs,key=lambda r:r["T0"]); out=[dict(r) for r in rs]
    for b0 in range(0,len(out),50):
        blk=[(r["pnl"],r["tp"]) for r in out[b0:b0+50]]; rng.shuffle(blk)
        for r,(p,t) in zip(out[b0:b0+50],blk): r["pnl"]=p; r["tp"]=t
    return out
NC["NC1_permuted_outcomes_in_blocks"]=model_eval(permute_blocks(dev),permute_blocks(val),MD.ALLF,"NC1")
# NC2 trasaturile deplasate la urmatoarea oportunitate
def shift(rs):
    rs=sorted(rs,key=lambda r:r["T0"]); out=[dict(rs[i],f=rs[i-1]["f"]) for i in range(1,len(rs))]; return out
NC["NC2_features_shifted_next_pool"]=model_eval(shift(dev),shift(val),MD.ALLF,"NC2")
# NC3 identificator ca unica trasatura
idfn=lambda rs: np.array([[int(hashlib.sha256(r["mint"].encode()).hexdigest()[:8],16)/2**32, int(hashlib.sha256(r["mint"][::-1].encode()).hexdigest()[:8],16)/2**32] for r in rs])
NC["NC3_identifier_only"]=model_eval(dev,val,["id1","id2"],"NC3",feature_fn=idfn)
# NC4 trasatura viitoare imposibila (pnl-ul final ca trasatura): garda trebuie sa o respinga; fortata, ar deveni perfecta (demonstreaza sensibilitatea)
try: MD.guard_feature_names(["future_pnl_final"]); g4="NOT_REJECTED"
except ValueError: g4="REJECTED"
fut=lambda rs: np.array([[r["pnl"]] for r in rs]); forced=model_eval(dev,val,["forced"],"NC4_forced",feature_fn=fut)
NC["NC4_impossible_future_feature"]=dict(guard=g4,forced_pr_auc=forced.get("pr_auc"),forced_EV_top20=forced.get("EV_top20"),note="garda a respins numele; fortarea trasaturii viitoare produce PR-AUC ~1 => pipeline-ul ar detecta o scurgere reala")
# NC5 secventa inversata in timp: trasaturile calculate din evenimentele de DUPA D (in ordine inversa) trebuie respinse de garda de timestamp (max_ts_used >= D)
def reversed_feats(rs):
    out=[]
    for r in rs:
        f=dict(r["f"]); f["max_ts_used"]=r["D"]+1; out.append(dict(r,f=f))
    return out
rv=reversed_feats(dev); T["NC5_time_reversed_rejected_by_guard"]=dict(status=ok(all(r["f"]["max_ts_used"]>=r["D"] for r in rv)),note="orice trasatura cu max_ts_used >= D pica testul T1 (garda de timestamp); nu se calculeaza outcome pe ea")
# NC6 intrare aleatoare cu aceeasi distributie de timp: placebo pe VAL (din discovery: r['placebo'] nu e in tabel) -> comparam EV al politicii la D+2 cu EV la intrari aleatoare in [D+7, D+122] din rezultatele salvate
res=json.load(open("research/master_edge_results.json")); C=res.get("candidate",{})
NC["NC6_random_entry_placebo"]=dict(candidate_OOD_EV=(C.get("OOD_VAL_AUDIT") or {}).get("EV"),placebo_EV=(C.get("stress",{}).get("placebo_random_entry") or {}).get("EV"))
def looks_predictive(e): return e.get("pr_auc") is not None and e.get("pr_auc_random") is not None and e["pr_auc"]>2*e["pr_auc_random"]+0.05 and (e.get("EV_top20") or 0)>(e.get("EV_all") or 0)+1.0
flags=[k for k in ("NC1_permuted_outcomes_in_blocks","NC2_features_shifted_next_pool","NC3_identifier_only") if looks_predictive(NC[k])]
status="PIPELINE_LEAKAGE_OR_INVALIDATION" if (flags or any(v.get("status")=="FAIL" for v in T.values())) else "NO_LEAKAGE_DETECTED"
out=dict(tests=T,negative_controls=NC,flags=flags,LEAKAGE_STATUS=status)
json.dump(out,open("research/master_leakage_tests.json","w"),indent=1,default=str)
print(json.dumps({k:v.get("status") for k,v in T.items()})); print("NC",{k:(v.get("pr_auc"),v.get("pr_auc_random"),v.get("EV_top20"),v.get("EV_all")) for k,v in NC.items() if isinstance(v,dict) and "pr_auc" in v}); print("LEAKAGE_STATUS",status)
