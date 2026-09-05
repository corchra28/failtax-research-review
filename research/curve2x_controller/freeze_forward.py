"""Ingheata spec-ul de forward paper INAINTE de orice data noua: model hash (champion imuabil), prag, schema de trasaturi, porti, maturitate 960 s, o decizie per mint, fara reantrenare in confirmare."""
import os,sys,json,time,hashlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); import controller_lib as C
champ=C.Champion()
def fit_baseline():
    """baseline state/headroom (model C V3): logit doar pe STATE_FEATS, TRAIN V3, calibrare pe CAL V3; determinist. Inghetat prin hash in spec."""
    import gzip,numpy as np; sys.path.insert(0,C.V3); import model_v3 as M3; V=C.V; L=C.L
    D3=os.environ.get("CURVE2X_V3_DERIVED_DIR",os.path.join(C.V3,"derived_v3")); rows=[json.loads(l) for l in gzip.open(f"{D3}/v3_rows.jsonl.gz","rt")]
    tr=[r for r in rows if r["split"]=="TRAIN" and M3.usable(r)]; ca=[r for r in rows if r["split"]=="CAL" and M3.usable(r)]; Xtr,fill=L.X_of(tr,V.STATE_FEATS); Xca,_=L.X_of(ca,V.STATE_FEATS,fill)
    clf=L.fit_mlogit(Xtr,M3.Y_of(tr)); cal=L.fit_vector_scaling(L.predict(clf,Xca),M3.Y_of(ca)); reg=L.fit_gbm_reg(Xtr,M3.pnl_of(tr)); p=L.pred_gbm_reg(reg,Xca); y=M3.pnl_of(ca); import numpy as np; edges=np.quantile(p,np.linspace(0,1,6)[1:-1]).tolist(); dec=np.clip(np.searchsorted(edges,p,side="right"),0,4)
    rs=dict(edges=edges,sd=[float((p[dec==d]-y[dec==d]).std()) if (dec==d).sum()>=5 else float((p-y).std()) for d in range(5)],n=[int((dec==d).sum()) for d in range(5)])
    art=dict(label="BASELINE_STATE_HEADROOM (model C V3)",features=V.STATE_FEATS,fill=fill.tolist(),models=dict(clf=clf,cal=cal,reg=reg,regstats=rs),policy_enabled=False); s=json.dumps(art,sort_keys=True,separators=(",",":"),default=float); open(os.path.join(HERE,"baseline_state_headroom.json"),"w").write(s); return hashlib.sha256(s.encode()).hexdigest()
bh=fit_baseline() if not os.path.exists(os.path.join(HERE,"baseline_state_headroom.json")) else hashlib.sha256(open(os.path.join(HERE,"baseline_state_headroom.json"),"rb").read()).hexdigest()
spec=dict(baseline_sha256=bh,name="CURVE2X_FORWARD_PAPER_SPEC",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),status="FROZEN_BEFORE_NEW_DATA",model_hash=champ.model_hash,feature_schema_hash=champ.feature_schema_hash,feature_schema=champ.art["features"],policy=champ.policy,policy_enabled=False,actions=["REJECT","WATCH"],
 maturity_s=960,one_decision_per_mint=True,no_retraining_in_confirmation=True,predictions_append_only_before_outcomes=True,gates=C.FORWARD_GATES,baseline="state/headroom (model C V3) cu aceeasi politica",multiple_testing="Bonferroni pe toate challengerele incercate (registru global)",
 data_source="director local de colectare scris de un colector extern (WSS) aprobat separat; controller-ul NU deschide RPC/WSS; replay-ul istoric NU conteaza ca forward",collection_started=False,LIVE_TRADING_ENABLED=False)
s=json.dumps({k:v for k,v in spec.items() if k!="spec_sha256"},sort_keys=True,indent=1); spec["spec_sha256"]=hashlib.sha256(s.encode()).hexdigest(); json.dump(spec,open(os.path.join(HERE,"forward_spec.json"),"w"),indent=1); print("FORWARD_SPEC_FROZEN sha256",spec["spec_sha256"][:16],"model",champ.model_hash[:16])
