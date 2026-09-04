"""EXTERNAL DEEP-ANALYSIS PACKAGE — research/external_review_bundle/. Fara secrete, fara adrese brute (SHA-256 cu namespace external-review-v1), fara benzi brute.
Surse: cache-uri derivate (regime_pools, m_pools, m_features), rezultatele regimului, trialurile master, testele de scurgere. Recalculeaza outcome-urile per pool x orizont pentru 4 politici + stres."""
import gzip,json,csv,os,sys,hashlib,bisect,collections,statistics as S,shutil,time,datetime,tarfile
SCR="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad"; D=f"{SCR}/derived"; B="research/external_review_bundle"; NS="external-review-v1"
sys.path.insert(0,"research"); import regime_gate as RG
SOL_USD=100.0; PRIO=0.01; HORIZONS=[5,10,20,30]; POLICIES={"TP100_SL30_300":(2.0,0.70,300),"TP50_SL20_300":(1.5,0.80,300),"FIX60":(None,None,60),"FIX180":(None,None,180)}
def hid(addr): return hashlib.sha256(f"{NS}:{addr}".encode()).hexdigest()[:32] if addr else ""
def sim(x,X,tp_m,sl_m,to,N=25.0,s=1.0,optimistic=False,lat_label=None):
    vq=x["vq"]; ev=x["ev"]; rb,rq,lp,pr,cc,i=RG.state_at(x,X,optimistic); q=int(N/SOL_USD*1e9); tok,qn=RG.exec_buy(rb,rq,vq,q,lp,pr,cc,s)
    if tok<=0: return None
    entry_slot=ev[i][2] if i>=0 else ev[0][2]; TP=N*tp_m if tp_m else None; SL=N*sl_m if sl_m else None; deadline=X+to; out=None; mfe=-N; mae=N; t_mfe=t_mae=None; t_tp=t_sl=None; amb=0
    def liq(e): rb2=e[8]-tok; rq2=e[9]+qn; return ((RG.exec_sell(rb2,rq2,vq,tok,e[12],e[13],e[14],s)/1e9*SOL_USD) if rb2>0 else 0.0),rb2,rq2
    j=i+1
    while j<len(ev) and ev[j][1]<=deadline:
        if optimistic: k=j
        else:
            sl_=ev[j][2]; k=j
            while k+1<len(ev) and ev[k+1][2]==sl_ and ev[k+1][1]<=deadline: k+=1
        V,rb2,rq2=liq(ev[k]); rel=ev[k][1]-X
        if V-N>mfe: mfe=V-N; t_mfe=rel
        if V-N<mae: mae=V-N; t_mae=rel
        hitTP=TP is not None and V>=TP; hitSL=SL is not None and V<=SL
        if hitTP and t_tp is None: t_tp=rel
        if hitSL and t_sl is None: t_sl=rel
        if hitTP and hitSL: amb=1
        if out is None:
            if optimistic and hitTP: out=("TP",V,ev[k][1],ev[k][2],rb2,rq2)
            elif hitSL: out=("SL",V,ev[k][1],ev[k][2],rb2,rq2)
            elif hitTP: out=("TP",V,ev[k][1],ev[k][2],rb2,rq2)
        if out is not None and (t_tp is not None or TP is None) and (t_sl is not None or SL is None): break
        j=k+1
    if out is None:
        rb3,rq3,lp3,pr3,cc3,i3=RG.state_at(x,deadline,optimistic); rb2=(rb3 if i3>=0 else rb)-tok; rq2=(rq3 if i3>=0 else rq)+qn
        V=(RG.exec_sell(rb2,rq2,vq,tok,lp3,pr3,cc3,s)/1e9*SOL_USD) if rb2>0 else 0.0; out=("TIMEOUT",V,deadline,None,rb2,rq2)
        if V-N>mfe: mfe=V-N; t_mfe=to
        if V-N<mae: mae=V-N; t_mae=to
    pnl=out[1]-N-2*PRIO
    return dict(entry_ts=X,entry_slot=entry_slot,entry_qty_tokens=tok,entry_quote_in_lamports=qn,entry_cost_usd=N,entry_rb=rb,entry_rq=rq,entry_fee_bps=lp+pr+cc,exit_type=out[0],first_barrier=("TP" if (t_tp is not None and (t_sl is None or t_tp<t_sl)) else ("SL" if t_sl is not None else "NONE")),exit_ts=out[2],exit_slot=out[3],exit_rb=out[4],exit_rq=out[5],exact_liquidation_usd=out[1],pnl_usd=pnl,ret=pnl/N,mfe_usd=mfe,mae_usd=mae,t_mfe_s=t_mfe,t_mae_s=t_mae,t_tp_s=t_tp,t_sl_s=t_sl,same_slot_tp_sl_ambiguity=amb,hold_s=out[2]-X)
