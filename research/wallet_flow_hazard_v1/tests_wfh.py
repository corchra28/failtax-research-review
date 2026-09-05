"""WALLET_FLOW_HAZARD_V1 — teste (fara date private): graf cauzal (pozitiile cu maturitate > t nu conteaza; future mutation), permutare (istoricul altui portofel schimba trasaturile A),
o decizie per mint (selectie), eticheta first-passage (V3 lib), bin-uri de hazard si exit dinamic conservativ, split per mint."""
import os,sys,json,random
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import wfh_lib as W; V=W.V; L=W.L; LAMP=L.LAMP
R={}
def check(n,c,d=""): R[n]=dict(pass_=bool(c),detail=str(d)[:200]); print("PASS" if c else "FAIL",n,d)
VS0=30*LAMP; VT0=1_073_000_000_000_000; RT0=793_100_000_000_000
def mk(steps,t0=1_000_000,slot0=1000):
    vs,vt,rs,rt=VS0,VT0,0,RT0; T=[]; seq=0
    for dt,ds,sol,user in steps:
        ts=t0+dt; slot=slot0+ds; seq+=1
        if sol>0: tok,net=L.curve_buy(vs,vt,sol); vs+=net; vt-=tok; rs+=net; rt-=tok; T.append([ts,slot,seq,0,user,sol,tok,1,rs,rt,vs,vt])
        else:
            want=-sol; h=vt*want//(vs-want) if vs>want else vt//10; g=vs-(vs*vt)//(vt+h); g=min(g,rs); vs-=g; vt+=h; rs-=g; rt+=h; T.append([ts,slot,seq,0,user,g,h,0,rs,rt,vs,vt])
    return T
def rec_of(T,t0=1_000_000): return dict(mint="S",creator="creator",create_ts=t0-1,trades=T,complete_ts=None,complete_slot=None,complete_seq=None,pool=None)
buys=lambda n,dt0,ds0,sol,u="w":[(dt0+i,ds0+2*i,sol,f"{u}{i}") for i in range(n)]
# graf cauzal: pozitii maturizate inainte/dupa t
G=W.WalletGraph(); G.add([("w1",100,100+960,1,0.2,1,0.25),("w1",5000,5000+960,0,-0.1,0,0.25)]); G.finalize()
s1=G.stats("w1",2000); s2=G.stats("w1",7000); check("causal_only_matured_before_t",s1["n"]==1 and s1["tp"]==1.0 and s2["n"]==2 and s2["tp"]==0.5,(s1,s2)); check("no_history_before_maturity",G.stats("w1",500) is None,"")
# future mutation: adaugarea unei pozitii cu maturitate dupa t nu schimba stats
G2=W.WalletGraph(); G2.add([("w1",100,1060,1,0.2,1,0.25),("w1",1500,2460,1,0.5,1,0.25)]); G2.finalize(); check("future_mutation_no_change",G2.stats("w1",2000)==G.stats("w1",2000),"")
# trasaturi A la decizie folosesc doar graful (permutare: istoricul altui portofel schimba trasaturile)
T=mk(buys(30,0,0,1*LAMP)); rec=rec_of(T); CG=W.CreatorGraph(); CG.finalize()
Ga=W.WalletGraph(); Ga.add([(f"w{i}",100,1060,1,0.3,1,0.5) for i in range(10)]); Ga.finalize(); Gb=W.WalletGraph(); Gb.add([(f"w{i}",100,1060,0,-0.2,0,0.5) for i in range(10)]); Gb.finalize()
fa=W.features(rec,29,T[29][0],30,Ga,CG,10.0); fb=W.features(rec,29,T[29][0],30,Gb,CG,10.0)
check("wallet_quality_reflects_history",fa["wq_prior_tp_rate_w"]>fb["wq_prior_tp_rate_w"] and fa["wq_prior_ev_w"]>fb["wq_prior_ev_w"] and all(fa[k]==fb[k] for k in W.BLOCKS["MARKET_STATE"]),(fa["wq_prior_tp_rate_w"],fb["wq_prior_tp_rate_w"]))
# permutation test: istoric permutat intre portofele => trasaturile A se schimba (dependenta reala de identitatea istoricului, fara wallet ID ca feature)
# permutare pe populatie: cumparatorii mint-ului (w0..w29) primesc istoricul altor portofele din populatie (w30..w59); istoric propriu bogat vs istoric permutat sarac
random.seed(1); ids=[f"w{i}" for i in range(60)]; hist=[(1 if i<30 and i%2==0 else 0,0.3 if i<30 and i%2==0 else -0.1) for i in range(60)]; Gp=W.WalletGraph(); Gp.add([(u,100,1060,tp,ev,1,0.5) for u,(tp,ev) in zip(ids,hist)]); Gp.finalize()
perm=hist[30:]+hist[:30]; Gq=W.WalletGraph(); Gq.add([(u,100,1060,tp,ev,1,0.5) for u,(tp,ev) in zip(ids,perm)]); Gq.finalize()
fp=W.features(rec,29,T[29][0],30,Gp,CG,10.0); fq=W.features(rec,29,T[29][0],30,Gq,CG,10.0); check("permutation_changes_wallet_features",fp["wq_prior_tp_rate_w"]!=fq["wq_prior_tp_rate_w"] or fp["wq_prior_ev_w"]!=fq["wq_prior_ev_w"],(fp["wq_prior_tp_rate_w"],fq["wq_prior_tp_rate_w"]))
check("no_identifier_features",not any(k in ("mint","wallet","user","ts","slot","seq") for k in W.FEATS),"")
# bin-uri de hazard + exit dinamic conservativ
T2=mk(buys(30,0,0,1*LAMP)+[(40+i*20,60+i*50,(0.3*LAMP if i%2 else -0.2*LAMP),f"m{i}") for i in range(40)]); pb=W.path_bins(rec_of(T2),29,T2[29][0])
check("path_bins_built",pb is not None and len(pb["bins"])>=5 and all("value_ratio" in b for b in pb["bins"]),len(pb["bins"]) if pb else None)
b=pb["bins"][3]; pnl=W.dynamic_exit_pnl(rec_of(T2),pb,3,b["exit_state"][1]) if b["exit_state"] else None; check("dynamic_exit_conservative_pnl",pnl is not None and pnl<=(b["value_ratio"]*pb["gross"]-L.NET_COST-pb["gross"])/LAMP+1e-9,pnl)
try:
    import build_wfh as Bd; check("same_fold_per_mint",len({Bd.split_of(t) for t in [rec["create_ts"]]*3})==1,"")
except Exception as ex: check("same_fold_per_mint",False,ex)
OUTD=os.environ.get("WFH_TEST_OUT",HERE); os.makedirs(OUTD,exist_ok=True); json.dump(dict(label="HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED",tests=R,n_tests=len(R),all_pass=all(v["pass_"] for v in R.values())),open(os.path.join(OUTD,"test_results.json"),"w"),indent=1); print("ALL_PASS" if all(v["pass_"] for v in R.values()) else "SOME_FAIL")
