"""S1 LARGE_SELL_OVERSHOOT_REVERSION (spec inghetat in cod inainte de outcome). Evenimente: SellEvent mari in pool-urile din cache-ul m_pools (946 migrari, T0..T0+420 s; portofele, creator) si pass2 (571 pool-uri, banda intreaga).
Trasaturi imediat dupa sell: size_rel = quote vandut / rq real pre-sell; impact = (pret post / pret pre - 1); referinta = pretul executabil al altor pool-uri active pentru acelasi mint (pass2) sau pretul pre-sell; vol/lichiditate pre-sell.
Semnal: size_rel >= decila 9 DEV SI displacement >= decila 9 DEV; excluderi: creator, sell-uri in semnaturi de arbitraj cross-pool (recensamant), rupturi/outage, drenare (rq_post < 1 SOL). Intrare +3 sloturi worst-of, 0,10 SOL, iesire +60 s; stres +5; cost x1.25; 120 s descriptiv."""
import sys,gzip,json,collections,statistics as S,bisect,time,math; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"; LAMP=10**9
spec=dict(strategy="S1_LARGE_SELL_OVERSHOOT_REVERSION",mechanism="un sell mare intr-un AMM subtire deplaseaza mecanic pretul sub referinta; arbitrajorii si cumparatorii obisnuiti restaureaza o parte din impact",who_loses="vanzatorul mare (plateste impactul) si LP-ul pool-ului subtire; noi cumparam dupa deplasare si vindem dupa restaurare partiala",
  events="toate SellEvent din m_pools (946 pool-uri, [T0, T0+420 s]) si pass2 (571 pool-uri) cu rezerve pre/post decodate",features=["size_rel = quote_out / rq_pre","impact_bp = (px_post/px_pre - 1) x 1e4 (negativ)","displacement_bp = px_post fata de referinta (alte pool-uri ale mint-ului la ultima stare ancorata <= slotul sell-ului; altfel px_pre)","vol_pre (dev. std. log-randamente ultimele 20 stari)","rq_pre"],
  signal="size_rel >= decila 9 DEV AND displacement_bp <= decila 1 DEV (cea mai negativa); stare solvabila (rq_post >= 1 SOL), fara ruptura de lant intre sell si landing, fara outage",exclusions=["vanzator = creatorul mint-ului","semnatura in ciclurile exacte ale recensamantului (arbitraj cross-pool)","evenimente cu lp_bp=0 (speciale)","pool-uri cu < 5 stari inainte (VQ)"],
  execution="intrare la +3 sloturi dupa slotul sell-ului (worst-of pre/post), 0,10 SOL exact-B; iesire +60 s; stres +5 sloturi; cost x1.25; 120 s descriptiv; max o pozitie de portofoliu per slot",rejects=["profitul dispare fara cele mai mari 1 % sell-uri","profitul dispare dupa controlul miscarii pietei aceluiasi token (randamentul pool-urilor de referinta in aceeasi fereastra)"],frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s1_frozen_spec.json",spec)
cens=set()
try:
    for l in gzip.open(f"{C.D}/census_rows.jsonl.gz","rt"):
        c=json.loads(l)
        if c["cls"] in ("EXACT","DUST"): cens.add(c["sig"])
except Exception: pass
# pool -> (ev, vq, creator, mint, day_fn)
pools={}
for l in gzip.open(f"{C.D}/m_pools.jsonl.gz","rt"):
    x=json.loads(l); pools[x["pool"]]=dict(ev=x["ev"],vq=x["vq"],creator=x["creator"],mint=x["mint"],src="m")
E=A.load_pass2(); meta=A.load_rpc_meta(); groups=collections.defaultdict(list)
for p,ev in E.items():
    if p in pools or not ev: continue
    vq=A.implied_vq(ev)[0]
    if vq is None or meta.get(p,{}).get("orientation")!="STRICT": continue
    pools[p]=dict(ev=ev,vq=int(vq),creator=None,mint=meta[p]["base_mint"],src="p")
for p,v in pools.items(): groups[v["mint"]].append(p)
def sig_of(e): return e[15] if isinstance(e[15],str) and len(e[15])>50 else None   # pass2: index 15 = semnatura; m_pools: index 15 = user (nu semnatura)
rows=[]; cnt=collections.Counter()
for p,v in pools.items():
    ev=v["ev"]; vq=v["vq"]; br=A.chain_breaks(ev); others=[q for q in groups[v["mint"]] if q!=p]
    for i,e in enumerate(ev):
        if e[5]!=0 or e[12]==0 or i<5: continue
        cnt["sells"]+=1
        if v["src"]=="m" and e[15]==v["creator"]: cnt["excl_creator"]+=1; continue
        s=sig_of(e)
        if s and s in cens: cnt["excl_arb_signature"]+=1; continue
        if e[9]<1*LAMP: cnt["excl_drain"]+=1; continue
        px_pre=(e[7]+vq)/e[6]; px_post=(e[9]+vq)/e[8]; size_rel=e[11]/e[7] if e[7]>0 else None
        ref=None
        for q in others:
            st=A.state_provable(pools[q]["ev"],e[2])
            if st: ref=(st[1]+pools[q]["vq"])/st[0]; break
        ref=ref or px_pre; disp=(px_post/ref-1)*1e4; lr=[math.log(((b[9]+vq)/b[8])/((a[9]+vq)/a[8])) for a,b in zip(ev[max(0,i-20):i-1],ev[max(0,i-20)+1:i]) if a[8]>0 and b[8]>0]; vol=(S.pstdev(lr)*1e4 if len(lr)>1 else 0.0)
        rows.append(dict(pool=p,mint=v["mint"],day=time.strftime("%Y-%m-%d",time.gmtime(e[1])),slot=e[2],i=i,size_rel=size_rel,impact_bp=(px_post/px_pre-1)*1e4,disp_bp=disp,vol_bp=vol,rq_pre=e[7]/LAMP,has_ref=(ref!=px_pre),quote_sold=e[11]/LAMP))
dev=[r for r in rows if r["day"]==C.DAYS["DEV"]]; q9_size=sorted(r["size_rel"] for r in dev)[int(0.9*len(dev))]; q1_disp=sorted(r["disp_bp"] for r in dev)[int(0.1*len(dev))]
thr=dict(q9_size_rel=q9_size,q1_disp_bp=q1_disp,n_dev_sells=len(dev)); C.write("s1_thresholds_frozen.json",dict(thr,frozen_at=time.strftime("%Y-%m-%d %H:%M:%S")))
sig=[r for r in rows if r["size_rel"]>=q9_size and r["disp_bp"]<=q1_disp]
# executie: max o pozitie de portofoliu per slot (prima semnal per slot, dupa cea mai mare deplasare)
bys=collections.defaultdict(list); [bys[r["slot"]].append(r) for r in sig]; chosen=[min(v,key=lambda r:r["disp_bp"]) for v in bys.values()]
out=[]
for r in chosen:
    v=pools[r["pool"]]; o=C.execute_at(v["ev"],v["vq"],r["slot"],3,0.10,60); o5=C.execute_at(v["ev"],v["vq"],r["slot"],5,0.10,60); oc=C.execute_at(v["ev"],v["vq"],r["slot"],3,0.10,60,fee_mult=1.25); o120=C.execute_at(v["ev"],v["vq"],r["slot"],3,0.10,120)
    # controlul miscarii pietei: randamentul pool-urilor de referinta in aceeasi fereastra (entry->exit), daca exista
    mk=None
    if o["status"]=="OK":
        for q in [q for q in groups[r["mint"]] if q!=r["pool"]]:
            a=A.state_after_slot(pools[q]["ev"],o["entry_slot"]); ts=[e[1] for e in pools[q]["ev"]]; j=bisect.bisect_right(ts,o["exit_ts"])-1
            if a and j>=0: mk=((pools[q]["ev"][j][9]+pools[q]["vq"])/pools[q]["ev"][j][8])/((a[1]+pools[q]["vq"])/a[0])-1; break
    out.append(dict(r,status=o["status"],pnl=o.get("pnl"),pnl5=o5.get("pnl"),pnlc=oc.get("pnl"),pnl120=o120.get("pnl"),market_move=mk,pnl_mkt_adj=((o["pnl"]-mk*0.10) if (o["status"]=="OK" and mk is not None) else None)))
test=[r for r in out if r["day"]!=C.DAYS["DEV"]]; st=C.stats(test); bs=C.boot(test); st5=C.stats(test,"pnl5"); stc=C.stats(test,"pnlc")
g,verdict=C.global_gate(st,bs,st5,stc,0.05)
srt=sorted([r for r in test if r.get("pnl") is not None],key=lambda r:-r["quote_sold"]); ex1=C.stats(srt[max(1,len(srt)//100):]); adj=C.stats(test,"pnl_mkt_adj")
if verdict.startswith("PASS") and ((ex1 or {}).get("EV",-1)<=0 or (adj or {}).get("EV",-1)<=0): verdict="FAIL_REJECT_RULE (fara top 1 % sell-uri sau dupa controlul pietei)"
res=dict(spec_sha256=C.sha(f"{OUT}/s1_frozen_spec.json"),thresholds=thr,counts=dict(cnt,pools=len(pools),sell_rows=len(rows),signals=len(sig),chosen=len(chosen),with_reference=sum(1 for r in rows if r["has_ref"])),dev_descriptive=C.stats([r for r in out if r["day"]==C.DAYS["DEV"]]),test=st,bootstrap=bs,stress5=st5,cost125=stc,descriptive_120=C.stats(test,"pnl120"),ex_largest_1pct_sells=ex1,market_adjusted=adj,status_counts=dict(collections.Counter(r["status"] for r in out)),gate=g,verdict=verdict)
C.write("s1_results.json",res); print("S1",verdict,"N",(st or {}).get("N"),"mints",(st or {}).get("mints"),"EV",(st or {}).get("EV"),"PF",(st or {}).get("PF"),"CI",(bs or {}).get("CI95"),dict(cnt)); print("S1_DONE")
