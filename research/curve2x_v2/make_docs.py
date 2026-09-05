"""CURVE2X V2 — documente: model_card.md, calibration_tables.csv, ablations.csv, policy_grid_cal.csv, terminal_summary.txt, final_summary.json (din results.json)."""
import json,csv,os,sys,hashlib,time
OUT="research/curve2x_v2"; R=json.load(open(f"{OUT}/results.json")); SPEC=json.load(open(f"{OUT}/frozen_spec_V1_REJECTED.json")); BM=json.load(open(f"{OUT}/build_manifest.json")); LC=json.load(open(f"{OUT}/label_check.json")); TR=json.load(open(f"{OUT}/test_results.json"))
RC=json.load(open(f"{OUT}/replay_check.json")) if os.path.exists(f"{OUT}/replay_check.json") else {}
def f(x,d=4): return "n/a" if x is None or (isinstance(x,float) and x!=x) else (f"{x:.{d}f}" if isinstance(x,float) else str(x))
N="0.25"; EV=R["evaluation"]; g=R["gates"]; sel=R["selection"]["selected"]; pol=R["policy_selected"]
# calibrare
with open(f"{OUT}/calibration_tables.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["segment","class","bin","n","pred","obs"])
    for seg in ("VAL","CONF","VAL+CONF"):
        m=EV[seg][N].get("all_rows_metrics") or {}
        for cls,key in (("TP_FIRST","rel_tp"),("SL_FIRST","rel_sl")):
            for b in m.get(key,[]): w.writerow([seg,cls,b["bin"],b["n"],f(b["pred"]),f(b["obs"])])
    c=next(c for c in R["candidates"] if (c["abl"],c["kind"])==tuple(sel))
    for cls,key in (("TP_FIRST","rel_tp"),("SL_FIRST","rel_sl")):
        for b in c[key]: w.writerow(["CAL",cls,b["bin"],b["n"],f(b["pred"]),f(b["obs"])])
with open(f"{OUT}/ablations.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["ablation","model","cal_log_loss","cal_brier","cal_top_gap","cal_top_n","cal_ece_tp","valconf_log_loss","valconf_brier","valconf_ece_tp"])
    for c in R["candidates"]:
        v=R["ablations_val_conf"].get(f"{c['abl']}/{c['kind']}",{}); w.writerow([c["abl"],c["kind"],f(c["log_loss"]),f(c["brier"]),f(c["top_gap"]),c["top_n"],f(c["ece_tp"]),f(v.get("log_loss")),f(v.get("brier")),f(v.get("ece_tp"))])
with open(f"{OUT}/policy_grid_cal.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["band","p_tp_min","p_sl_max","cal_mints","cal_EV","cal_LCB90","cal_PF","cal_TP_rate","cal_SL_rate"])
    for gr in R["policy_grid_cal"]:
        p=gr["policy"]; c=gr["cal"]; w.writerow([f"{p['band'][0]}-{p['band'][1]}",p["p_tp_min"],p["p_sl_max"],c.get("usable",0),f(c.get("EV")),f(c.get("LCB90")),f(c.get("PF"),2),f(c.get("TP_FIRST_rate"),3),f(c.get("SL_FIRST_rate"),3)])
def seg_line(seg,Nn,var="base"):
    s=EV[seg][Nn][var]
    return f"| {seg} | {Nn} | {var} | {s.get('usable',0)} | {f(s.get('TP_FIRST_rate'),3)} | {f(s.get('SL_FIRST_rate'),3)} | {f(s.get('timeout_rate'),3)} | {f(s.get('EV'))} | {f(s.get('median'))} | {f(s.get('PF'),2)} | {s.get('CI95')} | {f(s.get('EX_BEST_1PCT'))} | {f(s.get('max_mint_share'),3)}/{f(s.get('max_creator_share'),3)}/{f(s.get('max_hour_share'),3)} |"
PF_=json.load(open(f"{OUT}/policy_funnel.json")) if os.path.exists(f"{OUT}/policy_funnel.json") else None; FUNNEL_=[]
if PF_:
    FUNNEL_=["","## Diagnostic post-hoc: funnel-ul conditiilor (nu modifica politica)","| segment | randuri | in banda | headroom>=2 | fara gap | P_TP>=min | P_SL<=max | EV>0 | EV_LCB90>0 | mint-uri finale |","|---|---|---|---|---|---|---|---|---|---|"]
    for seg,v in PF_["funnel"].items():
        fr=v["funnel_rows"]; FUNNEL_.append(f"| {seg} | {fr.get('rows',0)} | {fr.get('in_band',0)} | {fr.get('headroom_ge_2',0)} | {fr.get('no_known_gap',0)} | {fr.get('p_tp_ge_min',0)} | {fr.get('p_sl_le_max',0)} | {fr.get('ev_gt_0',0)} | {fr.get('ev_lcb_gt_0',0)} | {v['funnel_mints'].get('ev_lcb_gt_0',0)} |")
    FUNNEL_+=["",f"Constatare structurala: in banda de intrare, mediana P(SL_FIRST) este ~0,65 si decila 10 ~0,50 (VAL: {PF_['funnel']['VAL']['in_band_pred']}); conditia P_SL_FIRST <= 0,40 este indeplinita de < 0,5 % din randuri, iar EV prezis mediu in banda este negativ. Politica 2x / -50 % pe curba nu este fezabila la nivelul cerut, indiferent de pragul P_TP.",""]
card=[f"# CURVE2X V2 — model card (HISTORICAL_REMEDIATION_NOT_SEALED)","",f"Generat {time.strftime('%Y-%m-%d %H:%M %Z')}. Remediere a ranker_2x V1 (pastrat in `research/ranker_2x/v1/`). Toate zilele fusesera inspectate anterior: VAL/CONF NU sunt sealed. Zero RPC, zero date noi, zero tranzactii.","",
 "## Definitie",f"- Unitate: (mint, landmark de progres {SPEC['checkpoints']['grid_pct']} %), o singura decizie per mint (primul landmark eligibil in banda {pol['band']} ∩ [20,70]).",
 f"- Eticheta: first-passage pe valoarea neta a lichidarii propriei pozitii (overlay static, intregi, taxa curba 125 bp, cost retea 0,00021 SOL = PRESUPUNERE, intrare/iesire la +3 sloturi): TP_FIRST (>= 2x) / SL_FIRST (<= 0,5x; castiga la egalitate de slot) / TIMEOUT_OTHER; orizont primar 15 min; continuare in pool-ul canonic PumpSwap cu rezerve efective (raw + VQ implicit).",
 f"- Date: {BM['mints']} mint-uri cu >= 10 % progres in 31 min, {BM['rows']} randuri; split {BM['by_split']}; randuri cu gap excluse {BM['gap_rows']}; migrate in fereastra {BM['migrated_rows']}, splice OK {BM['splice_ok_rows']}, CROSS_MIGRATION_LABEL_UNAVAILABLE {BM['splice_unavailable_rows']}.",
 f"- Status primar (0,25 SOL, 15M): {BM['primary_status']}",f"- Teste sintetice: {sum(1 for v in TR['tests'].values() if v['pass_'])}/{len(TR['tests'])} PASS; LABEL_AGREEMENT (a doua implementare, {LC['cases']} cazuri, {LC['strata']} straturi) = {LC['LABEL_AGREEMENT']:.4f}.","",
 "## Selectia modelului (CAL; log loss -> Brier -> gap in top -> EV)",f"- Selectat: bloc **{sel[0]}**, model **{sel[1]}** ({'multinomial logistic L2' if sel[1]=='A' else 'GBM depth-2 multiclass'}); etape: {R['selection']}",
 f"- Prior TRAIN pe CAL: log loss {f(R['cal_baseline_log_loss_train_prior'])}; baseline M0 ({sel[1]}): log loss {f(R['baseline_M0']['log_loss'])}, Brier {f(R['baseline_M0']['brier'])}.","",
 "| ablatiune | model | CAL log loss | CAL Brier | CAL gap top | CAL n top | VAL+CONF log loss | VAL+CONF Brier |","|---|---|---|---|---|---|---|---|"]
for c in R["candidates"]:
    v=R["ablations_val_conf"].get(f"{c['abl']}/{c['kind']}",{}); card.append(f"| {c['abl']} | {c['kind']} | {f(c['log_loss'])} | {f(c['brier'])} | {f(c['top_gap'])} | {c['top_n']} | {f(v.get('log_loss'))} | {f(v.get('brier'))} |")
card+=["",f"Prior TRAIN pe VAL+CONF: log loss {f(R['ablations_val_conf_prior'])}.","","## Politica inghetata (grila fixa pe CAL, max LCB90 al EV per mint, >= 100 mint-uri)",f"- Selectata: {pol}; CAL: {R['policy_selected_cal']}; combinatii fezabile pe CAL: {R['policy_grid_feasible']}/48."+(f" NOTA: {R['policy_note']}" if R.get("policy_note") else ""),"",
 "## Evaluare (o singura data; nivel de mint; CI95 bootstrap pe clustere = ore)","| segment | notional | varianta | mint-uri | TP_FIRST | SL_FIRST | timeout | EV SOL | mediana | PF | CI95 | EX_BEST_1% | max cota mint/creator/ora |","|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for seg in ("VAL","CONF","VAL+CONF"):
    for Nn in ("0.25","0.5","1.0"):
        for var in ("base","stress_land5","stress_cost125"): card.append(seg_line(seg,Nn,var))
m=EV["VAL+CONF"][N]; arm={k:v for k,v in (m.get('all_rows_metrics') or {}).items() if k not in ('rel_tp','rel_sl')}; card+=["",f"- Orizonturi secundare (0,25 SOL, VAL+CONF): 5M {m.get('horizon_5M')}; 30M {m.get('horizon_30M')}",f"- Calibrare in regiunea tranzactionata (VAL+CONF, 0,25): {m.get('traded_region_calibration')}",f"- Baseline STATE_HEADROOM (M0) cu aceeasi politica (VAL+CONF, 0,25): {m.get('baseline_M0_same_policy')}",f"- Metrici pe toate randurile VAL+CONF (0,25): {arm}",
 "",f"## Porti PAPER_CANDIDATE (regula 28)","| poarta | rezultat |","|---|---|"]+FUNNEL_+[f"| {k} | {v if isinstance(v,str) else ('PASS' if v else 'FAIL')} |" for k,v in g.items()]+["",f"**FINAL_VERDICT = {R['FINAL_VERDICT']}**; READY_FOR_REAL_MONEY = NO; LIVE_TRADING_ENABLED = NO.","",
 "## Limitari","- VAL/CONF nu sunt sealed (post-hoc); un singur regim de 2 zile; 09-01 lipseste local; costul de retea este o presupunere; taxa curbei mostenita din V1; overlay static (fara reactia altor participanti la propria pozitie); latenta +3 sloturi presupusa; VQ implicit din evenimente; probabilitatile pentru 0,50/1,00 SOL vin din modele separate (fara extrapolare).",
 f"- Automatizare: replay-only; AUTOMATION_REPLAY_AGREEMENT = {RC.get('AUTOMATION_REPLAY_AGREEMENT')} (eligibile batch {RC.get('batch_eligible',RC.get('batch_candidates'))} vs replay {RC.get('replay_eligible',RC.get('replay_candidates'))}); PAPER_CANDIDATE emise in replay = {RC.get('replay_paper_candidates','n/a')} (politica dezactivata in artefact: policy_enabled=false, final_verdict=NO_VERIFIED_EDGE)."]
open(f"{OUT}/model_card.md","w").write("\n".join(card))
v,c_,a_=EV["VAL"][N]["base"],EV["CONF"][N]["base"],EV["VAL+CONF"][N]["base"]
summ=dict(FINAL_VERDICT=R["FINAL_VERDICT"],MODEL_SELECTED=sel[1],FEATURE_BLOCK_SELECTED=sel[0],POLICY_SELECTED=pol,TOP_REGION_CALIBRATION=m.get("traded_region_calibration"),N_VAL=v.get("usable",0),N_CONF=c_.get("usable",0),TP_FIRST_RATE=a_.get("TP_FIRST_rate"),SL_FIRST_RATE=a_.get("SL_FIRST_rate"),EV_025_SOL=a_.get("EV"),PF_025_SOL=a_.get("PF"),CI95_025_SOL=a_.get("CI95"),EX_BEST_1PCT_EV=a_.get("EX_BEST_1PCT"),STRESS_5_SLOT_EV=EV["VAL+CONF"][N]["stress_land5"].get("EV"),STRESS_COST125_EV=EV["VAL+CONF"][N]["stress_cost125"].get("EV"),EV_050_SOL=EV["VAL+CONF"]["0.5"]["base"].get("EV"),EV_100_SOL=EV["VAL+CONF"]["1.0"]["base"].get("EV"),LABEL_AGREEMENT=LC["LABEL_AGREEMENT"],AUTOMATION_REPLAY_AGREEMENT=RC.get("AUTOMATION_REPLAY_AGREEMENT"),model_hash=R["model_hash"],gates=g)
json.dump(summ,open(f"{OUT}/final_summary.json","w"),indent=1,default=float)
lines=[f"CURVE2X_V2 | {R['FINAL_VERDICT']} | model {sel[0]}/{sel[1]} | policy {pol} | model_hash {R['model_hash'][:16]}..",f"VAL   0.25 SOL: mints {v.get('usable',0)} TP {f(v.get('TP_FIRST_rate'),3)} SL {f(v.get('SL_FIRST_rate'),3)} EV {f(v.get('EV'))} PF {f(v.get('PF'),2)} CI95 {v.get('CI95')}",f"CONF  0.25 SOL: mints {c_.get('usable',0)} TP {f(c_.get('TP_FIRST_rate'),3)} SL {f(c_.get('SL_FIRST_rate'),3)} EV {f(c_.get('EV'))} PF {f(c_.get('PF'),2)} CI95 {c_.get('CI95')}",f"TOTAL 0.25 SOL: mints {a_.get('usable',0)} EV {f(a_.get('EV'))} PF {f(a_.get('PF'),2)} CI95 {a_.get('CI95')} EXB1 {f(a_.get('EX_BEST_1PCT'))} stress+5 {f(summ['STRESS_5_SLOT_EV'])} cost+25% {f(summ['STRESS_COST125_EV'])}",f"0.50 SOL EV {f(summ['EV_050_SOL'])} | 1.00 SOL EV {f(summ['EV_100_SOL'])}","GATES: "+", ".join(f"{k}={x if isinstance(x,str) else ('PASS' if x else 'FAIL')}" for k,x in g.items())]
sd=m.get("signals_detail") or []
for s in sd[:40]: lines.append(f"SIGNAL | MINT={s['mint_id']} | LANDMARK={s['landmark']}% | DAY={s['day']} | P_TP_FIRST={s['p_tp']:.3f} | P_SL_FIRST={s['p_sl']:.3f} | P_TIMEOUT={s['p_to']:.3f} | P_TP_FIRST_LCB90={s['p_tp_lcb']:.3f} | EXPECTED_NET={s['ev']:+.4f} | EXPECTED_NET_LCB90={s['ev_lcb']:+.4f} | N_SIMILAR_OOS={s['n_similar']} | OUTCOME={s['state']} ({s['label_kind']}, {s['venue']}) | PNL={s['pnl']:+.4f} | ACTION={'PAPER_CANDIDATE' if R['FINAL_VERDICT']=='PAPER_CANDIDATE' else 'WATCH'}")
open(f"{OUT}/terminal_summary.txt","w").write("\n".join(lines)+"\n"); print("\n".join(lines[:6]))
