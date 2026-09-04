"""validate_bundle.py — validare independenta a pachetului (ruleaza din interiorul research/external_review_bundle/ sau cu calea ca argument).
Verifica: fisiere, gzip citibil, scheme, hash-uri (manifest), chei de join, duplicate, trasaturi <= decizie, outcome dupa intrare, nume de chei secrete, reproducerea metricilor de headline."""
import os,sys,gzip,csv,json,hashlib,re,statistics as S
B=sys.argv[1] if len(sys.argv)>1 else os.path.dirname(os.path.abspath(__file__)); fails=[]; notes=[]
REQ=["README.md","data_dictionary.csv","pool_master.csv.gz","pool_feature_panel.csv.gz","pool_outcomes.csv.gz","shadow_trade_ledger.csv.gz","regime_blocks.csv","regime_executed_trades.csv","hourly_daily_summary.csv","model_and_rule_trials.csv","integrity_checks.json","casebook.jsonl.gz","headline_metrics.json","code/regime_gate.py","code/regime_cache_build.py","code/master_leakage_tests.py","code/build_external_bundle.py","validate_bundle.py"]
for f in REQ:
    if not os.path.exists(os.path.join(B,f)): fails.append(f"MISSING {f}")
def rd(name):
    p=os.path.join(B,name); f=gzip.open(p,"rt",newline="") if name.endswith(".gz") else open(p,newline=""); rows=list(csv.DictReader(f)); f.close(); return rows
try:
    pm=rd("pool_master.csv.gz"); fp=rd("pool_feature_panel.csv.gz"); oc=rd("pool_outcomes.csv.gz"); sh=rd("shadow_trade_ledger.csv.gz"); bl=rd("regime_blocks.csv"); et=rd("regime_executed_trades.csv")
except Exception as e: fails.append(f"READ_ERROR {e}"); pm=fp=oc=sh=bl=et=[]
# scheme minime
need={"pool_master.csv.gz":["pool_id","mint_id","eligible","exclusion_reason","complete_ts"],"pool_feature_panel.csv.gz":["pool_id","horizon_s","decision_ts","feature_max_ts","actual_entry_ts"],"pool_outcomes.csv.gz":["pool_id","horizon_s","outcome_entry_ts","OUT_TP100_SL30_300_pnl_usd","OUT_TP100_SL30_300_exit_ts"],"shadow_trade_ledger.csv.gz":["pool_id","shadow_entry_ts","SHADOW_RESOLUTION_TIME","pnl_usd"],"regime_blocks.csv":["decision_ts","REGIME_ON","gate_N","OUTCOME_strategy_pnl_usd"]}
for name,cols in need.items():
    rows={"pool_master.csv.gz":pm,"pool_feature_panel.csv.gz":fp,"pool_outcomes.csv.gz":oc,"shadow_trade_ledger.csv.gz":sh,"regime_blocks.csv":bl}[name]
    if rows and any(c not in rows[0] for c in cols): fails.append(f"SCHEMA {name} lipsesc {[c for c in cols if c not in rows[0]]}")
# chei
ids={r["pool_id"] for r in pm}; el={r["pool_id"] for r in pm if r["eligible"]=="1"}
if len(ids)!=len(pm): fails.append("DUPLICATE pool_master pool_id")
if len({(r["pool_id"],r["horizon_s"]) for r in fp})!=len(fp): fails.append("DUPLICATE feature panel key")
if len({(r["pool_id"],r["horizon_s"]) for r in oc})!=len(oc): fails.append("DUPLICATE outcomes key")
if len({r["pool_id"] for r in sh})!=len(sh): fails.append("DUPLICATE shadow ledger")
for name,rows in (("features",fp),("outcomes",oc),("shadow",sh)):
    bad=sum(1 for r in rows if r["pool_id"] not in ids)
    if bad: fails.append(f"JOIN {name}: {bad} pool_id fara rand in pool_master")
