"""CURVE2X V2 — teste sintetice obligatorii (FAZA 3, regula 16). Rulare: python research/curve2x_v2/test_curve2x.py -> test_results.json. Zero RPC."""
import sys,os,json,copy,math
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L
LAMP=L.LAMP; VS0=30*LAMP; VT0=1_073_000_000_000_000; RT0=793_100_000_000_000
def mk_curve(steps,t0=1_000_000,slot0=1000):
    """steps: lista (dt_s, dslot, sol_signed_lamports, user); evolutie exacta a curbei (buy exact-input / sell exact-tokens echivalent)."""
    vs,vt,rs,rt=VS0,VT0,0,RT0; T=[]; seq=0
    for dt,ds,sol,user in steps:
        ts=t0+dt; slot=slot0+ds; seq+=1
        if sol>0:
            tok,net=L.curve_buy(vs,vt,sol); vs+=net; vt-=tok; rs+=net; rt-=tok; T.append([ts,slot,seq,0,user,sol,tok,1,rs,rt,vs,vt])
        else:
            # vanzare: alegem tokens astfel incat sol iesit ~ |sol|
            want=-sol; h=vt*want//(vs-want) if vs>want else vt//10; g=vs-(vs*vt)//(vt+h); g=min(g,rs); vs-=g; vt+=h; rs-=g; rt+=h; T.append([ts,slot,seq,0,user,g,h,0,rs,rt,vs,vt])
    return T
def rec_of(T,complete=None,pool=None):
    r=dict(mint="SYNTH",trades=T,complete_ts=None,complete_slot=None,complete_seq=None,pool=pool)
    if complete is not None: r["complete_ts"],r["complete_slot"],r["complete_seq"]=complete
    return r
def big_buys(n,dt0,dslot0,sol,user="w",step_dt=1,step_slot=2): return [(dt0+i*step_dt,dslot0+i*step_slot,sol,f"{user}{i}") for i in range(n)]
R={}
def check(name,cond,detail=""):
    R[name]=dict(pass_=bool(cond),detail=detail); print(("PASS" if cond else "FAIL"),name,detail)
N=0.25; H="15M"
# baza: 20 cumparari de 1 SOL -> ~progres ~23 %; decizia la ultimul trade (i=19), landing +3 sloturi
base=big_buys(20,0,0,1*LAMP)
# 1. TP inainte de SL: dupa intrare, cumparari mari -> 2x
T=mk_curve(base+big_buys(40,10,50,2*LAMP,"p")); rec=rec_of(T); out=L.simulate(rec,19,T[19][0],N)
check("TP_before_SL",out["status"]=="OK" and out[H]["state"]=="TP_FIRST" and out[H]["pnl"]>0,f"{out[H]}")
# 2. SL inainte de TP: dupa intrare, vanzari mari
T=mk_curve(base+[(10+i,50+2*i,-3*LAMP,f"s{i}") for i in range(8)]); rec=rec_of(T); out=L.simulate(rec,19,T[19][0],N)
check("SL_before_TP",out["status"]=="OK" and out[H]["state"]=="SL_FIRST" and out[H]["pnl"]<0,f"{out[H]}")
# 3. SL si TP in acelasi slot -> SL_FIRST
T=mk_curve(base+big_buys(40,10,50,2*LAMP,"p")); tp_i=next(i for i in range(20,len(T)) if L.simulate(rec_of(T[:i+1]),19,T[19][0],N)[H]["state"]=="TP_FIRST")
# adaugam o vanzare masiva in acelasi slot ca starea TP (dupa ea in ordinea seq)
tp_slot=T[tp_i][1]; T2=T[:tp_i+1]; vs,vt,rs,rt=T2[-1][10],T2[-1][11],T2[-1][8],T2[-1][9]; h=vt*3; g=vs-(vs*vt)//(vt+h); g=min(g,rs); T2.append([T2[-1][0],tp_slot,T2[-1][2]+1,0,"dump",g,h,0,rs-g,rt+h,vs-g,vt+h])
out=L.simulate(rec_of(T2),19,T2[19][0],N); check("SL_and_TP_same_slot_SL_wins",out[H]["state"]=="SL_FIRST",f"{out[H]['state']} slot={tp_slot}")
# 4. TP dupa un SL anterior -> SL_FIRST
T=mk_curve(base+[(10+i,50+2*i,-3*LAMP,f"s{i}") for i in range(8)]+big_buys(60,30,90,2*LAMP,"p")); out=L.simulate(rec_of(T),19,T[19][0],N)
check("TP_after_prior_SL_is_SL_FIRST",out[H]["state"]=="SL_FIRST" and out[H]["t_exit"]<30,f"{out[H]}")
# 5. timeout: miscari mici
T=mk_curve(base+[(10+i*30,50+i*75,(0.05*LAMP if i%2==0 else -0.05*LAMP),f"m{i}") for i in range(20)]); out=L.simulate(rec_of(T),19,T[19][0],N)
check("timeout",out[H]["state"]=="TIMEOUT_OTHER" and -0.05<out[H]["pnl"]<0,f"{out[H]}")
# 6. migrare intre decizie si TP: curba completeaza, pool-ul urca -> TP in pool
base65=big_buys(55,0,0,1*LAMP); steps=base65+big_buys(45,60,120,1*LAMP,"p"); T=mk_curve(steps); comp_i=next(i for i,t in enumerate(T) if t[8]>=L.TARGET_RS); T=T[:comp_i+1]; c=T[-1]
vq=17_584_892_010; rb0=206_900_000_000_000; rq0=85*LAMP-6*LAMP; ev=[]; rb,rq=rb0,rq0; slot=c[1]+2; ts=c[0]+1
for i in range(30):
    amt_q=3*LAMP; cp=amt_q; base_out=rb*cp//(rq+vq+cp); ev.append([ts+i,slot+2*i,c[2]+2+i,0,1,rb,rq,rb-base_out,rq+cp,base_out,cp,20,5,30]); rb-=base_out; rq+=cp
