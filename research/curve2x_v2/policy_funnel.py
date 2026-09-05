"""CURVE2X V2 — diagnostic POST-HOC (nu modifica politica): funnel-ul conditiilor universale si al pragurilor politicii selectate, per segment, la nivel de rand si de mint.
Explica de ce grila este infezabila pe CAL. Nu se cauta praguri noi."""
import gzip,json,sys,os,collections,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L, model_stage as MS
from curve2x_paper_watcher import Scorer
D=os.environ.get("CURVE2X_DERIVED_DIR",os.path.join(os.path.dirname(os.path.abspath(__file__)),"derived")); OUT="research/curve2x_v2"
art=json.load(open(f"{OUT}/model_artifact.json")); S=Scorer(art); pol=S.pol; N=S.N; W=MS.gap_windows(); rows=[json.loads(l) for l in gzip.open(f"{D}/curve2x_rows.jsonl.gz","rt")]
fun={}
for seg in ("CAL","VAL","CONF"):
    rr=[r for r in rows if r["split"]==seg]; c=collections.Counter(); mints=collections.defaultdict(set); evs=[]; lcbs=[]; ptp=[]; psl=[]
    for r in rr:
        sc=S.score(r); f=r["f"]; Lm=r["landmark"]; lo,hi=max(pol["band"][0],L.ENTRY_MIN),min(pol["band"][1],L.ENTRY_MAX); steps=[]
        steps.append(("rows",True)); steps.append(("in_band",lo<=Lm<=hi)); steps.append(("headroom_ge_2",f.get(f"headroom_{L.notional_tag(N)}",0)>=2.0)); steps.append(("no_known_gap",not L.known_gap(r["ts"],W)))
        steps.append(("p_tp_ge_min",sc["p_tp"]>=pol["p_tp_min"])); steps.append(("p_sl_le_max",sc["p_sl"]<=pol["p_sl_max"])); steps.append(("ev_gt_0",sc["ev"]>0)); steps.append(("ev_lcb_gt_0",sc["ev_lcb"]>0))
        ok=True
        for name,cond in steps:
            ok=ok and cond
            if ok: c[name]+=1; mints[name].add(r["mint"])
        if lo<=Lm<=hi: evs.append(sc["ev"]); lcbs.append(sc["ev_lcb"]); ptp.append(sc["p_tp"]); psl.append(sc["p_sl"])
    fun[seg]=dict(funnel_rows=dict(c),funnel_mints={k:len(v) for k,v in mints.items()},in_band_pred=dict(n=len(evs),ev_mean=float(np.mean(evs)) if evs else None,ev_pos_share=float(np.mean(np.array(evs)>0)) if evs else None,ev_lcb_pos_share=float(np.mean(np.array(lcbs)>0)) if lcbs else None,p_tp_q50=float(np.median(ptp)) if ptp else None,p_tp_q90=float(np.quantile(ptp,0.9)) if ptp else None,p_sl_q10=float(np.quantile(psl,0.1)) if psl else None,p_sl_q50=float(np.median(psl)) if psl else None,share_p_tp_ge_030_and_p_sl_le_040=float(np.mean((np.array(ptp)>=0.3)&(np.array(psl)<=0.4))) if ptp else None))
res=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED / DIAGNOSTIC_POST_HOC (fara modificarea politicii)",policy=pol,funnel=fun); json.dump(res,open(f"{OUT}/policy_funnel.json","w"),indent=1); print(json.dumps(res))