if {r["pool_id"] for r in fp}!=el or {r["pool_id"] for r in oc}!=el: fails.append("JOIN: multimea pool-urilor eligibile difera intre master/features/outcomes")
# timestamp-uri
v=sum(1 for r in fp if r["feature_max_ts"] and float(r["feature_max_ts"])>=float(r["decision_ts"]))
if v: fails.append(f"FEATURE_AFTER_DECISION {v}")
v=sum(1 for r in oc if r.get("OUT_TP100_SL30_300_exit_ts") and float(r["OUT_TP100_SL30_300_exit_ts"])<float(r["outcome_entry_ts"]))
if v: fails.append(f"OUTCOME_BEFORE_ENTRY {v}")
v=sum(1 for r in sh if float(r["SHADOW_RESOLUTION_TIME"])<float(r["shadow_entry_ts"]))
if v: fails.append(f"SHADOW_RESOLUTION_BEFORE_ENTRY {v}")
# secrete: nume de coloane / fisiere / continut README+cod
pat=re.compile(r"(api[_-]?key|secret|private[_-]?key|seed|mnemonic|token=|password|authorization)",re.I)
for name,rows in (("master",pm),("features",fp),("outcomes",oc),("shadow",sh),("blocks",bl),("trades",et)):
    if rows and any(pat.search(c) for c in rows[0]): fails.append(f"SECRET_LIKE_COLUMN in {name}")
for root,_,fs in os.walk(B):
    for f in fs:
        if f.endswith((".py",".md",".json",".csv")):
            if f=="validate_bundle.py": continue   # propriul fisier contine sabloanele de cautare
            txt=open(os.path.join(root,f),errors="ignore").read()
            if re.search(r"api-key=[A-Za-z0-9-]{8,}",txt) or ("BEGIN "+"PRIVATE KEY") in txt or re.search(r"\b[1-9A-HJ-NP-Za-km-z]{43,44}pump\b",txt): fails.append(f"SECRET_OR_RAW_ADDRESS in {f}")
# adrese brute in date (base58 lung) — id-urile sunt hex de 32
for name,rows in (("master",pm),("shadow",sh)):
    if rows and any(len(r["pool_id"])!=32 or not re.fullmatch(r"[0-9a-f]{32}",r["pool_id"]) for r in rows[:2000]): fails.append(f"ID_FORMAT {name}")
# hash-uri din manifest (daca exista langa pachet)
mp=os.path.join(os.path.dirname(B.rstrip("/")),"external_review_bundle_manifest.json")
if os.path.exists(mp):
    man=json.load(open(mp)); bad=0
    for f,info in man["files"].items():
        p=os.path.join(B,f)
        if f=="validate_bundle.py" or not os.path.exists(p): continue
        h=hashlib.sha256(open(p,"rb").read()).hexdigest()
        if h!=info["sha256"]: bad+=1
    if bad: fails.append(f"HASH_MISMATCH {bad}")
    notes.append(f"manifest verificat: {len(man['files'])} fisiere")
# reproducerea metricilor de headline
head=json.load(open(os.path.join(B,"headline_metrics.json")))
unc=[float(r["pnl_usd"]) for r in sh]; ev=sum(unc)/len(unc)
if abs(ev-head["UNCOND_EV"])>1e-6 or len(unc)!=head["UNCOND_N"]: fails.append(f"HEADLINE_UNCOND mismatch {ev} vs {head['UNCOND_EV']}")
on=[float(r["OUTCOME_strategy_pnl_usd"]) for r in bl if r["REGIME_ON"]=="1" and r["OUTCOME_strategy_pnl_usd"]!=""]
if head["ON_trades"]!=len(on): fails.append(f"HEADLINE_ON_TRADES {len(on)} vs {head['ON_trades']}")
if on and head["ON_EV"] is not None and abs(sum(on)/len(on)-head["ON_EV"])>1e-6: fails.append("HEADLINE_ON_EV mismatch")
if sum(1 for r in bl if r["REGIME_ON"]=="1")!=head["N_ON_blocks"]: fails.append("HEADLINE_ON_BLOCKS mismatch")
# recalcularea portii dintr-un bloc (independenta de scripturi): gate_N>=30 etc. coerent cu REGIME_ON
inc=0
for r in bl:
    g=lambda k: float(r[k]) if r[k] not in ("","None") else None
    on_=(g("gate_N") or 0)>=30 and (g("gate_trimmed_mean") or 0)>0 and (g("gate_PF") or 0)>1.15 and (g("gate_median") or 0)>0 and (g("gate_ex_best_1_EV") or 0)>0 and (g("gate_EV_first30") or 0)>0 and (g("gate_EV_second30") or 0)>0
    if int(on_)!=int(r["REGIME_ON"]): inc+=1
if inc: fails.append(f"GATE_RECOMPUTE_MISMATCH {inc}")
notes.append(f"randuri: master {len(pm)} (eligibile {len(el)}), features {len(fp)}, outcomes {len(oc)}, shadow {len(sh)}, blocuri {len(bl)}, tranzactii {len(et)}")
print("\n".join(notes)); print("FAILS:",fails if fails else "none"); print("BUNDLE_VALIDATION =","PASS" if not fails else "FAIL")
