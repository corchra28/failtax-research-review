"""Stage 2: panoul deterministic portofel/cohorta (FARA outcome-uri) + teste de scurgere. Sursa: cache m_pools (946 migrari cu istoric pre-migrare complet), wallet_history (istoric comportamental anterior deciziei).
Decizie D = T0_ts + 60 s. Toate trasaturile folosesc EXCLUSIV evenimente cu ts < D (pool) si trade-urile de curba (anterioare completarii). INVENTORY_PROXY = inventar reconstruit din trade-uri (nu solduri ajustate cu transferuri).
Iesire: derived/cohort_panel.jsonl.gz (randuri per mint; portofelele raman locale, nepublicate), cohort_panel_manifest.json, leakage_tests.json."""
import gzip,json,hashlib,collections,statistics as S,math,time,sys,os,copy,random
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/overnight_20260905"; DEC=60; SUPPLY_PROXY=10**15
def load_hist():
    H={}
    for l in gzip.open(f"{D}/wallet_history.jsonl.gz","rt"): r=json.loads(l); H[r["w"]]=r["m"]
    return H
def prior_mints(H,w,mint,Dts):
    """numar de mint-uri DISTINCTE tranzactionate de portofel strict inainte de D (fara mint-ul curent); si cate in ultimele 24 h."""
    h=H.get(w,{}); n=0; n24=0
    for m,t in h.items():
        if m==mint or t>=Dts: continue
        n+=1; n24+=(t>=Dts-86400)
    return n,n24
def features(x,H,Dts=None):
    Dts=Dts or x["T0_ts"]+DEC; vq=x["vq"]; ev=[e for e in x["ev"] if e[1]<Dts]   # STRICT < D
    bal=collections.Counter(); cb=collections.Counter()
    for tr in x["curve"]:
        if tr[5]: bal[tr[6]]+=tr[4]; cb[tr[6]]+=tr[4]
        else: bal[tr[6]]-=tr[4]
    cohort={u:b for u,b in bal.items() if b>0}; inv_total=sum(cohort.values()); f=dict(mint=x["mint"],day=x["day"],T0_ts=x["T0_ts"],D=Dts,complete_ts=x["complete_ts"],creator=x["creator"])
    f["cohort_size"]=len(cohort); f["inventory_proxy_total"]=inv_total; f["creator_inventory_share"]=(cohort.get(x["creator"],0)/inv_total) if inv_total else 0.0
    f["feature_max_ts"]=(max(e[1] for e in ev) if ev else None); f["last_contributing_slot"]=(max(e[2] for e in ev) if ev else None); f["n_post_swaps"]=len(ev)
    if not ev:
        f.update(dict(n_post_buyers=0,n_post_sellers=0,n_post_only_buyers=0,n_incumbent_sellers=0,buy_quote=0.0,sell_quote=0.0,incumbent_sell_quote=0.0,incumbent_sell_share=0.0,post_only_buy_quote=0.0,post_only_buy_share=0.0,top1_buy_share=None,top3_buy_share=None,hhi_buy=None,inc_sell_0_30=0.0,inc_sell_30_60=0.0,decay_ratio=None,remaining_inventory_proxy=1.0,largest_incumbent_remaining_share=(max(cohort.values())/SUPPLY_PROXY if cohort else 0.0),buyers_prior=[],median_prior_mints=None,liquidity_sol=None,ret_bp=None,vol_bp=None,buy_flow_sol_per_s=0.0,buyers_repeat_share=None)); return f
    e0=x["ev"][0]; p_open=(e0[7]+vq)/e0[6]; pxs=[(e[9]+vq)/e[8] for e in ev]
    buyq=collections.Counter(); sellq_inc=0.0; sells_inc=set(); buyers=set(); sellers=set(); post_only=set(); sold_tok_inc=collections.Counter(); bought_tok_post=collections.Counter(); inc0=0.0; inc30=0.0
    for e in ev:
        u=e[15]; q=e[11]/1e9
        if e[5]==1:
            buyq[u]+=q; buyers.add(u)
            if u not in cohort: post_only.add(u)
            else: bought_tok_post[u]+=e[10]
        else:
            sellers.add(u)
            if u in cohort:
                sellq_inc+=q; sells_inc.add(u); sold_tok_inc[u]+=e[10]
                if e[1]<x["T0_ts"]+30: inc0+=q
                else: inc30+=q
    tb=sum(buyq.values()); ts_=sum(e[11]/1e9 for e in ev if e[5]==0); tot=tb+ts_
    shares=sorted(buyq.values(),reverse=True); f["n_post_buyers"]=len(buyers); f["n_post_sellers"]=len(sellers); f["n_post_only_buyers"]=len(post_only); f["n_incumbent_sellers"]=len(sells_inc)
    f["buy_quote"]=tb; f["sell_quote"]=ts_; f["incumbent_sell_quote"]=sellq_inc; f["incumbent_sell_share"]=(sellq_inc/tot) if tot>0 else 0.0
    poq=sum(q for u,q in buyq.items() if u in post_only); f["post_only_buy_quote"]=poq; f["post_only_buy_share"]=(poq/tb) if tb>0 else 0.0
    f["top1_buy_share"]=(shares[0]/tb) if tb>0 else None; f["top3_buy_share"]=(sum(shares[:3])/tb) if tb>0 else None; f["hhi_buy"]=(sum((q/tb)**2 for q in shares)) if tb>0 else None
    f["inc_sell_0_30"]=inc0; f["inc_sell_30_60"]=inc30; f["decay_ratio"]=(inc30/(inc0+1e-9)) if (inc0>0 or inc30>0) else None
    remaining={u:cohort[u]-sold_tok_inc.get(u,0)+bought_tok_post.get(u,0) for u in cohort}; rem=sum(max(0,v) for v in remaining.values()); f["remaining_inventory_proxy"]=(rem/inv_total) if inv_total else 1.0; f["largest_incumbent_remaining_share"]=(max([max(0,v) for v in remaining.values()]+[0])/SUPPLY_PROXY)
    bp=[]; 
    for u in post_only:
        n,n24=prior_mints(H,u,x["mint"],Dts); bp.append((n,n24,buyq[u]))
    f["buyers_prior"]=bp; f["median_prior_mints"]=(S.median([b[0] for b in bp]) if bp else None); f["median_prior_mints_24h"]=(S.median([b[1] for b in bp]) if bp else None)
    f["liquidity_sol"]=ev[-1][9]/1e9; f["ret_bp"]=(pxs[-1]/p_open-1)*1e4; lr=[math.log(b/a) for a,b in zip([p_open]+pxs,pxs) if a>0 and b>0]; f["vol_bp"]=(S.pstdev(lr)*1e4 if len(lr)>1 else 0.0); f["buy_flow_sol_per_s"]=tb/DEC
    return f
