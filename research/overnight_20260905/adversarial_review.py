"""Stage 5: revizuire adversariala pe regulile INGHETATE (fara modificarea lor): determinism/hash-uri, cei mai mari castigatori/pierzatori, ex-best, leave-one-day/mint-out,
amestecarea identitatilor portofelelor in pool-uri comparabile, placebo D+180 s, informatie incrementala peste controale, breadth artificial din portofele repetate, scanare lookahead in sursa, reconcilierea contoarelor."""
import gzip,json,hashlib,collections,statistics as S,math,time,sys,os,copy,random,re,subprocess
sys.path.insert(0,'research'); sys.path.insert(0,'research/overnight_20260905'); import fixed_family_eval as FE; import cohort_panel as CP
D=FE.D; OUT=FE.OUT; DAYS=FE.DAYS
def main():
    t0=time.time(); P=FE.load_panel(); feat={f["mint"]:f for f in P}; rows=[json.loads(l) for l in gzip.open(f"{D}/signals.jsonl.gz","rt")]; R={h:json.load(open(f"{OUT}/{n}_results.json")) for h,n in (("H1","h1_cohort_rotation"),("H2","h2_seller_overhang"),("H3","h3_selective_buyer"))}
    A_={}
    # 1. determinism: rerulare din proces curat a build_signals + evaluate si comparare hash
    thr,sig=FE.build_signals(P,None); r2=FE.evaluate(copy.deepcopy(rows),feat,sig,thr); hs=lambda o: hashlib.sha256(json.dumps(o,sort_keys=True,default=str).encode()).hexdigest()
    A_["determinism"]={h:dict(rerun_equal=(hs({k:v for k,v in R[h].items() if k!="label"})==hs({k:v for k,v in r2[h].items() if k!="label"}))) for h in ("H1","H2","H3")}
    A_["thresholds_match_frozen"]=(json.load(open(f"{OUT}/thresholds_frozen.json"))["thresholds"]==thr)
    for h in ("H1","H2","H3"):
        s=[r for r in rows if r["day"]!=DAYS["DEV"] and r[f"{h}_elig"] and r[h]]; d={}
        if s:
            srt=sorted(s,key=lambda r:-r["pnl"]); d["top5_winners"]=[(hashlib.sha256(("external-review-v1:"+r["mint"]).encode()).hexdigest()[:16],r["day"],round(r["pnl"],5)) for r in srt[:5]]; d["top5_losers"]=[(hashlib.sha256(("external-review-v1:"+r["mint"]).encode()).hexdigest()[:16],r["day"],round(r["pnl"],5)) for r in srt[-5:]]
            d["ex_best_1pct_EV"]=FE.stats(s)["EX_BEST_1PCT"]; d["ex_best_3_EV"]=FE.stats(s)["EX_BEST_3"]
            d["leave_one_day_out"]={dd:(FE.stats([r for r in s if r["day"]!=dd]) or {}).get("EV") for dd in sorted({r["day"] for r in s})}
            d["leave_one_mint_out_min_EV"]=min((sum(r["pnl"] for r in s if r["mint"]!=m)/max(1,len(s)-1)) for m in {r["mint"] for r in s})
            # informatie incrementala: corelatia de rang a scorului cu PnL-ul rezidual dupa controale (regresie liniara pe controale, fit pe DEV, aplicata pe VAL+CONF)
            import numpy as np
            keys=("liquidity_sol","ret_bp","n_post_swaps","buy_flow_sol_per_s"); elig=[r for r in rows if r[f"{h}_elig"] and r[f"{h}_v"] is not None]
            dev=[r for r in elig if r["day"]==DAYS["DEV"]]; test=[r for r in elig if r["day"]!=DAYS["DEV"]]
            if len(dev)>10 and len(test)>10:
                Xd=np.array([[feat[r["mint"]][k] or 0 for k in keys]+[1] for r in dev]); yd=np.array([r["pnl"] for r in dev]); beta,*_=np.linalg.lstsq(Xd,yd,rcond=None)
                Xt=np.array([[feat[r["mint"]][k] or 0 for k in keys]+[1] for r in test]); res=np.array([r["pnl"] for r in test])-Xt@beta; v=np.array([r[f"{h}_v"] for r in test])
                rk=lambda a: np.argsort(np.argsort(a)); d["rank_corr_feature_vs_residual_pnl_VAL_CONF"]=float(np.corrcoef(rk(v),rk(res))[0,1]); d["rank_corr_feature_vs_raw_pnl_VAL_CONF"]=float(np.corrcoef(rk(v),rk(np.array([r["pnl"] for r in test])))[0,1])
        A_[h]=d
    # portofele repetate: breadth artificial? cota cumparatorilor post-only care apar in > 5 pool-uri (in panou)
    cnt=collections.Counter()
    X=FE.load_pools(); H=CP.load_hist()
    for f in P:
        x=X[f["mint"]]; seen=set()
        for e in x["ev"]:
            if e[1]<f["D"] and e[5]==1 and e[15] not in seen: seen.add(e[15]); cnt[e[15]]+=1
    tot=sum(cnt.values()); A_["repeated_wallets"]=dict(distinct_post_buyers=len(cnt),buyer_appearances=tot,share_appearances_from_wallets_in_gt5_pools=(sum(c for c in cnt.values() if c>5)/tot if tot else None),wallets_in_gt5_pools=sum(1 for c in cnt.values() if c>5),max_pools_per_wallet=max(cnt.values()) if cnt else 0)
    # amestecarea identitatilor portofelelor in pool-uri comparabile (aceeasi zi, lichiditate similara): permutam listele buyers_prior intre pool-uri -> recalculam H1/H3 -> EV al semnalelor (200 permutari)
    rng=random.Random(11); pnl={r["mint"]:r for r in rows}; perm_ev={"H1":[],"H3":[]}
    byday=collections.defaultdict(list); [byday[f["day"]].append(f) for f in P]
    for _ in range(200):
        P2=[]
        for d,fs in byday.items():
            fs=sorted(fs,key=lambda f:(f["liquidity_sol"] or 0)); 
            for i in range(0,len(fs),10):
                blk=[copy.copy(f) for f in fs[i:i+10]]; bp=[f["buyers_prior"] for f in blk]; rng.shuffle(bp)
                for f,b in zip(blk,bp): f["buyers_prior"]=b; f["n_post_only_buyers"]=len(b); f["median_prior_mints"]=(S.median([q[0] for q in b]) if b else None)
                P2+=blk
        thr2,sig2=FE.build_signals(P2,None)
        for h in ("H1","H3"):
            s=[pnl[m] for m,v in sig2.items() if v[h] and pnl.get(m) and pnl[m]["day"]!=DAYS["DEV"]]; perm_ev[h].append(sum(r["pnl"] for r in s)/len(s) if s else None)
    A_["wallet_shuffle_within_comparable_pools"]={h:dict(perm_mean_EV=(S.mean([v for v in perm_ev[h] if v is not None]) if any(v is not None for v in perm_ev[h]) else None),observed_EV=(R[h]["signals"] or {}).get("EV"),p_perm_ge_observed=(sum(1 for v in perm_ev[h] if v is not None and (R[h]["signals"] or {}).get("EV") is not None and v>=R[h]["signals"]["EV"])/max(1,sum(1 for v in perm_ev[h] if v is not None)))) for h in ("H1","H3")}
    # placebo: decizie la T0+180 s (trasaturi si executie deplasate), aceleasi praguri DEV
    P180=[CP.features(X[f["mint"]],H,f["T0_ts"]+180) for f in P]; feat180={f["mint"]:f for f in P180}; rows180=[]
    for f in P180:
        o=FE.execute(X[f["mint"]],f["D"])
        if o["status"]=="OK": rows180.append(dict(mint=f["mint"],day=f["day"],pnl=o["pnl_sol"],pnl_120=None,pnl_c125=None,pnl_l2=None))
    thr180,sig180=FE.build_signals(P180,None)
    A_["placebo_decision_plus180"]={h:dict(N=len([r for r in rows180 if r["day"]!=DAYS["DEV"] and sig180[r["mint"]][h]]),EV=(FE.stats([r for r in rows180 if r["day"]!=DAYS["DEV"] and sig180[r["mint"]][h]]) or {}).get("EV"),unconditional_EV=(FE.stats([r for r in rows180 if r["day"]!=DAYS["DEV"]]) or {}).get("EV")) for h in ("H1","H2","H3")}
    # scanare lookahead in sursa: trasaturile nu folosesc 'exit', 'pnl', 'landing'; executia nu intra in build_signals
    src=open("research/overnight_20260905/cohort_panel.py").read().split("def features(")[1].split("\ndef ")[0]; A_["source_lookahead_scan"]=dict(features_reference_outcomes=any(k in src for k in ("pnl","exit","sell_out","execute(")),features_use_strict_lt_D=("e[1]<Dts" in src),build_signals_uses_outcomes=("pnl" in open("research/overnight_20260905/fixed_family_eval.py").read().split("def build_signals(")[1].split("\ndef ")[0]))
    # reconcilierea contoarelor
    man=json.load(open(f"{OUT}/cohort_panel_manifest.json")); om=json.load(open(f"{OUT}/outcomes_manifest.json")); A_["count_reconciliation"]=dict(m_cache_pools=man["m_cache_manifest"]["N"],panel_rows=man["rows"],outcome_rows=om["rows"],executable_rows=len(rows),status_counts=om["status_counts"],signals_val_conf={h:len([r for r in rows if r["day"]!=DAYS["DEV"] and r[f"{h}_elig"] and r[h]]) for h in ("H1","H2","H3")},reported={h:(R[h]["signals"] or {}).get("N") for h in ("H1","H2","H3")})
    A_["discrepancies"]=[k for k,v in A_["count_reconciliation"]["reported"].items() if v!=A_["count_reconciliation"]["signals_val_conf"][k]]+([] if A_["thresholds_match_frozen"] else ["thresholds_mismatch"])+[h for h in ("H1","H2","H3") if not A_["determinism"][h]["rerun_equal"]]
    A_["runtime_s"]=round(time.time()-t0,1); json.dump(A_,open(f"{OUT}/adversarial_review.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in A_.items() if k in ("determinism","thresholds_match_frozen","repeated_wallets","wallet_shuffle_within_comparable_pools","placebo_decision_plus180","source_lookahead_scan","discrepancies")},default=str)[:2500]); print("ADVERSARIAL_DONE")
if __name__=="__main__": main()
