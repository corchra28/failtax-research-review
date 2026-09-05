#!/usr/bin/env python3
"""Promovarea Challenger -> Champion: NICIODATA automata. Cere: (1) evaluation_report.json cu toate portile statistice PASS, (2) un fisier de aprobare umana care contine hash-ul raportului
si fraza exacta de confirmare, (3) --i-am-a-human. Chiar si atunci: scrie un champion.json NOU (cel vechi este arhivat), policy_enabled ramane false, LIVE_TRADING_ENABLED=NO."""
import os,sys,json,hashlib,time,argparse,shutil
HERE=os.path.dirname(os.path.abspath(__file__)); ST=os.environ.get("CURVE2X_CTRL_STATE",os.path.join(HERE,"state"))
ap=argparse.ArgumentParser(); ap.add_argument("--human-approval-file",required=True); ap.add_argument("--i-am-a-human",action="store_true"); a=ap.parse_args()
if not a.i_am_a_human: sys.exit("REFUSED: aprobare umana explicita obligatorie (--i-am-a-human)")
rep_p=os.path.join(ST,"evaluation_report.json"); rep=json.load(open(rep_p)); rh=hashlib.sha256(open(rep_p,"rb").read()).hexdigest()
if not rep.get("all_statistical_gates_pass"): sys.exit("REFUSED: portile statistice nu sunt toate PASS")
ap_=json.load(open(a.human_approval_file))
if ap_.get("evaluation_report_sha256")!=rh or ap_.get("confirmation")!="I approve promoting the challenger to champion for PAPER/SHADOW use only": sys.exit("REFUSED: fisierul de aprobare nu corespunde raportului sau frazei de confirmare")
ch=os.path.join(ST,"challenger_artifact.json"); h=hashlib.sha256(open(ch,"rb").read()).hexdigest(); old=json.load(open(os.path.join(HERE,"champion.json"))); shutil.copy(os.path.join(HERE,"champion.json"),os.path.join(ST,f"champion_archived_{int(time.time())}.json")); new_path=os.path.join(ST,f"champion_{h[:16]}.json"); shutil.copy(ch,new_path)
json.dump(dict(role="CHAMPION",artifact_path=os.path.relpath(new_path,os.path.dirname(os.path.dirname(HERE))),artifact_sha256=h,promoted_from=old["artifact_sha256"],approved_by="HUMAN (fisier de aprobare)",approved_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),policy_enabled=False,immutable=True,live_trading_enabled=False),open(os.path.join(HERE,"champion.json"),"w"),indent=1)
print("PROMOTED (paper/shadow only) | new champion",h[:16],"| POLICY_ENABLED=false | LIVE_TRADING_ENABLED=NO")