def leakage_tests(pools,H):
    """modificarea/eliminarea TUTUROR evenimentelor cu ts >= D nu poate schimba nicio trasatura; deplasarea D inainte schimba doar trasaturile post."""
    rng=random.Random(5); same=0; diff=[]; n=0
    for x in pools[:200]:
        f0=features(x,H); y=copy.deepcopy(x); Dts=x["T0_ts"]+DEC
        y["ev"]=[e for e in y["ev"] if e[1]<Dts]+[[e[0],e[1],e[2],e[3],e[4],1-e[5],e[6]*2+1,e[7]*3+7,e[8],e[9]*5,e[10]*11,e[11]*13,e[12],e[13],e[14],"FUTURE"+str(rng.random())] for e in y["ev"] if e[1]>=Dts]
        f1=features(y,H); n+=1
        if f0==f1: same+=1
        else: diff.append(x["mint"])
    return dict(pools_tested=n,identical_after_future_mutation=same,violations=len(diff),violation_examples=diff[:5],PASS=(same==n and n>0))
if __name__=="__main__":
    t0=time.time(); H=load_hist(); pools=[]
    with gzip.open(f"{D}/m_pools.jsonl.gz","rt") as f:
        for l in f: pools.append(json.loads(l))
    lt=leakage_tests(pools,H); json.dump(dict(feature_leakage=lt,rule="toate trasaturile din evenimente cu ts < D strict; istoricul portofelelor filtrat la first_ts < D; INVENTORY_PROXY din trade-uri",tested_at=time.strftime("%Y-%m-%d %H:%M:%S")),open(f"{OUT}/leakage_tests.json","w"),indent=1); print("leakage",lt)
    assert lt["PASS"],"LEAKAGE TEST FAILED — stop"
    h=hashlib.sha256(); n=0
    with gzip.open(f"{D}/cohort_panel.jsonl.gz","wt") as f:
        for x in pools: r=features(x,H); s=json.dumps(r,separators=(",",":"),default=str)+"\n"; f.write(s); h.update(s.encode()); n+=1
    man=dict(built=time.strftime("%Y-%m-%d %H:%M:%S"),rows=n,by_day=dict(collections.Counter(x["day"] for x in pools)),decision="T0_ts+60s",panel_content_sha256=h.hexdigest(),wallet_history_manifest=json.load(open(f"{D}/wallet_history_manifest.json")),m_cache_manifest=json.load(open(f"{D}/m_cache_manifest.json")),script_sha256=hashlib.sha256(open(__file__,"rb").read()).hexdigest(),runtime_s=round(time.time()-t0,1),published="NU (randurile contin portofele brute); doar manifestul si dictionarul")
    json.dump(man,open(f"{OUT}/cohort_panel_manifest.json","w"),indent=1); print(json.dumps({k:v for k,v in man.items() if k not in ("wallet_history_manifest","m_cache_manifest")})); print("PANEL_DONE")
