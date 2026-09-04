"""S7 TOXIC_TOKEN_AVOIDANCE_FILTER (spec inghetat in cod inainte de outcome): scor de toxicitate din componente PRE-intrare normalizate pe DEV (ranguri, ponderi egale), aplicat baseline-ului neconditionat
(decizie T0+60 s, intrare +3 sloturi worst-of, 0,10 SOL, iesire +60 s). Trece doar daca reduce pierderea din coada stanga SI imbunatateste EV net."""
import sys,gzip,json,collections,statistics as S,bisect,time; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"; spec=dict(strategy="S7_TOXIC_TOKEN_AVOIDANCE_FILTER",mechanism="respingerea tranzactiilor cu semne PRE-intrare de extractie (creator/concentrare/vanzari incumbente/spam/discontinuitati) reduce pierderile extreme ale unei intrari fixe",who_loses="nimeni direct: filtrul evita sa fim contrapartea extractorilor (creatori, sniperi, wash) in lansarile toxice",
  components=["creator_prior_failure_rate (istoricul creatorului din lansarile ANTERIOARE in banda: 1 - rata de migrare; None => neutru 0.5)","creator_inventory_share (pre-migrare)","top1_buy_share (dominanta unui portofel)","incumbent_sell_share (vanzari incumbente imediate)","spam_buyer_share (cota cumparatorilor post-only cu >= 20 mint-uri in 24 h anterioare)","chain_breaks_pre_decision (discontinuitati de rezerve inainte de D)","liquidity_deterioration (rq la D / rq la deschidere, inversat)","same_signature_multi_swap_share (evenimente din tranzactii cu >= 2 swap-uri in acelasi pool inainte de D)"],
  normalization="rang percentil pe DEV per componenta (toxicitate crescatoare), medie egal ponderata; filtru = scor >= Q3 DEV",baseline="decizie T0+60 s; intrare +3 sloturi (worst-of pre/post), 0,10 SOL, exact-B; iesire +60 s; stres +5 sloturi; cost x1.25",pass_rule="reduce pierderea medie a cozii stangi (5 % cele mai slabe) SI creste EV net pe VAL+PH; altfel TAIL_ONLY sau NO_VALUE",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s7_frozen_spec.json",spec)
P=[json.loads(l) for l in gzip.open(f"{C.D}/cohort_panel.jsonl.gz","rt")]; X={}
for l in gzip.open(f"{C.D}/m_pools.jsonl.gz","rt"): x=json.loads(l); X[x["mint"]]=x
# istoricul creatorului din lansarile anterioare din bandа (CreateEvent -> CompleteEvent), calculat din inventarul curbei: folosim m_pools (doar migrate) + creatii din regime cache? Sursa disponibila fara alta trecere: creatorii din m_pools (toate migrate) => rata de migrare anterioara nu e calculabila fara toate creatiile. Marcat NEUTRU (0.5) si raportat ca limitare.
def comps(f,x):
    D_=f["D"]; ev=[e for e in x["ev"] if e[1]<D_]; br=A.chain_breaks(ev) if ev else []; e0=x["ev"][0]
    spam=[b for b in f["buyers_prior"] if b[1]>=20]; spam_share=(sum(b[2] for b in spam)/f["post_only_buy_quote"]) if f["post_only_buy_quote"]>0 else 0.0
    sigcnt=collections.Counter(e[3] for e in ev); multi=sum(1 for e in ev if sigcnt[e[3]]>=2)/len(ev) if ev else 0.0
    liq_det=(e0[7]/ev[-1][9]) if ev and ev[-1][9]>0 else 1.0
    return dict(creator_prior_failure=0.5,creator_inventory_share=f["creator_inventory_share"],top1_buy_share=(f["top1_buy_share"] or 0.0),incumbent_sell_share=f["incumbent_sell_share"],spam_buyer_share=spam_share,chain_breaks=len(br),liquidity_deterioration=liq_det,same_sig_multi_share=multi)
