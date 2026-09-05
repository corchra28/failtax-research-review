#!/usr/bin/env python3
"""Promovarea Challenger -> Champion: NICIODATA automata si NICIODATA pe baza de replay/istoric. Accepta EXCLUSIV state/evaluation_report_forward.json cu report_kind=FORWARD; verifica spec_sha256
(recalculat), fereastra prospectiva neatinsa (registru), Bonferroni (alpha = 0,05 / challengere incercate) si toate portile forward; cere fisier de aprobare umana cu hash-ul raportului si --i-am-a-human.
Chiar dupa promovare: policy_enabled=false, LIVE_TRADING_ENABLED=false."""
import os,sys,json,hashlib,time,argparse,shutil
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); ST=os.environ.get("CURVE2X_CTRL_STATE",os.path.join(HERE,"state"))
ap=argparse.ArgumentParser(); ap.add_argument("--report",default=os.path.join(ST,"evaluation_report_forward.json")); ap.add_argument("--human-approval-file",required=True); ap.add_argument("--i-am-a-human",action="store_true"); a=ap.parse_args()
def refuse(m): print("REFUSED:",m); sys.exit(3)
if not a.i_am_a_human: refuse("aprobare umana explicita obligatorie (--i-am-a-human)")
if os.path.basename(a.report)!="evaluation_report_forward.json" or not os.path.exists(a.report): refuse("se accepta exclusiv evaluation_report_forward.json")
rep=json.load(open(a.report)); rh=hashlib.sha256(open(a.report,"rb").read()).hexdigest()
if rep.get("report_kind")!="FORWARD" or "REPLAY" in str(rep.get("label","")).upper() or "HISTORIC" in str(rep.get("label","")).upper(): refuse("raport replay/istoric — promovarea cere forward autentic")
import forward_lib as F, controller_lib as C
spec=F.load_spec(os.path.join(HERE,"forward_spec.json"))
if rep.get("spec_sha256")!=spec["spec_sha256"]: refuse("spec_sha256 al raportului nu corespunde spec-ului inghetat curent")
if not rep.get("untouched_window"): refuse("fereastra prospectiva nu este neatinsa (registru)")
n_tried=C.n_challengers_tried()
if abs(rep.get("bonferroni_alpha",-1)-0.05/max(1,n_tried))>1e-12: refuse(f"Bonferroni: raportul foloseste alpha {rep.get('bonferroni_alpha')} dar registrul cere {0.05/max(1,n_tried):.6f} ({n_tried} challengere)")
g=rep.get("gates",{}); fails=[k for k,v in g.items() if k not in ("HUMAN_APPROVAL_REQUIRED","MULTIPLE_TESTING_CORRECTION") and v is not True]
if fails: refuse(f"porti forward nepromovabile: {fails}")
ap_=json.load(open(a.human_approval_file)) if os.path.exists(a.human_approval_file) else {}
if ap_.get("evaluation_report_sha256")!=rh or ap_.get("confirmation")!="I approve promoting the challenger to champion for PAPER/SHADOW use only": refuse("fisierul de aprobare nu corespunde raportului sau frazei de confirmare")
ch=os.path.join(ST,"challenger_artifact.json")
if not os.path.exists(ch): refuse("niciun challenger antrenat")
h=hashlib.sha256(open(ch,"rb").read()).hexdigest(); old=json.load(open(os.path.join(HERE,"champion.json"))); shutil.copy(os.path.join(HERE,"champion.json"),os.path.join(ST,f"champion_archived_{int(time.time())}.json")); new_path=os.path.join(ST,f"champion_{h[:16]}.json"); shutil.copy(ch,new_path)
json.dump(dict(role="CHAMPION",artifact_path=os.path.relpath(new_path,os.path.dirname(os.path.dirname(HERE))),artifact_sha256=h,promoted_from=old["artifact_sha256"],approved_by="HUMAN (fisier de aprobare)",approved_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),report_sha256=rh,policy_enabled=False,immutable=True,live_trading_enabled=False),open(os.path.join(HERE,"champion.json"),"w"),indent=1)
C.register_attempt("PROMOTION",dict(new_champion=h,report_sha256=rh,window_end_ts=rep.get("window_end_ts")))
print("PROMOTED (paper/shadow only) | new champion",h[:16],"| POLICY_ENABLED=false | LIVE_TRADING_ENABLED=NO")
