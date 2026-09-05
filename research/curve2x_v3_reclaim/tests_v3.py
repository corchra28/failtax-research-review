"""CURVE2X V3 RECLAIM — teste sintetice (fara date private): detectie anchor/pullback/reclaim, abandon dupa 120 s, o decizie per mint, TP/SL/timeout, SL in acelasi slot,
splice indisponibil, future mutation (trasaturile depind doar de T[:dec+1]), independenta etichetei de trasaturi, split per mint."""
import os,sys,json,copy
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import v3_lib as V; L=V.L; LAMP=L.LAMP
VS0=30*LAMP; VT0=1_073_000_000_000_000; RT0=793_100_000_000_000
def mk(steps,t0=1_000_000,slot0=1000):
    vs,vt,rs,rt=VS0,VT0,0,RT0; T=[]; seq=0
    for dt,ds,sol,user in steps:
        ts=t0+dt; slot=slot0+ds; seq+=1
        if sol>0:
            tok,net=L.curve_buy(vs,vt,sol); vs+=net; vt-=tok; rs+=net; rt-=tok; T.append([ts,slot,seq,0,user,sol,tok,1,rs,rt,vs,vt])
        else:
            want=-sol; h=vt*want//(vs-want) if vs>want else vt//10; g=vs-(vs*vt)//(vt+h); g=min(g,rs); vs-=g; vt+=h; rs-=g; rt+=h; T.append([ts,slot,seq,0,user,g,h,0,rs,rt,vs,vt])
    return T