rows=[]
for f in P:
    x=X[f["mint"]]; c=comps(f,x); vq=x["vq"]; ts=[e[1] for e in x["ev"]]; di=bisect.bisect_right(ts,f["D"])-1; dslot=x["ev"][di][2] if di>=0 else x["ev"][0][2]
    o=C.execute_at(x["ev"],vq,dslot,3,0.10,60); o5=C.execute_at(x["ev"],vq,dslot,5,0.10,60); oc=C.execute_at(x["ev"],vq,dslot,3,0.10,60,fee_mult=1.25); o120=C.execute_at(x["ev"],vq,dslot,3,0.10,120)
    rows.append(dict(mint=f["mint"],day=f["day"],comp=c,pnl=o.get("pnl"),status=o["status"],pnl5=o5.get("pnl"),pnlc=oc.get("pnl"),pnl120=o120.get("pnl")))
dev=[r for r in rows if r["day"]==C.DAYS["DEV"]]; keys=list(dev[0]["comp"].keys()); sd={k:sorted(r["comp"][k] for r in dev) for k in keys}
def score(r): return sum(bisect.bisect_right(sd[k],r["comp"][k])/len(sd[k]) for k in keys)/len(keys)
for r in rows: r["tox"]=score(r)
q3=sorted(r["tox"] for r in dev)[int(0.75*len(dev))]; thr=dict(q3_toxicity=q3,components=keys); C.write("s7_thresholds_frozen.json",dict(thr,frozen_at=time.strftime("%Y-%m-%d %H:%M:%S")))
test=[r for r in rows if r["day"]!=C.DAYS["DEV"] and r["pnl"] is not None]; base=test; filt=[r for r in test if r["tox"]<q3]; removed=[r for r in test if r["tox"]>=q3]
def tail(rs,q=0.05):
    v=sorted(r["pnl"] for r in rs); k=max(1,int(len(v)*q)); return sum(v[:k])/k if v else None
res=dict(spec_sha256=C.sha(f"{OUT}/s7_frozen_spec.json"),thresholds=thr,baseline=C.stats(base),filtered=C.stats(filt),removed=C.stats(removed),tail5_baseline=tail(base),tail5_filtered=tail(filt),opportunity_reduction=(len(removed)/len(base) if base else None),remaining_trades=len(filt),stress5=dict(baseline=C.stats(base,"pnl5"),filtered=C.stats(filt,"pnl5")),cost125=dict(baseline=C.stats(base,"pnlc"),filtered=C.stats(filt,"pnlc")),descriptive_120=dict(baseline=C.stats(base,"pnl120"),filtered=C.stats(filt,"pnl120")),dev_descriptive=dict(baseline=C.stats(dev),filtered=C.stats([r for r in dev if r["tox"]<q3])),bootstrap_filtered=C.boot(filt),status_counts=dict(collections.Counter(r["status"] for r in rows)),limitation="creator_prior_failure neutru (istoricul complet al creatorilor cere o trecere separata pe toate creatiile; vezi S5)")
b=res["baseline"]; f_=res["filtered"]; tb=res["tail5_baseline"]; tf=res["tail5_filtered"]
if b and f_:
    tail_better=(tf is not None and tb is not None and tf>tb); ev_better=f_["EV"]>b["EV"]
    res["verdict"]=("TOXICITY_FILTER_IMPROVES_EXECUTION_SET" if (tail_better and ev_better) else ("TOXICITY_FILTER_REDUCES_TAIL_ONLY" if tail_better else "TOXICITY_FILTER_NO_VALUE")); res["standalone_profitability_claim"]=("NO (baseline filtrat negativ)" if f_["EV"]<=0 else "NU se afirma: filtrul nu este o strategie de sine statatoare")
else: res["verdict"]="INSUFFICIENT_CLEAN_SAMPLE"
C.write("s7_results.json",res); print("S7",res["verdict"],"base",{k:b.get(k) for k in ("N","EV","PF")} if b else None,"filt",{k:f_.get(k) for k in ("N","EV","PF")} if f_ else None,"tail",tb,tf); print("S7_DONE")