def wcsv(path,rows,cols,gz=True):
    f=gzip.open(path,"wt",newline="") if gz else open(path,"w",newline=""); w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader()
    for r in rows: w.writerow({k:("" if r.get(k) is None else r.get(k)) for k in cols})
    f.close()
def main():
    os.makedirs(f"{B}/code",exist_ok=True); t0=time.time()
    pools=[]; 
    with gzip.open(f"{D}/regime_pools.jsonl.gz","rt") as f:
        for l in f: x=json.loads(l); x["_ts"]=[e[1] for e in x["ev"]]; pools.append(x)
    byid={x["mint"]:x for x in pools}; R=json.load(open("research/regime_gate_results.json"))
    with gzip.open(f"{D}/regime_shadow.jsonl.gz","rt") as f:
        for l in f: r=json.loads(l); byid[r["mint"]]["sh"]=r["sh"]
    for x in pools: x.setdefault("sh",None); blocks=json.load(open(f"{D}/regime_blocks.json")); trades=json.load(open(f"{D}/regime_trades.json"))
    excl=json.load(open(f"{D}/regime_excluded_pools.json")) if os.path.exists(f"{D}/regime_excluded_pools.json") else []
    feats={}; 
    with gzip.open(f"{D}/m_features.jsonl.gz","rt") as f:
        for l in f: r=json.loads(l); feats[(r["mint"],r["h"])]=r
    curve_hold={}
    with gzip.open(f"{D}/m_pools.jsonl.gz","rt") as f:
        for l in f:
            x=json.loads(l); bal=collections.Counter()
            for tr in x["curve"]: bal[tr[6]]+= tr[4] if tr[5] else -tr[4]
            curve_hold[x["mint"]]={u for u,b in bal.items() if b>0}
    # ---------- C. pool_master ----------
    pm=[]
    for x in pools:
        ev=x["ev"]; ok_chain=sum(1 for a,b in zip(ev,ev[1:]) if a[8]==b[6] and a[9]==b[7]); pairs=max(1,len(ev)-1)
        pm.append(dict(pool_id=hid(x["pool"]),mint_id=hid(x["mint"]),source=x["source"],date_utc=x["day"],hour_utc=datetime.datetime.utcfromtimestamp(x["complete_ts"]).strftime("%Y-%m-%d %H:00"),complete_ts=x["complete_ts"],complete_slot=x["complete_slot"],pool_creation_ts=x["T0_ts"],pool_creation_slot=x["T0_slot"],eligible=1,exclusion_reason="",schema_variant=("HIST24_VAULT_BALANCES_TXINDEX" if x["source"].startswith("SEP01") else "PROSPECTIVE_EVENTS_NO_TXINDEX"),boost_classification="BOOST_PROXY_17_58",vq_lamports=x["vq"],ordering_quality=x["ordering"],fee_mode=x["fee_mode"],coverage_s_after_creation=(ev[-1][1]-x["T0_ts"]) if ev else 0,gap_flag=0,corruption_flag=0,first_executable_ts=x["complete_ts"]+7,initial_rb=ev[0][6],initial_rq=ev[0][7],n_events_420s=len(ev),n_buys=sum(1 for e in ev if e[5]==1),n_sells=sum(1 for e in ev if e[5]==0),reserve_chain_consistency=round(ok_chain/pairs,4),has_curve_features=int((x["mint"],5) in feats),has_wallets=int(x["fee_mode"]=="OBSERVED_EVENT_BPS")))
    for r in excl:
        pm.append(dict(pool_id=(hid(r["pool"]) if r["pool"] else hid("NOPOOL:"+r["mint"])),mint_id=hid(r["mint"]),source="PROSPECTIVE_TAPE_EVENTS",date_utc=datetime.datetime.utcfromtimestamp(r["complete_ts"]).strftime("%Y-%m-%d"),hour_utc=datetime.datetime.utcfromtimestamp(r["complete_ts"]).strftime("%Y-%m-%d %H:00"),complete_ts=r["complete_ts"],complete_slot=r["complete_slot"],pool_creation_ts=r["T0_ts"],eligible=0,exclusion_reason=r["reason"],schema_variant="PROSPECTIVE_EVENTS_NO_TXINDEX",boost_classification=("NON_BOOST_OR_UNKNOWN" if r["reason"] in ("NOT_BOOST_PROXY_INITIAL_STATE","NO_EVENTS_OR_VQ_UNVERIFIABLE_OR_FIRST_STATE_NOT_BOOST") else ""),gap_flag=int(r["reason"]=="OUTAGE_IN_REQUIRED_INTERVAL"),corruption_flag=int(r["reason"]=="UNREADABLE_SEGMENT_IN_REQUIRED_INTERVAL"),initial_rq=r.get("pool_quote_initial")))
    PM_COLS=["pool_id","mint_id","source","date_utc","hour_utc","complete_ts","complete_slot","pool_creation_ts","pool_creation_slot","eligible","exclusion_reason","schema_variant","boost_classification","vq_lamports","ordering_quality","fee_mode","coverage_s_after_creation","gap_flag","corruption_flag","first_executable_ts","initial_rb","initial_rq","n_events_420s","n_buys","n_sells","reserve_chain_consistency","has_curve_features","has_wallets"]
    wcsv(f"{B}/pool_master.csv.gz",pm,PM_COLS)
    # ---------- D/E. feature panel + outcomes ----------
    FEAT_COLS=["pool_id","mint_id","horizon_s","decision_ts","feature_max_ts","pool_creation_ts","complete_ts","actual_entry_ts","actual_entry_slot","partition_master","features_available","missingness_reason","manipulation_flag_burst","ordering_quality_flag"]+RG_FEATS if False else None
    fnames=json.load(open("research/master_feature_registry.json"))
    ALLF=["t0h_sell_share","t0h_sold_frac","t0h_sellers_n","fresh_buyers_n","fresh_buy_quote","fresh_share","ret_buy_share","ret_buyers_n","buy_ratio","net_quote_flow","last5_buy_share","sign_runs","size_median_sol","size_top1_share","repeat_size_share","max_wallets_per_slot","burst_event_share","px_ret_bp","impact_per_sol","absorption","max_dd_bp","recovery_bp","rq_change_sol","n_events","events_per_s","creator_t0_share","creator_sold_pre_D","creator_sold_on_curve","curve_duration_s","curve_trades_n","curve_unique_buyers"]
    FEAT_COLS=["pool_id","mint_id","horizon_s","decision_ts","feature_max_ts","pool_creation_ts","complete_ts","actual_entry_ts","actual_entry_slot","partition_master","features_available","missingness_reason","n_missing_features","manipulation_flag_burst","ordering_quality_flag"]+["f_"+k for k in ALLF]
    frows=[]; orows=[]
    for x in pools:
        for h in HORIZONS:
            Dts=x["T0_ts"]+h; X=Dts+2; fr=feats.get((x["mint"],h)); base=dict(pool_id=hid(x["pool"]),mint_id=hid(x["mint"]),horizon_s=h,decision_ts=Dts,pool_creation_ts=x["T0_ts"],complete_ts=x["complete_ts"],ordering_quality_flag=x["ordering"])
            prim=sim(x,X,2.0,0.70,300); base["actual_entry_ts"]=X; base["actual_entry_slot"]=prim["entry_slot"] if prim else None
            if fr:
                f=fr["f"]; miss=sum(1 for k in ALLF if f.get(k) is None); frows.append(dict(base,feature_max_ts=f.get("max_ts_used"),partition_master=fr["part"],features_available=1,missingness_reason=("NO_EVENTS_BEFORE_DECISION" if f.get("n_events")==0 else ""),n_missing_features=miss,manipulation_flag_burst=int((f.get("burst_event_share") or 0)>=0.5),**{"f_"+k:f.get(k) for k in ALLF}))
            else: frows.append(dict(base,feature_max_ts=None,partition_master="",features_available=0,missingness_reason=("SEP01_NO_WALLET_IDENTITY_IN_POOL_TAPE" if x["source"].startswith("SEP01") else "NO_CREATE_EVENT_IN_TAPE_OR_EXCLUDED_FROM_MASTER_POPULATION"),n_missing_features=len(ALLF),manipulation_flag_burst=None))
            o=dict(pool_id=hid(x["pool"]),mint_id=hid(x["mint"]),horizon_s=h,decision_ts=Dts,outcome_entry_ts=X)
            for pname,(tp,sl,to) in POLICIES.items():
                r=sim(x,X,tp,sl,to)
                if r:
                    for k,v in r.items(): o[f"OUT_{pname}_{k}"]=v
                if pname=="TP100_SL30_300":
                    for lab,kw in (("cost125",dict(s=1.25)),("cost150",dict(s=1.5)),("optimistic",dict(optimistic=True))):
                        rr=sim(x,X,tp,sl,to,**kw); o[f"OUT_{pname}_{lab}_pnl_usd"]=rr["pnl_usd"] if rr else None; o[f"OUT_{pname}_{lab}_exit_type"]=rr["exit_type"] if rr else None
                    for lat in (0.8,1.2,5.0):
                        rr=sim(x,Dts+lat,tp,sl,to); o[f"OUT_{pname}_lat{lat}_pnl_usd"]=rr["pnl_usd"] if rr else None
            orows.append(o)
    OUT_COLS=sorted({k for o in orows for k in o},key=lambda k:(k not in ("pool_id","mint_id","horizon_s","decision_ts","outcome_entry_ts"),k))
    wcsv(f"{B}/pool_feature_panel.csv.gz",frows,FEAT_COLS); wcsv(f"{B}/pool_outcomes.csv.gz",orows,OUT_COLS)
    # ---------- F. shadow ledger ----------
    sh=[]
    with gzip.open(f"{D}/regime_shadow.jsonl.gz","rt") as f:
        for l in f:
            r=json.loads(l); s=r["sh"]; sh.append(dict(pool_id=hid(r["pool"]),mint_id=hid(r["mint"]),date_utc=r["day"],source=r["source"],fee_mode=r["fee_mode"],ordering_quality=r["ordering"],complete_ts=r["complete_ts"],complete_slot=r["complete_slot"],eligibility_ts=r["complete_ts"]+7,shadow_entry_ts=s["entry_ts"],shadow_entry_slot=s["entry_slot"],notional_usd=25,entry_qty_tokens=s["tok"],entry_quote_in_lamports=s["q_in_lamports"],entry_rb=s["entry_rb"],entry_rq=s["entry_rq"],exit_kind=s["exit_kind"],exit_value_usd=s["exit_value"],exit_ts=s["exit_ts"],SHADOW_RESOLUTION_TIME=s["resolution_ts"],pnl_usd=s["pnl"],hold_s=s["hold_s"],mfe_usd=s["mfe"],mae_usd=s["mae"],pnl_optimistic_usd=(r["sh_opt"] or {}).get("pnl"),pnl_cost125_usd=(r["sh_c125"] or {}).get("pnl"),pnl_cost150_usd=(r["sh_c150"] or {}).get("pnl"),pnl_latency_plus5_usd=(r["sh_lat5"] or {}).get("pnl")))
    SH_COLS=list(sh[0].keys()); wcsv(f"{B}/shadow_trade_ledger.csv.gz",sh,SH_COLS)
    # ---------- G. regime blocks ----------
    br=[]
    for b in blocks:
        g=b["gate"]; br.append(dict(block_start_utc=b["B_utc"],decision_ts=b["B"],date_utc=b["day"],n_window_entries=b["n_window_entries"],n_unresolved_excluded=b["n_unresolved"],gate_N=g.get("N"),gate_trimmed_mean=g.get("trimmed_mean"),gate_PF=g.get("PF"),gate_median=g.get("median"),gate_ex_best_1_EV=g.get("ex_best_1_EV"),gate_EV_first30=g.get("EV_first30"),gate_EV_second30=g.get("EV_second30"),REGIME_ON=int(b["ON"]),migrations_available_in_block=b["n_migrations_in_block"],selected_pool_id=hid(byid[b["selected_mint"]]["pool"]) if b.get("selected_mint") else "",skip_reason=b.get("skip_reason") or "",no_future_fields_in_decision="YES",OUTCOME_strategy_pnl_usd=b.get("strategy_pnl"),OUTCOME_strategy_exit_kind=b.get("strategy_exit_kind") or ""))
    wcsv(f"{B}/regime_blocks.csv",br,list(br[0].keys()),gz=False)
    # ---------- H. executed trades ----------
    et=[]
    for t in trades["ON"]:
        x=byid[t["mint"]]; et.append(dict(block_start_utc=datetime.datetime.utcfromtimestamp(t["block"]).strftime("%Y-%m-%d %H:%M"),block_decision_ts=t["block"],pool_id=hid(x["pool"]),mint_id=hid(x["mint"]),regime_decision="ON",complete_ts=x["complete_ts"],eligibility_ts=x["complete_ts"]+7,entry_ts=t["entry_ts"],entry_slot=t["entry_slot"],exit_ts=t["exit_ts"],exit_kind=t["exit_kind"],exit_value_usd=t["exit_value"],pnl_usd_25=t["pnl"],latency_s=2,observation_s=5,fee_bps_entry=None,ordering="CONSERVATIVE",eligible_boost=1,eligible_coverage=1,eligible_no_gap=1,**{f"bankroll_{Bk}_{k}":v for Bk in (100,500,2000) for k,v in (lambda L:(("notional",L["notional"]),("pnl",L["pnl"]),("before",L["bankroll_before"]),("after",L["bankroll_after"]),("drawdown",L["drawdown"])) if L else (("notional",None),("pnl",None),("before",None),("after",None),("drawdown",None)))(next((l for l in R["bankroll"][str(Bk)]["ledger"] if l["block"]==t["block"]),None))}))
    if et: wcsv(f"{B}/regime_executed_trades.csv",et,list(et[0].keys()),gz=False)
    else: open(f"{B}/regime_executed_trades.csv","w").write("block_start_utc,pool_id,note\n,,NO_ON_TRADES\n")
    # ---------- I. hourly/daily summary ----------
    on_hours={int(b["B"]//3600) for b in blocks if b["ON"]}; hs=[]
    for key,grp in sorted(collections.groupby(sorted(sh,key=lambda r:int(r["shadow_entry_ts"]//3600)),key=lambda r:int(r["shadow_entry_ts"]//3600))) if False else []: pass
    byhour=collections.defaultdict(list); [byhour[int(r["shadow_entry_ts"]//3600)].append(r) for r in sh]
    for hk,rs in sorted(byhour.items()):
        pn=[r["pnl_usd"] for r in rs]; w=[a for a in pn if a>0]; l=[a for a in pn if a<=0]
        hs.append(dict(level="HOUR",utc=datetime.datetime.utcfromtimestamp(hk*3600).strftime("%Y-%m-%d %H:00"),date_utc=datetime.datetime.utcfromtimestamp(hk*3600).strftime("%Y-%m-%d"),regime_state=("ON" if hk in on_hours else "OFF"),coverage=("PARTIAL" if len(rs)<5 else "FULL"),n_shadow=len(pn),EV_usd=S.mean(pn),median_usd=S.median(pn),PF=(sum(w)/abs(sum(l))) if l and sum(l)<0 else None,P_gt0=len(w)/len(pn)))
    byday=collections.defaultdict(list); [byday[r["date_utc"]].append(r) for r in sh]
    for d,rs in sorted(byday.items()):
        pn=[r["pnl_usd"] for r in rs]; w=[a for a in pn if a>0]; l=[a for a in pn if a<=0]
        hs.append(dict(level="DAY",utc=d,date_utc=d,regime_state=f"ON_blocks={sum(1 for b in blocks if b['ON'] and b['day']==d)}",coverage=("FULL" if d=="2026-09-03" or d=="2026-09-01" else "PARTIAL"),n_shadow=len(pn),EV_usd=S.mean(pn),median_usd=S.median(pn),PF=(sum(w)/abs(sum(l))) if l and sum(l)<0 else None,P_gt0=len(w)/len(pn)))
    wcsv(f"{B}/hourly_daily_summary.csv",hs,list(hs[0].keys()),gz=False)
    # ---------- J. trials ----------
    shutil.copy("research/master_edge_trials.csv",f"{B}/model_and_rule_trials.csv")
    # ---------- L. casebook ----------
    def path_of(x,maxn=400):
        vq=x["vq"]; hold=curve_hold.get(x["mint"]); s=x["sh"]; tok,qn=(s["tok"],s["q_in_lamports"]) if s else (0,0); out=[]
        for e in x["ev"][:maxn]:
            rb2=e[8]-tok; rq2=e[9]+qn; V=(RG.exec_sell(rb2,rq2,vq,tok,e[12],e[13],e[14])/1e9*SOL_USD) if (tok and rb2>0) else None
            u=e[15]; coh=("UNKNOWN_NO_WALLET" if u is None else ("UNKNOWN_NO_CURVE" if hold is None else ("T0_HOLDER" if u in hold else "FRESH")))
            out.append(dict(rel_ts=e[1]-x["complete_ts"],slot=e[2],side=("BUY" if e[5]==1 else ("SELL" if e[5]==0 else "LP_OR_OTHER")),quote_lamports=e[11],token_amount=e[10],rb_post=e[8],rq_post=e[9],exec_liquidation_usd_25=V,wallet_id=hid(u) if u else "",cohort_at_time=coh))
        return out
    cases=[]; seen=set()
    def add(x,cat):
        if x["mint"] in seen: return
        seen.add(x["mint"]); cases.append(dict(case_type=cat,pool_id=hid(x["pool"]),mint_id=hid(x["mint"]),date_utc=x["day"],source=x["source"],complete_ts=x["complete_ts"],shadow=x["sh"],path=path_of(x)))
    for t in trades["ON"]: add(byid[t["mint"]],"REGIME_EXECUTED_TRADE")
    on_blocks={b["B"] for b in blocks if b["ON"]}; onsel={t["mint"] for t in trades["ON"]}
    n=0
    for x in sorted(pools,key=lambda x:x["complete_ts"]):
        if int((x["complete_ts"]+7)//900*900) in on_blocks and x["mint"] not in onsel and x["sh"]: add(x,"ON_BLOCK_NOT_TRADED_OVERLAP"); n+=1
        if n>=20: break
    n=0
    for x in sorted(pools,key=lambda x:x["complete_ts"]):
        if int((x["complete_ts"]+7)//900*900) not in on_blocks and x["sh"]: add(x,"EARLIEST_OFF_POOL"); n+=1
        if n>=20: break
    withsh=[x for x in pools if x["sh"]]
    for x in sorted(withsh,key=lambda x:-x["sh"]["pnl"])[:20]: add(x,"HIGHEST_PNL")
    for x in sorted(withsh,key=lambda x:x["sh"]["pnl"])[:20]: add(x,"LOWEST_PNL")
    for x in sorted(withsh,key=lambda x:abs(x["sh"]["pnl"]))[:20]: add(x,"NEAREST_ZERO")
    onp=[x for x in withsh if int((x["complete_ts"]+7)//900*900) in on_blocks]; offp=[x for x in withsh if int((x["complete_ts"]+7)//900*900) not in on_blocks]
    for x in onp[:20]:
        y=min(offp,key=lambda y:(abs(y["ev"][0][7]-x["ev"][0][7])/1e9+abs(y["complete_ts"]-x["complete_ts"])/3600)) if offp else None
        add(x,"MATCHED_PAIR_ON"); 
        if y: add(y,"MATCHED_PAIR_OFF")
    with gzip.open(f"{B}/casebook.jsonl.gz","wt") as f:
        for c in cases: f.write(json.dumps(c,default=str)+"\n")
    # ---------- headline + integrity ----------
    head=dict(FINAL_VERDICT=R["FINAL_VERDICT"],N_eligible=R["N_eligible"],N_blocks=R["N_blocks"],N_ON_blocks=R["N_ON_blocks"],ON_trades=R["ON"]["trades"],ON_EV=(R["ON"]["stats"] or {}).get("EV"),OFF_EV=(R["OFF_A"]["stats"] or {}).get("EV"),EVERY_EV=(R["EVERY_B"]["stats"] or {}).get("EV"),UNCOND_EV=R["UNCOND_F"]["stats"]["EV"],UNCOND_N=R["UNCOND_F"]["stats"]["N"],bankroll_100_end=R["bankroll"]["100"]["end"])
    json.dump(head,open(f"{B}/headline_metrics.json","w"),indent=1)
    integ=dict(rows=dict(pool_master=len(pm),pool_master_eligible=sum(1 for r in pm if r["eligible"]==1),pool_master_excluded=sum(1 for r in pm if r["eligible"]==0),feature_panel=len(frows),outcomes=len(orows),shadow_ledger=len(sh),regime_blocks=len(br),executed_trades=len(et),casebook=len(cases)),unique_pools=dict(master=len({r["pool_id"] for r in pm}),features=len({r["pool_id"] for r in frows}),outcomes=len({r["pool_id"] for r in orows}),shadow=len({r["pool_id"] for r in sh})),
        duplicates=dict(master=len(pm)-len({(r["pool_id"]) for r in pm}),feature_panel=len(frows)-len({(r["pool_id"],r["horizon_s"]) for r in frows}),outcomes=len(orows)-len({(r["pool_id"],r["horizon_s"]) for r in orows})),missingness=dict(feature_rows_without_features=sum(1 for r in frows if r["features_available"]==0),reasons=dict(collections.Counter(r["missingness_reason"] for r in frows if r["features_available"]==0))),
        timestamp_violations=dict(feature_after_decision=sum(1 for r in frows if r["feature_max_ts"] not in (None,"") and r["feature_max_ts"]>=r["decision_ts"]),outcome_before_entry=sum(1 for o in orows if o.get("OUT_TP100_SL30_300_exit_ts") is not None and o["OUT_TP100_SL30_300_exit_ts"]<o["outcome_entry_ts"]),shadow_resolution_before_entry=sum(1 for r in sh if r["SHADOW_RESOLUTION_TIME"]<r["shadow_entry_ts"])),
        join_checks=dict(features_pools_in_master=all(r["pool_id"] in {p["pool_id"] for p in pm} for r in frows),outcomes_pools_in_master=all(r["pool_id"] in {p["pool_id"] for p in pm} for r in orows),shadow_pools_in_master=all(r["pool_id"] in {p["pool_id"] for p in pm} for r in sh)),
        reserve_consistency=dict(mean_chain_consistency=S.mean([r["reserve_chain_consistency"] for r in pm if r["eligible"]==1]),pools_below_0_99=sum(1 for r in pm if r["eligible"]==1 and r["reserve_chain_consistency"]<0.99)),corrupt_segment_exclusions=dict(collections.Counter(r["exclusion_reason"] for r in pm if r["eligible"]==0)),
        source_hashes=dict(regime_cache=json.load(open(f"{D}/regime_cache_manifest.json")),m_cache=json.load(open(f"{D}/m_cache_manifest.json"))),leakage_tests=json.load(open("research/master_leakage_tests.json")),row_count_explanation="pool_master = eligibile + excluse (cu motiv); feature_panel/outcomes = eligibile x 4 orizonturi; trasaturile exista doar pentru pool-urile din populatia master (946: cu CreateEvent in banda si portofele); SEP01 nu are portofele in pool tapes => fara trasaturi de cohorta; shadow_ledger = eligibile cu shadow executabil")
    json.dump(integ,open(f"{B}/integrity_checks.json","w"),indent=1,default=str)
    for src in ("research/regime_gate.py","research/regime_cache_build.py","research/regime_exclusions_pass.py","research/master_edge_build_m_cache.py","research/master_edge_discovery.py","research/master_leakage_tests.py","research/build_external_bundle.py","research/regime_gate_frozen_spec.json","research/regime_gate_results.json","research/master_feature_registry.json","pumpswap_fees.py"): shutil.copy(src,f"{B}/code/{os.path.basename(src)}")
    print("bundle rows",integ["rows"],"runtime",round(time.time()-t0,1),flush=True); print("BUNDLE_DONE")
if __name__=="__main__": main()