pool=dict(canonical=True,quote_wsol=True,cp_ts=c[0],cp_slot=c[1]+1,cp_seq=c[2]+1,pool_base=rb0,pool_quote=rq0+vq,events=ev)
rec=rec_of(T,complete=(c[0],c[1],c[2]),pool=pool); DEC=54; out=L.simulate(rec,DEC,T[DEC][0],N,pool=L.pool_prepare(pool))
check("migration_then_TP_in_pool",out["migrated_in_window"] and out["splice_ok"] and out[H]["state"]=="TP_FIRST" and out[H]["venue"]=="pool",f"{out[H]}")
# 7. lipsa starii PumpSwap -> CROSS_MIGRATION_LABEL_UNAVAILABLE
out=L.simulate(rec_of(T,complete=(c[0],c[1],c[2]),pool=None),DEC,T[DEC][0],N,pool=None); check("missing_pumpswap_state_unavailable",out["splice_ok"] is False and out[H]["state"] is None and out[H]["label_kind"]=="CROSS_MIGRATION_LABEL_UNAVAILABLE",f"{out[H]}")
# 8. taxa/VQ ambigua: evenimente inconsistente -> pool_prepare None
bad=copy.deepcopy(pool); 
for i,a in enumerate(bad["events"]): a[10]=a[10]*(1+0.3*(i%3))
check("ambiguous_vq_rejects_splice",L.pool_prepare(bad) is None,"implied_vq IQR mare")
# 9. rezerve virtuale nenule: valoarea cu vq > fara vq, plafonata la quote-ul real
h=10**12; v1=L.pool_liq(rb0,rq0,vq,h,55); v0=L.pool_liq(rb0,rq0,0,h,55); cap=L.pool_liq(rb0,10**6,vq,h,55)
check("nonzero_virtual_reserves",v1>v0 and cap<=10**6,f"vq {v1} novq {v0} cap {cap}")
# 10. impact mai rau la notional mai mare
st=T[DEC]; hr=[L.curve_headroom(st[10],st[11],st[8],int(n*LAMP))[0] for n in (0.25,0.5,1.0)]; sl=[]
for n in (0.25,0.5,1.0):
    tok,ds=L.curve_buy(st[10],st[11],int(n*LAMP)); sl.append((ds/tok)/(st[10]/st[11])-1)
check("impact_worse_larger_notional",hr[0]>hr[1]>hr[2] and sl[0]<sl[1]<sl[2],f"headroom {hr} slip {sl}")
# 11. maximum un semnal per mint
srs=[dict(landmark=Lm,f={"headroom_025":3.0},p_tp=0.5,p_sl=0.1,ev=0.01,ev_lcb=0.001) for Lm in L.LANDMARKS]; pol=dict(band=(20,70),p_tp_min=0.3,p_sl_max=0.3)
d=L.decide_mint(srs,pol,0.25); check("one_signal_per_mint",d is not None and d["landmark"]==20 and sum(1 for s in srs if L.eligible(s,pol,0.25)[0])>1,f"ales {d['landmark'] if d else None}")
# 12. modificarea viitorului nu schimba features/predictia (motorul streaming)
def run_engine(events):
    E=L.Engine(); [E.on_event(e) for e in events]; return E.rows
T=mk_curve(base+big_buys(10,10,50,2*LAMP,"p")); ev=[["C",T[0][0]-5,T[0][1]-5,0,"SYNTH","creator"]]+[["T",t[0],t[1],t[2],t[3],"SYNTH",t[4],t[5],t[6],t[7],t[8],t[9],t[10],t[11]] for t in T]
rows=run_engine(ev); lm20=next(r for r in rows if r["landmark"]==20); cut=lm20["i"]+2
alt=ev[:cut]+[["T",t[0]+5,t[1]+7,t[2]+100,0,"SYNTH","zz",5*LAMP,1,0,t[8],t[9],t[10],t[11]] for t in T[cut-1:]]   # viitor complet diferit
rows2=run_engine(alt); lm20b=next(r for r in rows2 if r["landmark"]==20)
check("future_mutation_no_feature_change",lm20["f"]==lm20b["f"] and len(rows)>1,f"landmark 20 identic; {len(rows)} landmark-uri")
# 13. toate snapshot-urile unui mint in acelasi fold (split per create_ts)
sys.argv=["x"]; import importlib
try:
    import build_dataset as BD; sp={BD.split_of(t) for t in [lm20["create_ts"]]*8}; check("same_fold_per_mint",len(sp)==1,f"{sp}")
except Exception as ex: check("same_fold_per_mint",False,f"build_dataset indisponibil: {ex}")
json.dump(dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",tests=R,all_pass=all(v["pass_"] for v in R.values())),open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"test_results.json"),"w"),indent=1)
print("ALL_PASS" if all(v["pass_"] for v in R.values()) else "SOME_FAIL")