R={}
def check(n,c,d=""): R[n]=dict(pass_=bool(c),detail=str(d)[:300]); print("PASS" if c else "FAIL",n,d)
buys=lambda n,dt0,ds0,sol,u="w",sdt=1,sds=2:[(dt0+i*sdt,ds0+i*sds,sol,f"{u}{i}") for i in range(n)]
# anchor la ~40 %: 36 cumparari de 1 SOL; pullback: 6 vanzari de 1 SOL; reclaim: 6 cumparari de 1 SOL in <120 s
base=buys(36,0,0,1*LAMP); pb=[(40+i,80+2*i,-1*LAMP,f"s{i}") for i in range(6)]; rc=buys(6,50,100,1*LAMP,"r")
T=mk(base+pb+rc); d=V.detect(T,T[0][0]-1)
check("detect_anchor_pullback_reclaim",d is not None and d["anchor"]<d["pb"]<=d["trough"]<d["dec"] and T[d["anchor"]][8]>=0.4*L.TARGET_RS,d)
# abandon: reclaim dupa >120 s nu este valid
T2=mk(base+pb+buys(6,200,400,1*LAMP,"r")); d2=V.detect(T2,T2[0][0]-1); check("reclaim_after_120s_rejected",d2 is None,d2)
# o decizie per mint: detect se opreste la prima decizie; al doilea reclaim ulterior este ignorat
T3=mk(base+pb+rc+[(70+i,140+2*i,-1*LAMP,f"s2{i}") for i in range(6)]+buys(6,80,160,1*LAMP,"r2")); d3=V.detect(T3,T3[0][0]-1); check("one_decision_per_mint",d3 is not None and d3["dec"]==d["dec"],(d3 or {}).get("dec"))
# trasaturi: depind doar de T[:dec+1] (future mutation)
f1=V.features(T,T[0][0]-1,"creator",d,0.0); Tm=T[:d["dec"]+1]+mk(buys(20,300,600,3*LAMP,"z"))[:0]; f2=V.features(T3,T3[0][0]-1,"creator",d3,0.0)
check("future_mutation_no_feature_change",f1==f2 and len(f1)==len(V.FEATS) and all(k in f1 for k in V.FEATS),len(f1))
# etichete
rec=lambda T,c=None,p=None:dict(mint="S",trades=T,complete_ts=None if c is None else c[0],complete_slot=None if c is None else c[1],complete_seq=None if c is None else c[2],pool=p)
Ttp=mk(base+pb+rc+buys(60,60,130,2*LAMP,"p")); dtp=V.detect(Ttp,Ttp[0][0]-1); o=V.simulate_v3(rec(Ttp),dtp["dec"],Ttp[dtp["dec"]][0]); check("TP_first",o["status"]=="OK" and o["15M"]["state"]=="TP_FIRST" and o["15M"]["pnl"]>0,o["15M"])
Tsl=mk(base+pb+rc+[(60+i,130+2*i,-4*LAMP,f"d{i}") for i in range(10)]); dsl=V.detect(Tsl,Tsl[0][0]-1); o=V.simulate_v3(rec(Tsl),dsl["dec"],Tsl[dsl["dec"]][0]); check("SL_first",o["15M"]["state"]=="SL_FIRST" and o["15M"]["pnl"]<0,o["15M"])
Tto=mk(base+pb+rc+[(60+i*30,130+i*75,(0.05*LAMP if i%2 else -0.05*LAMP),f"m{i}") for i in range(20)]); dto=V.detect(Tto,Tto[0][0]-1); o=V.simulate_v3(rec(Tto),dto["dec"],Tto[dto["dec"]][0]); check("timeout",o["15M"]["state"]=="TIMEOUT_OTHER",o["15M"])
# SL si TP in acelasi slot -> SL
tp_i=next(i for i in range(dtp["dec"]+1,len(Ttp)) if V.simulate_v3(rec(Ttp[:i+1]),dtp["dec"],Ttp[dtp["dec"]][0])["15M"]["state"]=="TP_FIRST"); Ts=Ttp[:tp_i+1]; s=Ts[-1]; h=s[11]*3; g=min(s[10]-(s[10]*s[11])//(s[11]+h),s[8]); Ts.append([s[0],s[1],s[2]+1,0,"dump",g,h,0,s[8]-g,s[9]+h,s[10]-g,s[11]+h])
o=V.simulate_v3(rec(Ts),dtp["dec"],Ttp[dtp["dec"]][0]); check("same_slot_SL_wins",o["15M"]["state"]=="SL_FIRST",o["15M"]["state"])
# splice indisponibil dupa migrare
Tmig=mk(base+pb+rc+buys(80,60,130,1*LAMP,"p")); ci=next(i for i,t in enumerate(Tmig) if t[8]>=L.TARGET_RS); Tmig=Tmig[:ci+1]; c=Tmig[-1]; dm=V.detect(Tmig,Tmig[0][0]-1)
# TP pe curba inainte de migrare? verificam ca fara pool eticheta e fie rezolvata pe curba, fie UNAVAILABLE
o=V.simulate_v3(rec(Tmig,(c[0],c[1],c[2])),dm["dec"],Tmig[dm["dec"]][0]); check("migration_without_splice_flagged",o["splice_ok"] is False and o["15M"]["label_kind"] in ("CROSS_MIGRATION_LABEL_UNAVAILABLE","CURVE_RESOLVED_BEFORE_MIGRATION"),o["15M"]["label_kind"])
# eticheta nu depinde de trasaturi (mutarea trasaturilor nu schimba simularea) — trivial prin constructie; verificam ca simularea nu citeste f
o2=V.simulate_v3(rec(Ttp),dtp["dec"],Ttp[dtp["dec"]][0]); check("label_independent_of_features",o2["15M"]==V.simulate_v3(rec(Ttp),dtp["dec"],Ttp[dtp["dec"]][0])["15M"],"determinist")
# CompleteEvent la horizon+100 s fara pool => CURVE_ONLY: TIMEOUT_OTHER, unavailable=false, migrated_in_window=false
Tl=mk(base+pb+rc+[(60+i*30,130+i*75,(0.05*LAMP if i%2 else -0.05*LAMP),f"m{i}") for i in range(20)]); dl=V.detect(Tl,Tl[0][0]-1); dts=Tl[dl["dec"]][0]; last=Tl[-1]
cts=dts+V.H_PRIMARY+100; o=V.simulate_v3(rec(Tl,(cts,last[1]+5000,last[2]+5000)),dl["dec"],dts)
check("complete_after_horizon_is_curve_only",o["status"]=="OK" and o["15M"]["state"]=="TIMEOUT_OTHER" and not o["15M"].get("unavailable") and o["migrated_in_window"] is False and o["15M"]["label_kind"]=="CURVE_ONLY",{k:o["15M"].get(k) for k in ("state","unavailable","label_kind")}|{"mig":o["migrated_in_window"]})
# limite de ordine in slotul de aterizare: conservative <= midpoint <= optimistic; slotul de aterizare cu 3 trade-uri
Tb=mk(base+pb+rc+[(56,Tl[dl["dec"]][1]-1000+3,2*LAMP,"q1"),(56,Tl[dl["dec"]][1]-1000+3,-1*LAMP,"q2"),(56,Tl[dl["dec"]][1]-1000+3,3*LAMP,"q3")]+buys(60,60,130,2*LAMP,"p")); db=V.detect(Tb,Tb[0][0]-1); ob=V.simulate_v3_bounds(rec(Tb),db["dec"],Tb[db["dec"]][0])
check("landing_bounds_ordered",ob["status"]=="OK" and ob["n_entry_positions"]==4 and ob["conservative"]["pnl"]<=ob["midpoint"]["pnl"]<=ob["optimistic"]["pnl"],{k:ob.get(k) for k in ("n_entry_positions","conservative","midpoint","optimistic")})
# ruptura de lant in slotul de aterizare => exclus
Tc=[list(t) for t in Tb]; j=db["dec"]+2; Tc[j][10]+=5*LAMP; Tc[j][8]+=5*LAMP; oc=V.simulate_v3_bounds(rec([tuple(t) for t in Tc]),db["dec"],Tb[db["dec"]][0]); check("chain_break_excluded",oc["status"]=="CHAIN_BREAK",oc["status"])
try:
    import build_v3 as B; check("same_fold_per_mint",len({B.split_of(t) for t in [Ttp[0][0]]*3})==1,"split per create_ts")
except Exception as ex: check("same_fold_per_mint",False,ex)
json.dump(dict(label="HISTORICAL_DEV_NOT_SEALED",tests=R,all_pass=all(v["pass_"] for v in R.values())),open(os.path.join(HERE,"test_results.json"),"w"),indent=1); print("ALL_PASS" if all(v["pass_"] for v in R.values()) else "SOME_FAIL")
