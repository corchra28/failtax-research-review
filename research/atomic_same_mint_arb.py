"""ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE — executor. Etape: (1) perechi duplicate din inventar (pass 1); (2) pass 2: evenimentele pool-urilor din perechi (cache);
(3) fezabilitate FARA PnL + FEASIBILITY_GATE; (4) spec inghetata + hash-uri; (5) motor atomic exact, decizie/landing fara lookahead, costuri, metrici, poarta finala.
Ruleaza: python research/atomic_same_mint_arb.py stage  (stage in: pass2 | feasibility | freeze | run)."""
import gzip,json,base64,struct,os,glob,collections,sys,time,zlib,hashlib,bisect,math,random,statistics as S,datetime,csv
sys.path.insert(0,'strategy_e'); import pda; from pda import b58e
sys.path.insert(0,'.'); import pumpswap_fees as PF
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; TAPE="strategy_m/data/tape"; WSOL="So11111111111111111111111111111111111111112"   # SUPPLY hardcodat eliminat: supply validat per mint sau tier demonstrat din evenimente
INV=f"{D}/pamm_pool_inventory.json.gz"; CACHE2=f"{D}/arb_pair_events.jsonl.gz"; SPEC="research/atomic_same_mint_arb_frozen_spec.json"; DERIV="research/atomic_same_mint_arb_derivation.json"; RPC_PAIRS=f"{D}/same_mint_pairs_rpc.json"; RPC_META="research/pool_metadata_normalized.jsonl.gz"
PUMP="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"; PAMM="pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"; TOKEN_PROGRAM_MAP_PATH="research/token_program_map.json"   # {mint: owner_program}; inexistent => necunoscut
SPL_TOKEN="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"; TOKEN_2022="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
def load_token_program_map():
    return json.load(open(TOKEN_PROGRAM_MAP_PATH)) if os.path.exists(TOKEN_PROGRAM_MAP_PATH) else {}
def pair_allowed_for_pnl(token_mint,token_program_map):
    """(allowed, reason): doar mint-uri cu program CUNOSCUT si egal cu SPL Token clasic intra in motorul de PnL. Fara presupuneri din sufix/creator."""
    prog=token_program_map.get(token_mint)
    if prog is None: return False,"TOKEN_PROGRAM_UNKNOWN"
    if prog==SPL_TOKEN: return True,"SPL_TOKEN"
    if prog==TOKEN_2022: return False,"TOKEN_2022_EXCLUDED"
    return False,"TOKEN_PROGRAM_UNSUPPORTED"
def pump_pool_authority(token_mint): return pda.find_pda([b"pool-authority",pda.b58d(token_mint)],pda.b58d(PUMP))[0]
def canonical_pool_address(token_mint):
    """PDA PumpSwap: ["pool", u16_le(0), creator(=pool-authority pump), base_mint(token), quote_mint(WSOL)]."""
    creator=pump_pool_authority(token_mint); return pda.find_pda([b"pool",struct.pack("<H",0),pda.b58d(creator),pda.b58d(token_mint),pda.b58d(WSOL)],pda.b58d(PAMM))[0],creator
def episode_first_flags(pred_nets):
    """(blocant 8) pentru o secventa cronologica de predicted_net ale unei (perechi, directii, notional): 1 doar la prima stare pozitiva a fiecarui episod; episodul se inchide cand predicted <= 0."""
    flags=[]; open_=False
    for v in pred_nets:
        if v is None or v<=0: flags.append(0); open_=False
        else: flags.append(0 if open_ else 1); open_=True
    return flags
def final_gate(A,BN,viol,spec,token_program_observable):
    """(blocant 9) toate criteriile portii din spec, calculate explicit; no_post_hoc = constantele motorului identice cu spec-ul."""
    rb_=A["realized_net_base"]; segs=[k for k in ("CANONICAL+NONCANONICAL","NONCANONICAL+NONCANONICAL") if BN.get(k) and BN[k]["realized_net_base"]]
    VK=("INVARIANT_VIOLATION_PREDICTED","INVARIANT_VIOLATION_LANDING","FEE_RESOLVER_NONE","TIMING_LANDING_BEFORE_DECISION","CHAIN_BREAK_DECISION_TO_LANDING","STATE_IN_OUTAGE_OR_TRUNCATION","PAIR_COMBO_EXCLUDED_NO_EVENTS_OR_VQ","PAIR_EXCLUDED_TOKEN_PROGRAM","ORIENTATION_VIOLATION")
    fg=spec["final_gate"]
    return dict(N50=rb_["N"]>=fg["N_realized_min"],days2=A["positive_days"]>=fg["positive_days_min"],EV=rb_["EV"]>0,median=rb_["median"]>0,PF=rb_["PF"]>=fg["PF_min"],CI_low=rb_.get("CI95_cluster_hour",(-1,0))[0]>0,exb1pct=rb_["EX_BEST_1PCT"]>0,top1=rb_["top1pct_contrib"]<=fg["top1pct_max"],day_share=(A["max_day_share"] if A["max_day_share"] is not None else 1)<=fg["max_day_share_max"],survival=A["survival_pred_to_realized_base"]>=fg["survival_min"],landing_s2=((A["realized_landing_s2_base"] or {}).get("EV",-1))>0,stress2=(A["realized_net_stress2"]["EV"])>0,
        zero_violations=all(viol.get(k,0)==0 for k in VK) and token_program_observable is True,segments_positive=(all(BN[k]["realized_net_base"]["EV"]>0 for k in segs) if segs else False),
        no_post_hoc=(spec["primary_notional_sol"]==PRIMARY and spec["notionals_sol"]==NOTIONALS and spec["final_gate"]["PF_min"]==1.5 and spec["final_gate"]["N_realized_min"]==50 and spec["costs"]["priority_fee_lamports"]==PRIO and spec["costs"]["jito_tip_scenarios_lamports"]==TIPS and spec["costs"]["base_signature_fee_lamports"]==SIG_FEE))
LAMP=10**9; SIG_FEE=5000; PRIO=100000; TIPS={"ZERO_TIP_DIAGNOSTIC":0,"BASE":10000,"STRESS_1":100000,"STRESS_2":1000000}; NOTIONALS=[0.01,0.05,0.10,0.25,0.50,1.00]; PRIMARY=0.25
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
def load_inv(): return json.load(gzip.open(INV,"rt"))
def pairs_from_inventory(inv):
    """PRIMAR (blocant 1): doar pool-uri cu base_mint=token si quote_mint=WSOL; pool-urile cu base=WSOL sunt excluse (orientare inversa, nenormalizata). Returneaza (dup_strict, info_unordered)."""
    P=inv["pools"]; strict=collections.defaultdict(list); unordered=collections.defaultdict(list); reversed_excluded=0
    for p,m in P.items():
        if m["quote_mint"]==WSOL and m["base_mint"]!=WSOL: strict[m["base_mint"]].append(p)
        elif m["base_mint"]==WSOL: reversed_excluded+=1
        if WSOL in (m["base_mint"],m["quote_mint"]): unordered[m["quote_mint"] if m["base_mint"]==WSOL else m["base_mint"]].append(p)
    dup={tok:sorted(set(ps)) for tok,ps in strict.items() if len(set(ps))>=2}
    info=dict(unordered_pairs_with_2plus=sum(1 for ps in unordered.values() if len(set(ps))>=2),reversed_orientation_pools_excluded=reversed_excluded)
    # perechi recuperate prin derivare zero-RPC (canonical derivat + pool index>0), doar orientare stricta
    if os.path.exists(DERIV):
        for d in json.load(open(DERIV))["pairs"]:
            if d["strict_orientation"] and d["canonical_active"]:
                ps=set(dup.get(d["token_mint"],[]))|{d["canonical_pool"],d["sibling_pool"]}; dup[d["token_mint"]]=sorted(ps)
    return dup,info
def derived_pool_meta(inv):
    """meta sintetic pentru pool-urile canonice derivate (CreatePoolEvent anterior benzii): canonical=True, base=token, quote=WSOL, index 0, marcate derived=True."""
    P=dict(inv["pools"])
    if os.path.exists(DERIV):
        for d in json.load(open(DERIV))["pairs"]:
            if d["canonical_pool"] not in P: P[d["canonical_pool"]]=dict(pool=d["canonical_pool"],index=0,creator=d["canonical_creator"],base_mint=d["token_mint"],quote_mint=WSOL,canonical=True,derived=True,ts=None,slot=None)
    return P
def stage_derive():
    """(1) DERIVARE LOCALA ZERO-RPC: pentru fiecare CreatePoolEvent cu WSOL pe o parte si index>0, deriveaza pool-ul canonical si verifica-l in setul pool-urilor active."""
    inv=load_inv(); P=inv["pools"]; active=set(inv["stats"].keys()); ok=0; bad=0
    for p,m in P.items():   # validarea derivarii pe pool-urile canonice observate in banda
        if m["canonical"]:
            addr,_=canonical_pool_address(m["base_mint"]); ok+= (addr==p); bad+= (addr!=p)
    rows=[]
    for p,m in P.items():
        if m["index"]<=0 or WSOL not in (m["base_mint"],m["quote_mint"]): continue
        tok=m["quote_mint"] if m["base_mint"]==WSOL else m["base_mint"]; addr,creator=canonical_pool_address(tok)
        rows.append(dict(sibling_pool=p,sibling_index=m["index"],sibling_creator=m["creator"],sibling_is_canonical_creator=(m["creator"]==creator),token_mint=tok,strict_orientation=(m["base_mint"]==tok and m["quote_mint"]==WSOL),canonical_creator=creator,canonical_pool=addr,canonical_in_tape_createpool=(addr in P),canonical_active=(addr in active),sibling_active=(p in active),canonical_events=(inv["stats"].get(addr,{}).get("n_buy",0)+inv["stats"].get(addr,{}).get("n_sell",0)),sibling_events=(inv["stats"].get(p,{}).get("n_buy",0)+inv["stats"].get(p,{}).get("n_sell",0))))
    allnc=[]
    for p,m in P.items():
        if m["canonical"] or WSOL not in (m["base_mint"],m["quote_mint"]): continue
        tok=m["quote_mint"] if m["base_mint"]==WSOL else m["base_mint"]; addr,creator=canonical_pool_address(tok)
        if addr in active: allnc.append(dict(noncanonical_pool=p,index=m["index"],strict_orientation=(m["base_mint"]==tok),token_mint=tok,canonical_pool=addr,canonical_active=True,noncanonical_active=(p in active)))
    out=dict(built=time.strftime("%Y-%m-%d %H:%M:%S"),all_noncanonical_sol_pools_scanned=sum(1 for m in P.values() if not m["canonical"] and WSOL in (m["base_mint"],m["quote_mint"])),all_noncanonical_with_active_derived_canonical=allnc,derivation_validation=dict(canonical_pools_in_tape=ok+bad,pda_matches=ok,pda_mismatches=bad),INDEX_GT0_SOL_POOLS=len(rows),DERIVED_CANONICAL_ADDRESSES=len({r["canonical_pool"] for r in rows}),DERIVED_CANONICAL_ACTIVE_MATCHES=sum(1 for r in rows if r["canonical_active"]),STRICT_ORIENTATION_MATCHES=sum(1 for r in rows if r["canonical_active"] and r["strict_orientation"]),REVERSED_ORIENTATION_MATCHES=sum(1 for r in rows if r["canonical_active"] and not r["strict_orientation"]),PAIRS_WITH_BOTH_EVENT_STREAMS=sum(1 for r in rows if r["canonical_active"] and r["sibling_active"]),pairs=rows)
    json.dump(out,open(DERIV,"w"),indent=1); print({k:v for k,v in out.items() if k!="pairs"}); print("DERIVE_DONE")
def readlines(fp):
    try:
        with gzip.open(fp,"rt") as f:
            for line in f: yield line
    except (EOFError,zlib.error,OSError): return
def outages():
    def lt(s): return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M:%S").timestamp()
    W=[]; o=None
    for line in open(f"{TAPE}/collector.log"):
        if len(line)<20: continue
        try: t=lt(line[:19])
        except Exception: continue
        if "DECONECTARE" in line and o is None: o=t
        if "conectat:" in line and o is not None: W.append((o,t)); o=None
    last_hb=max(lt(l[:19]) for l in open(f"{TAPE}/collector.log") if "[HB]" in l); W.append((last_hb+600,time.time())); return W
# ---------------- pass 2 ----------------
def stage_pass2():
    inv=load_inv(); dup,_=pairs_from_inventory(inv); want={p for ps in dup.values() for p in ps}
    if os.path.exists(DERIV): want|={d["canonical_pool"] for d in json.load(open(DERIV))["pairs"] if d["canonical_active"]}|{d["sibling_pool"] for d in json.load(open(DERIV))["pairs"] if d["canonical_active"]}   # inclusiv orientarea inversa, pentru raportare
    if os.path.exists(RPC_PAIRS): want|={p for ps in json.load(open(RPC_PAIRS))["pairs"].values() for p in ps}   # PHASE 1: perechi same-mint din metadatele RPC (toate orientarile, pentru raportare)
    print("pool-uri in perechi duplicate",len(want),"perechi",len(dup),flush=True)
    if not want:
        with gzip.open(CACHE2,"wt") as f: pass
        print("PASS2_DONE 0 (fara pool-uri in perechi)"); return
    EV=collections.defaultdict(list); seq=0; t0=time.time()
    for fp in sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")):
        for line in readlines(fp):
            if '"src":"pamm"' not in line or ('BuyEvent' not in line and 'SellEvent' not in line): continue
            r=json.loads(line)
            for k,e in enumerate(r["events"]):
                if e["ev"] not in ("BuyEvent","SellEvent"): continue
                raw=base64.b64decode(e["raw"]); pool=b58e(raw[120:152])
                if pool not in want: continue
                ts,=struct.unpack_from("<q",raw,8); amt,mx,ub,uq,rb,rq,q2=struct.unpack_from("<QQQQQQQ",raw,16); lpbp,lpf,prbp,prf,q3,uq2=struct.unpack_from("<QQQQQQ",raw,72)
                if e["ev"]=="BuyEvent": rb_post=rb-amt; rq_post=rq+q3; cp_q=q3-lpf; gross=max(q2,uq2); cce=max(0,round((gross-cp_q-lpf-prf)*10000/cp_q)) if cp_q>0 else 0
                else: rb_post=rb+amt; rq_post=rq-q3; cp_q=q3+lpf; net=min(q2,uq2); cce=max(0,round((cp_q-lpf-prf-net)*10000/cp_q)) if cp_q>0 else 0
                EV[pool].append([r["t"],ts,r["slot"],seq,k,1 if e["ev"]=="BuyEvent" else 0,rb,rq,rb_post,rq_post,amt,cp_q,lpbp,prbp,cce,r["sig"]])
            seq+=1
        print(os.path.basename(fp),"ev",sum(len(v) for v in EV.values()),round(time.time()-t0),"s",flush=True)
    with gzip.open(CACHE2,"wt") as f:
        for p,ev in EV.items(): ev.sort(key=lambda x:(x[2],x[3],x[4])); f.write(json.dumps(dict(pool=p,ev=ev),separators=(",",":"))+"\n")
    print("PASS2_DONE",len(EV),flush=True)
def load_pass2():
    E={}
    with gzip.open(CACHE2,"rt") as f:
        for l in f: r=json.loads(l); E[r["pool"]]=r["ev"]
    return E
def chain_breaks(ev):
    """indicii i pentru care post-starea lui ev[i-1] != pre-starea lui ev[i] (Deposit/Withdraw neobservabile sau evenimente lipsa)."""
    return [i for i in range(1,len(ev)) if not (ev[i-1][8]==ev[i][6] and ev[i-1][9]==ev[i][7])]
def chain_ok_between(breaks,i0,i1):
    """True daca nu exista ruptura de lant in intervalul de indici (i0, i1] (decizie -> landing)."""
    j=bisect.bisect_right(breaks,i0); return not (j<len(breaks) and breaks[j]<=i1)
def implied_vq(ev):
    """(blocant 6) VQ implicit: >=5 observatii, mediana nenegativa, dispersie mica (IQR <= max(0.02 SOL, 2 % din mediana)), consistenta pe primele 80 evenimente; altfel None (pool exclus)."""
    v=[]
    for a in ev[:80]:
        if a[10]<=0 or a[11]<=0: continue
        if a[5]==1: v.append(a[6]*a[11]/a[10]-a[7]-a[11])
        else: v.append(a[11]*(a[6]+a[10])/a[10]-a[7])
    if len(v)<5: return None,len(v)
    v.sort(); med=v[len(v)//2]; q1=v[len(v)//4]; q3=v[3*len(v)//4]; iqr=q3-q1
    if med<0 or iqr>max(0.02e9,0.02*abs(med)): return None,len(v)
    return med,len(v)
def truncated_tails():
    out=[]
    for fp in sorted(glob.glob(f"{TAPE}/events_*.jsonl.gz")):
        last=None; ok=True
        try:
            with gzip.open(fp,"rt") as f:
                for line in f:
                    if '"t":' in line[:40]:
                        try: last=float(line.split('"t":')[1].split(',')[0])
                        except Exception: pass
        except (EOFError,zlib.error,OSError): ok=False
        h=datetime.datetime.strptime(os.path.basename(fp)[7:17],"%Y%m%d%H").timestamp()
        if (not ok) or (last is not None and last<h+3600-5): out.append((last if last else h,h+3600))
    return out
def interval_clean(t1,t2,OUT_W,TR):
    return not any(not (e<=t1 or s>=t2) for s,e in OUT_W) and not any(not (e<=t1 or s>=t2) for s,e in TR)
def joint_windows_clean(evA,evB,OUT_W,TR,brA,brB):
    """ferestre de stare comuna (dedup pe slot de inceput), fara outage/trunchiere pana la landing s+2 si FARA ruptura de lant in oricare pool in interiorul ferestrei (consistenta 100 %)."""
    W=joint_windows(evA,evB,OUT_W,TR); out=[]; slA=[e[2] for e in evA]; slB=[e[2] for e in evB]
    for s1,s2,L,t1 in W:
        ia0=bisect.bisect_right(slA,s1)-1; ia1=bisect.bisect_right(slA,s2+2)-1; ib0=bisect.bisect_right(slB,s1)-1; ib1=bisect.bisect_right(slB,s2+2)-1
        if ia0<0 or ib0<0: continue
        if chain_ok_between(brA,ia0,ia1) and chain_ok_between(brB,ib0,ib1): out.append((s1,s2,L,t1))
    return out
def load_rpc_meta():
    M={}
    for l in gzip.open(RPC_META,"rt"): r=json.loads(l); M[r["pool"]]=r
    return M
def stage_feasibility_rpc():
    """PHASE 1 (item 6-7): perechi same-mint din metadatele RPC; ferestre din Buy/Sell existente; FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM. Fara spread/PnL."""
    M=load_rpc_meta(); pairs=json.load(open(RPC_PAIRS))["pairs"]; E=load_pass2(); OUT_W=outages(); TR=truncated_tails(); inv=load_inv()
    res=[]; n_w=0; n_w2=0; n_w2_clean=0; win_by_date=collections.Counter(); win_by_date_all=collections.Counter(); both=0; combos_type=collections.Counter(); ptype=collections.Counter(); vq_ok=0; vq_n=0; chain_pairs=chain_bad=0; excl=collections.Counter()
    for tok,ps in pairs.items():
        strict=[p for p in ps if M[p]["orientation"]=="STRICT"]; rev=[p for p in ps if M[p]["orientation"]=="REVERSED"]
        ptype["STRICT_ONLY_GROUP" if len(strict)>=2 else ("MIXED" if strict and rev else "REVERSED_ONLY")]+=1
        if len(strict)<2: excl["GROUP_WITHOUT_2_STRICT_POOLS"]+=1; continue
        evs={p:E.get(p,[]) for p in strict}; brk={p:chain_breaks(evs[p]) for p in strict}
        for p in strict:
            ev=evs[p]; chain_pairs+=max(0,len(ev)-1); chain_bad+=len(brk[p]); vq_n+=1; vq_ok+=(implied_vq(ev)[0] is not None)
        for i in range(len(strict)):
            for j in range(i+1,len(strict)):
                a,b=strict[i],strict[j]
                if not evs[a] or not evs[b]: excl["COMBO_MISSING_EVENT_STREAM"]+=1; continue
                both+=1; c=M[a]["canonical"]+M[b]["canonical"]; combos_type["CANONICAL+NONCANONICAL" if c==1 else ("NONCANONICAL+NONCANONICAL" if c==0 else "CANONICAL+CANONICAL")]+=1
                Wall=joint_windows(evs[a],evs[b],OUT_W,TR); Wc=joint_windows_clean(evs[a],evs[b],OUT_W,TR,brk[a],brk[b]); n_w+=len(Wall); g2=[w for w in Wall if w[2]>2]; c2=[w for w in Wc if w[2]>2]; n_w2+=len(g2); n_w2_clean+=len(c2)
                for w in c2: win_by_date[datetime.datetime.utcfromtimestamp(w[3]).strftime("%Y-%m-%d")]+=1
                for w in g2: win_by_date_all[datetime.datetime.utcfromtimestamp(w[3]).strftime("%Y-%m-%d")]+=1
                res.append(dict(token_mint=tok,pool_a=a,pool_b=b,canonical_a=M[a]["canonical"],canonical_b=M[b]["canonical"],ev_a=len(evs[a]),ev_b=len(evs[b]),breaks_a=len(brk[a]),breaks_b=len(brk[b]),windows=len(Wall),windows_gt2=len(g2),windows_gt2_clean=len(c2)))
    F=dict(source="PHASE1_RPC_METADATA + tape Buy/Sell",groups=len(pairs),group_types=dict(ptype),excluded=dict(excl),combos_with_both_streams=both,combo_types=dict(combos_type),windows_total=n_w,windows_gt2=n_w2,windows_gt2_clean_chain100=n_w2_clean,windows_gt2_clean_by_utc_date=dict(win_by_date),windows_gt2_all_by_utc_date=dict(win_by_date_all),chain=dict(pairs=chain_pairs,breaks=chain_bad),vq=dict(pools=vq_n,computable=vq_ok),outage_windows=len(OUT_W),truncated_segments=len(TR),fee_resolver=json.load(open("research/external_review_remediation.json")).get("FEE_RESOLVER_VALID"),combos=res)
    gate=dict(pairs_ge_20=sum(1 for r in res if r["windows_gt2_clean"]>0)>=20,clean_windows_gt2_ge_100=n_w2_clean>=100,dates_ge_2=len(win_by_date)>=2,both_streams_present=both>0,reserves_valid_and_chain100_in_used_windows=(F["fee_resolver"] is True and n_w2_clean>0))
    F["pairs_with_clean_windows"]=sum(1 for r in res if r["windows_gt2_clean"]>0); F["FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM"]=dict(gate,PASS=all(v is True for v in gate.values()))
    json.dump(F,open("research/atomic_same_mint_arb_feasibility_rpc.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in F.items() if k!="combos"},default=str)); print("FEASIBILITY_RPC_DONE")
def joint_windows(evA,evB,OUT_W,TR=()):
    """ferestre de stare comuna: intre schimbari consecutive ale oricaruia din pool-uri, cand ambele au stare cunoscuta; dedup pe slot de inceput; lungime in sloturi."""
    if not evA or not evB: return []
    start=max(evA[0][2],evB[0][2]); slots=sorted({e[2] for e in evA if e[2]>=start}|{e[2] for e in evB if e[2]>=start}); tA=max(evA[-1][0],0); tB=max(evB[-1][0],0); end_t=min(evA[-1][0],evB[-1][0])
    tmap={}; 
    for e in evA+evB: tmap[e[2]]=max(tmap.get(e[2],0),e[0])
    W=[]
    for s1,s2 in zip(slots,slots[1:]):
        L=s2-s1; t1=tmap.get(s1); t2=tmap.get(s2)
        if t1 is None or t2 is None: continue
        if not interval_clean(t1,t2+1.0,OUT_W,TR): continue   # pana la landing (s+2 ~ +0.8 s) + marja
        W.append((s1,s2,L,t1))
    return W
# ---------------- fezabilitate ----------------
def stage_feasibility():
    inv=load_inv(); P=derived_pool_meta(inv); ST=inv["stats"]; dup,pinfo=pairs_from_inventory(inv); E=load_pass2(); OUT_W=outages(); TR=truncated_tails(); TPM=load_token_program_map()
    DV=json.load(open(DERIV)) if os.path.exists(DERIV) else {}
    F=dict(inventory=dict(built=inv["built"],event_types=inv["event_types"],n_create_pool=inv["n_create_pool"],n_active_pools=inv["n_active_pools"],deposit_withdraw_events_present=any(k in inv["event_types"] for k in ("DepositEvent","WithdrawEvent")),n_canonical=sum(1 for m in inv["pools"].values() if m["canonical"]),n_noncanonical=sum(1 for m in inv["pools"].values() if not m["canonical"]),n_derived_canonical_meta=sum(1 for m in P.values() if m.get("derived"))),
        pairs=dict(strict_token_base_wsol_quote_pairs_with_2plus_pools=len(dup),unordered_info_only=pinfo["unordered_pairs_with_2plus"],reversed_orientation_pools_excluded=pinfo["reversed_orientation_pools_excluded"]),gaps=dict(outage_windows=len(OUT_W),truncated_segments=len(TR)))
    pairs=[]; ptype=collections.Counter(); dates=set(); n_windows=0; n_windows_gt2=0; chain_bad=0; chain_pairs=0; vq_ok=0; vq_n=0; tokprog=collections.Counter(); win_by_date=collections.Counter(); excluded=collections.Counter()
    for tok,ps in dup.items():
        ps=sorted(set(ps)); metas=[P[p] for p in ps]; canon=[p for p in ps if P[p]["canonical"]]; nonc=[p for p in ps if not P[p]["canonical"]]
        assert all(P[p]["quote_mint"]==WSOL and P[p]["base_mint"]==tok for p in ps)
        if len(canon)>=2: excluded["CANONICAL+CANONICAL_IMPOSSIBLE"]+=1; continue   # un singur pool canonical per mint; doua = eroare de clasificare
        typ="CANONICAL+NONCANONICAL" if canon and nonc else "NONCANONICAL+NONCANONICAL"
        allowed,reason=pair_allowed_for_pnl(tok,TPM); pump_mint=allowed; tokprog[reason]+=1
        evs={p:E.get(p,[]) for p in ps}
        for p in ps:
            ev=evs[p]
            for a,b in zip(ev,ev[1:]):
                chain_pairs+=1
                if not (a[8]==b[6] and a[9]==b[7]): chain_bad+=1
            vq,nv=implied_vq(ev); vq_n+=1
            if vq is not None: vq_ok+=1
        # combinatii de 2 pool-uri (toate)
        pw=0; pw2=0; combos=[]
        for i in range(len(ps)):
            for j in range(i+1,len(ps)):
                a,b=ps[i],ps[j]; W=joint_windows(evs[a],evs[b],OUT_W,TR); pw+=len(W); pw2+=sum(1 for w in W if w[2]>2)
                for w in W:
                    if w[2]>2: win_by_date[datetime.datetime.utcfromtimestamp(w[3]).strftime("%Y-%m-%d")]+=1
                combos.append(dict(pool_a=a,pool_b=b,windows=len(W),windows_gt2=sum(1 for w in W if w[2]>2),ev_a=len(evs[a]),ev_b=len(evs[b])))
        if pw2>0:
            for m in metas: dates.add(datetime.datetime.utcfromtimestamp(m["ts"]).strftime("%Y-%m-%d"))
        n_windows+=pw; n_windows_gt2+=pw2; ptype[typ]+=1
        pairs.append(dict(token_mint=tok,n_pools=len(ps),type=typ,pump_mint=pump_mint,pools=[dict(pool=p,index=P[p]["index"],canonical=P[p]["canonical"],base_is_sol=(P[p]["base_mint"]==WSOL),created_ts=P[p]["ts"],created_slot=P[p]["slot"],n_events=len(evs[p]),implied_vq=implied_vq(evs[p])[0]) for p in ps],combos=combos,windows=pw,windows_gt2=pw2))
    F["pairs_detail"]=pairs; F["pair_types"]=dict(ptype); F["excluded_pairs"]=dict(excluded); F["derivation"]={k:v for k,v in DV.items() if k!="pairs"}
    F["token_program_observability"]=dict(tokprog,observable=(len(TPM)>0),mapped_mints=len(TPM),note="programul tokenului (owner-ul mint-ului) nu este in evenimentele PumpSwap; maparea explicita research/token_program_map.json este goala => toate perechile raman TOKEN_PROGRAM_UNKNOWN pentru PnL; NU blocheaza numararea perechilor")
    F["PREREQUISITE_MISSING_FOR_PNL"]="token_program_per_mint (owner-ul contului de mint) pentru mint-urile din perechile recuperate"; F["MINIMAL_RECOVERY_REQUIRED"]="o citire getAccountInfo per mint (sau captura owner-ului la CreatePool) — NU se executa fara aprobare"
    F["overlap"]=dict(windows_total_dedup_pair_slot=n_windows,windows_gt2_slots=n_windows_gt2,windows_gt2_by_utc_date=dict(win_by_date),dates_with_pairs=sorted(dates))
    F["chain_consistency"]=dict(pairs=chain_pairs,mismatches=chain_bad,rate_ok=(1-chain_bad/chain_pairs) if chain_pairs else None); F["vq"]=dict(pools=vq_n,vq_computable=vq_ok)
    F["fee_resolver"]=json.load(open("research/external_review_remediation.json")).get("FEE_RESOLVER_VALID") if os.path.exists("research/external_review_remediation.json") else None
    gate=dict(pairs_ge_20=len(pairs)>=20,windows_gt2_ge_100=n_windows_gt2>=100,dates_ge_2=len(win_by_date)>=2,reserves_and_fee_resolver_valid=bool(F["fee_resolver"]) and (F["chain_consistency"]["rate_ok"] or 0)>0.99,no_gap_in_required_interval=(n_windows_gt2>0))
    F["FEASIBILITY_GATE_BEFORE_TOKEN_PROGRAM"]=dict(gate,PASS=all(v is True for v in gate.values()))
    F["FEASIBILITY_GATE"]=dict(gate,token_program_known_for_pairs=(len(TPM)>0 and all(pair_allowed_for_pnl(p["token_mint"],TPM)[0] for p in pairs)),PASS=all(v is True for v in gate.values()) and len(TPM)>0)
    json.dump(F,open("research/atomic_same_mint_arb_feasibility.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in F.items() if k!="pairs_detail"},default=str)[:2500]); print("FEASIBILITY_DONE")
# ---------------- motor ----------------
def exec_buy(rb,rq,vq,q,lp,pr,cc):
    tot=lp+pr+cc; q2=q*10000//(10000+tot); lpf=q2*lp//10000; tok=rb*q2//(rq+vq+q2); return tok,q2,lpf,q2*pr//10000,q2*cc//10000
def exec_sell(rb,rq,vq,b,lp,pr,cc):
    if rb<=0 or b<=0: return 0,0,0,0,0
    brut=(rq+vq)*b//(rb+b); lpf=brut*lp//10000; prf=brut*pr//10000; ccf=brut*cc//10000; u=brut-lpf-prf-ccf; return min(u,max(0,rq)),brut,lpf,prf,ccf
TIER_SET={(int(lp),int(math.ceil(pr)),int(math.ceil(cr))) for _,cr,pr,lp in PF.TIERS}   # (lp, protocol, creator) intregi, fractiile rotunjite in sus
def resolve_fee(P,pool,rb,rq,vq,supply=None,ev_tier=None):
    """(lp, protocol, creator) bps sau None (=stare exclusa). Canonical: (a) tier DEMONSTRAT din evenimente (ev_tier = tripletul observat nenul identic inainte si dupa stare), altfel (b) tabelul de tiere cu supply VALIDAT per mint (fara constanta hardcodata); fara niciuna => None. Noncanonical: 25/5/0."""
    m=P[pool]
    if not m["canonical"]: return 25,5,0
    if ev_tier is not None: return ev_tier if tuple(ev_tier) in TIER_SET else None
    if supply is None: return None
    f=PF.fees_for(rb,rq,vq,supply); return int(f["lp_bp"]),int(math.ceil(f["protocol_bp"])),int(math.ceil(f["creator_bp"]))
def event_tier_at(ev,i):
    """tierul demonstrat de evenimente pentru starea de dupa ev[i]: ultimul triplet nenul <= i si primul triplet nenul > i trebuie sa fie identice; altfel None."""
    def trip(e): return (e[12],e[13],e[14]) if (len(e)>15 and isinstance(e[14],int)) else None
    prev=None
    for j in range(i,-1,-1):
        t=trip(ev[j])
        if t and t[0]>0: prev=t; break
    nxt=None
    for j in range(i+1,len(ev)):
        t=trip(ev[j])
        if t and t[0]>0: nxt=t; break
    return prev if (prev is not None and nxt is not None and prev==nxt) else None
def fee_schema_valid(pool_meta,ev):
    """schema de taxe observata compatibila: canonical => toate tripletele nenule apartin tabelului de tiere; noncanonical => toate egale cu (25,5,0). Returneaza (ok, triplete_observate)."""
    obs=collections.Counter((e[12],e[13],e[14]) for e in ev if len(e)>15 and isinstance(e[14],int) and e[12]>0)
    if not obs: return False,{}
    ok=all(t in TIER_SET for t in obs) if pool_meta["canonical"] else all(t==(25,5,0) for t in obs)
    return ok,{f"{a}/{b}/{c}":n for (a,b,c),n in obs.items()}
def token_episode_selection(routes_by_slot):
    """(dedup economic la nivel de token) routes_by_slot: lista cronologica de (slot, {route_id: predicted_net}) pentru un token. Max o ruta per (token, slot);
    un singur trade per EPISOD la nivel de token: episodul se deschide la primul slot cu max(predicted)>0 si se reseteaza doar cand max(predicted) intre toate rutele devine <=0.
    Returneaza lista de (slot, route_id, predicted_net) selectate."""
    sel=[]; open_=False
    for slot,routes in routes_by_slot:
        pos={r:v for r,v in routes.items() if v is not None and v>0}
        if not pos: open_=False; continue
        if not open_: r=max(pos.items(),key=lambda kv:(kv[1],kv[0]))[0]; sel.append((slot,r,pos[r])); open_=True
    return sel
def arb(P,pa,sa,vqa,pb,sb,vqb,Q):
    """SOL Q (lamports) -> token in pool a -> SOL in pool b. Stari s=(rb,rq). Ambele pool-uri trebuie sa aiba orientarea token=base, SOL=quote (blocant 1). Returneaza dict cu out, taxe, invarianti."""
    assert P[pa]["quote_mint"]==WSOL and P[pb]["quote_mint"]==WSOL and P[pa]["base_mint"]==P[pb]["base_mint"]!=WSOL, "orientare invalida"
    rb1,rq1=sa; rb2,rq2=sb; fa=resolve_fee(P,pa,rb1,rq1,vqa,supply=P[pa].get("supply"),ev_tier=P[pa].get("_ev_tier")); fb=resolve_fee(P,pb,rb2,rq2,vqb,supply=P[pb].get("supply"),ev_tier=P[pb].get("_ev_tier"))
    if fa is None or fb is None or sum(fa)<=0 or sum(fb)<=0: return None
    tok,q2,lpf1,prf1,ccf1=exec_buy(rb1,rq1,vqa,Q,*fa)
    if tok<=0 or tok>=rb1: return None
    out,brut,lpf2,prf2,ccf2=exec_sell(rb2,rq2,vqb,tok,*fb)
    inv_ok=((rb1-tok)*(rq1+vqa+q2)>=rb1*(rq1+vqa)) and ((rb2+tok)*(rq2+vqb-brut)>=rb2*(rq2+vqb)) and (rb1-tok>0) and (rq2-out>=0)
    return dict(tok=tok,out=out,fee1=lpf1+prf1+ccf1,fee2=lpf2+prf2+ccf2,fee1_bps=sum(fa),fee2_bps=sum(fb),capped=(out<brut-lpf2-prf2-ccf2),invariant_ok=inv_ok)
def state_after_slot(ev,slot):
    """starea dupa toate evenimentele cu slot <= slot; None daca niciunul."""
    i=bisect.bisect_right([e[2] for e in ev],slot)-1
    return (ev[i][8],ev[i][9],i) if i>=0 else None
def stage_eligibility():
    """PREFILTRARE INAINTE DE MINT RPC: ELIGIBLE_BEFORE_TOKEN_PROGRAM din date existente; poarta pe token-uri unice si ferestre (token, start_slot); doua populatii inghetate."""
    M=load_rpc_meta(); groups=json.load(open(RPC_PAIRS))["pairs"]; E=load_pass2(); OUT_W=outages(); TR=truncated_tails()
    pool_info={}
    for tok,ps in groups.items():
        for p in ps:
            ev=E.get(p,[]); vq,nv=implied_vq(ev); fv,obs=fee_schema_valid(M[p],ev)
            pool_info[p]=dict(token=tok,strict=(M[p]["orientation"]=="STRICT"),canonical=M[p]["canonical"],stream=bool(ev),n_events=len(ev),vq_valid=(vq is not None),vq=vq,fee_valid=fv,fee_observed=obs,breaks=len(chain_breaks(ev)))
    def population(kind):
        toks={}; combos=[]
        for tok,ps in groups.items():
            ok=[p for p in ps if pool_info[p]["strict"] and pool_info[p]["stream"] and pool_info[p]["vq_valid"] and pool_info[p]["fee_valid"]]
            win_tok={}; pair_w=0; n_c=0
            for i in range(len(ok)):
                for j in range(i+1,len(ok)):
                    a,b=ok[i],ok[j]; c=pool_info[a]["canonical"]+pool_info[b]["canonical"]
                    if c==2: continue
                    if kind=="PRIMARY_MEME" and c!=1: continue
                    if kind=="SECONDARY_ALL_NONCANONICAL" and c!=0: continue
                    W=[w for w in joint_windows_clean(E[a],E[b],OUT_W,TR,chain_breaks(E[a]),chain_breaks(E[b])) if w[2]>2]
                    if not W: continue
                    n_c+=1; pair_w+=len(W); combos.append(dict(token=tok,pool_a=a,pool_b=b,clean_windows=len(W)))
                    for w in W: win_tok.setdefault(w[0],w[3])   # dedup (token, start_slot)
            if n_c: toks[tok]=dict(pools=ok,combos=n_c,clean_pair_windows=pair_w,clean_token_slot_windows=len(win_tok),dates=sorted({datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d") for t in win_tok.values()}),by_date=dict(collections.Counter(datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d") for t in win_tok.values())))
        tw=sorted((v["clean_token_slot_windows"] for v in toks.values()),reverse=True); tot=sum(tw) or 1; dates=collections.Counter()
        for v in toks.values():
            for d,n in v["by_date"].items(): dates[d]+=n
        pools=sorted({p for v in toks.values() for p in v["pools"]})
        rep_=dict(UNIQUE_TOKENS=len(toks),UNIQUE_POOLS=len(pools),PAIR_COMBINATIONS=sum(v["combos"] for v in toks.values()),CLEAN_PAIR_WINDOWS=sum(v["clean_pair_windows"] for v in toks.values()),CLEAN_TOKEN_SLOT_WINDOWS=tot if toks else 0,DATES=sorted(dates),by_date=dict(dates),VQ_VALID_POOLS=sum(1 for p in pools if pool_info[p]["vq_valid"]),FEE_VALID_POOLS=sum(1 for p in pools if pool_info[p]["fee_valid"]),TOP1_TOKEN_WINDOW_SHARE=(tw[0]/tot if tw else None),TOP3_TOKEN_WINDOW_SHARE=(sum(tw[:3])/tot if tw else None),top_tokens=sorted(((t,v["clean_token_slot_windows"]) for t,v in toks.items()),key=lambda kv:-kv[1])[:10])
        gate=dict(UNIQUE_TOKEN_GATE=len(toks)>=20,TOKEN_SLOT_DEDUP_GATE=(tot if toks else 0)>=100,DATES_GATE=len(dates)>=2,VQ_GATE=(rep_["VQ_VALID_POOLS"]==len(pools) and len(pools)>0),FEE_GATE=(rep_["FEE_VALID_POOLS"]==len(pools) and len(pools)>0))
        rep_["GATE"]=dict(gate,PASS=all(gate.values())); return rep_,toks,combos
    out={}
    allp=[p for p in pool_info]; out["pool_filter_summary"]=dict(pools_in_groups=len(allp),strict=sum(1 for p in allp if pool_info[p]["strict"]),stream=sum(1 for p in allp if pool_info[p]["stream"]),vq_valid=sum(1 for p in allp if pool_info[p]["vq_valid"]),fee_valid=sum(1 for p in allp if pool_info[p]["fee_valid"]),all_four=sum(1 for p in allp if pool_info[p]["strict"] and pool_info[p]["stream"] and pool_info[p]["vq_valid"] and pool_info[p]["fee_valid"]),fee_invalid_examples=[(p[:8],pool_info[p]["canonical"],pool_info[p]["fee_observed"]) for p in allp if pool_info[p]["stream"] and not pool_info[p]["fee_valid"]][:8])
    for kind in ("PRIMARY_MEME","SECONDARY_ALL_NONCANONICAL"):
        r,toks,combos=population(kind); out[kind]=dict(report=r,tokens=toks,combos=combos)
    out["frozen_at"]=time.strftime("%Y-%m-%d %H:%M:%S %Z"); out["inputs"]=dict(rpc_meta_sha256=sha(RPC_META),pair_events_cache_sha256=sha(CACHE2),rpc_pairs_sha256=sha(RPC_PAIRS)); out["rule"]="ELIGIBLE_BEFORE_TOKEN_PROGRAM: ambele pool-uri STRICT (base=token, quote=WSOL), ambele fluxuri prezente, VQ valid separat (>=5 obs, nenegativ, IQR mic), schema de taxe observata compatibila (canonical: triplete in tabelul de tiere; noncanonical: 25/5/0), >=1 fereastra curata >2 sloturi cu lant 100 % si fara outage/trunchiere; poarta: >=20 token-uri unice, >=100 ferestre (token, start_slot), >=2 zile UTC; PRIMARY_MEME = doar canonical+noncanonical; SECONDARY = doar noncanonical+noncanonical, raportare separata"
    out["proposed_mint_rpc"]=dict(eligible_mints=sorted(set(out["PRIMARY_MEME"]["tokens"])|set(out["SECONDARY_ALL_NONCANONICAL"]["tokens"])),count=len(set(out["PRIMARY_MEME"]["tokens"])|set(out["SECONDARY_ALL_NONCANONICAL"]["tokens"])),calls_needed=(len(set(out["PRIMARY_MEME"]["tokens"])|set(out["SECONDARY_ALL_NONCANONICAL"]["tokens"]))+99)//100)
    json.dump(out,open("research/atomic_same_mint_arb_populations_frozen.json","w"),indent=1,default=str)
    print(json.dumps(out["pool_filter_summary"],default=str)); [print(k,json.dumps({kk:vv for kk,vv in out[k]["report"].items() if kk!="top_tokens"},default=str)) for k in ("PRIMARY_MEME","SECONDARY_ALL_NONCANONICAL")]; print("proposed_mint_rpc",out["proposed_mint_rpc"]["count"],"calls",out["proposed_mint_rpc"]["calls_needed"]); print("ELIGIBILITY_DONE")
POPFILE="research/atomic_same_mint_arb_populations_frozen.json"; SPEC2="research/slow_atomic_revert_arb_frozen_spec.json"
USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
def load_frozen_secondary(path=POPFILE):
    """populatia SECONDARY_ALL_NONCANONICAL inghetata (token -> pools); NU inventarul si NU derivarea."""
    Pp=json.load(open(path)); sec=Pp["SECONDARY_ALL_NONCANONICAL"]
    return dict(tokens={t:v["pools"] for t,v in sec["tokens"].items()},combos=sec["combos"],inputs=Pp["inputs"],rule=Pp["rule"],frozen_at=Pp["frozen_at"])
def run_engine(population,meta,events,spec,selector=None,OUT_W=(),TR=()):
    """SLOW_ATOMIC_REVERT_ARB — motor pur (fara I/O). population: {token: [pools]} (SECONDARY inghetat); meta: {pool: {orientation, canonical, base_mint, quote_mint, supply?}}; events: {pool: ev}.
    Decizie = ultima stare completa observabila (dupa slotul s); rutele unui token = toate perechile ordonate (buy in a, sell in b); selectia = token_episode_selection (max o decizie per token si episod, exclusiv dupa predicted);
    landing primar s+L1 (implicit 3), stres s+L2 (implicit 5); ambele leg-uri intr-o tranzactie atomica cu garda min_out = Q + costuri; garda picata => tranzactie REVERTATA: fara pierdere de inventar, dar taxa completa de retea+prioritate.
    Fara Jito/relay privat. Taxe: noncanonical 25/5/0; canonical doar cu tier demonstrat din evenimente sau supply validat (niciodata hardcodat)."""
    sel_fn=selector or token_episode_selection; L1=spec["landing"]["primary_slots"]; L2=spec["landing"]["stress_slots"]; SIG=spec["costs"]["base_signature_fee_lamports"]; PRI=spec["costs"]["priority_fee_lamports"]; Q=int(spec["notional_sol"]*LAMP)
    rows=[]; viol=collections.Counter(); episodes=0; used_selector=[]
    for tok,pools in population.items():
        ok=[]
        for p in pools:
            m=meta.get(p)
            if m is None or p not in events or not events[p]: viol["POOL_NOT_IN_META_OR_NO_EVENTS"]+=1; continue
            if m["orientation"]!="STRICT" or m["quote_mint"]!=WSOL or m["base_mint"]!=tok: viol["ORIENTATION_VIOLATION"]+=1; continue
            if m["canonical"]: viol["CANONICAL_POOL_IN_SECONDARY_POPULATION"]+=1; continue
            if implied_vq(events[p])[0] is None: viol["VQ_INVALID"]+=1; continue   # eligibilitate globala (populatia inghetata); la decizie se foloseste doar trecutul
            ok.append(p); m["_breaks"]=chain_breaks(events[p]); m["_slots"]=[e[2] for e in events[p]]; m["_vqcache"]={}
        if len(ok)<2: viol["TOKEN_WITHOUT_2_ELIGIBLE_POOLS"]+=1; continue
        routes=[(a,b) for a in ok for b in ok if a!=b]; slots=sorted({e[2] for p in ok for e in events[p]}); by_slot=[]; cache={}
        def vq_at(p,idx):
            """VQ implicit din evenimentele <= idx (fara lookahead); None daca insuficient/invalid."""
            c=meta[p]["_vqcache"]
            if idx not in c: c[idx]=implied_vq(events[p][:idx+1])[0]
            return c[idx]
        for s in slots:
            st={p:state_after_slot(events[p],s) for p in ok}; preds={}
            for a,b in routes:
                if st[a] is None or st[b] is None: continue
                va=vq_at(a,st[a][2]); vb=vq_at(b,st[b][2])
                if va is None or vb is None: continue
                pr=arb(meta,a,st[a][:2],int(va),b,st[b][:2],int(vb),Q)
                if pr is None or not pr["invariant_ok"]: continue
                preds[f"{a}>{b}"]=pr["out"]-Q-SIG-PRI
            if preds: by_slot.append((s,preds)); cache[s]=st
        selected=sel_fn(by_slot); used_selector.append(len(by_slot))
        for ep_i,(s,route,pred) in enumerate(selected):
            a,b=route.split(">"); st=cache[s]; t1=max(events[p][st[p][2]][0] for p in (a,b))
            if not interval_clean(t1-1,t1+L2*0.4+1,OUT_W,TR): viol["STATE_IN_OUTAGE_OR_TRUNCATION"]+=1; continue
            la1=state_after_slot(events[a],s+L1); lb1=state_after_slot(events[b],s+L1); la2=state_after_slot(events[a],s+L2); lb2=state_after_slot(events[b],s+L2)
            if not (chain_ok_between(meta[a]["_breaks"],st[a][2],la2[2]) and chain_ok_between(meta[b]["_breaks"],st[b][2],lb2[2])): viol["CHAIN_BREAK_DECISION_TO_LANDING"]+=1; continue
            va=int(vq_at(a,st[a][2])); vb=int(vq_at(b,st[b][2]))   # VQ de la decizie (constanta de protocol), nu re-estimat din viitor
            def land(sa,sb):
                r=arb(meta,a,sa[:2],va,b,sb[:2],vb,Q)
                if r is None or not r["invariant_ok"]: return dict(status="REVERTED_GUARD",pnl=-(SIG+PRI)/LAMP,out=None)
                min_out=Q+SIG+PRI   # garda de profit >= 0 pe leg-ul 2
                if r["out"]>=min_out: return dict(status="SUCCESS",pnl=(r["out"]-Q-SIG-PRI)/LAMP,out=r["out"])
                return dict(status="REVERTED_GUARD",pnl=-(SIG+PRI)/LAMP,out=r["out"])
            r1=land(la1,lb1); r2=land(la2,lb2); episodes+=1
            rows.append(dict(token=tok,episode_id=f"{tok}#{ep_i}",decision_slot=s,decision_t=t1,utc_date=datetime.datetime.utcfromtimestamp(t1).strftime("%Y-%m-%d"),route=route,pool_buy=a,pool_sell=b,n_routes_available=len(by_slot and [1]),predicted_net_sol=pred/LAMP,landing_primary_status=r1["status"],realized_primary_sol=r1["pnl"],landing_stress_status=r2["status"],realized_stress_sol=r2["pnl"],usdc_related=int(tok==USDC)))
    # dedup portofoliu: cheia include token+episod (deja unic) si max o tranzactie per slot intre token-uri (dupa predicted)
    best={}
    for r in rows:
        k=r["decision_slot"]
        if k not in best or r["predicted_net_sol"]>best[k]["predicted_net_sol"]: best[k]=r
    keep={(r["token"],r["episode_id"]) for r in best.values()}
    for r in rows: r["in_portfolio"]=int((r["token"],r["episode_id"]) in keep)
    return dict(rows=rows,violations=dict(viol),episodes=episodes,selector_calls=len(used_selector),selector_inputs=sum(used_selector))
def evaluate_slow_arb(rows,spec):
    """portile economice INGHETATE (spec['gates']); unitatea independenta = episodul la nivel de token."""
    port=[r for r in rows if r["in_portfolio"]]; g=spec["gates"]
    if not port: return dict(N=0,gate=None,verdict="SLOW_ATOMIC_REVERT_ARB_INSUFFICIENT_SAMPLE")
    pn=[r["realized_primary_sol"] for r in port]; st=stats(pn); succ=sum(1 for r in port if r["landing_primary_status"]=="SUCCESS")
    days=collections.defaultdict(float); [days.__setitem__(r["utc_date"],days[r["utc_date"]]+r["realized_primary_sol"]) for r in port]
    toks=collections.defaultdict(float); [toks.__setitem__(r["token"],toks[r["token"]]+r["realized_primary_sol"]) for r in port]; gp=sum(max(0,v) for v in toks.values()) or 1e-12
    cl=collections.defaultdict(list); [cl[(r["token"],r["utc_date"])].append(r["realized_primary_sol"]) for r in port]; groups=list(cl.values()); rng=random.Random(7); bs=[]
    for _ in range(1000):
        flat=[a for gg in [rng.choice(groups) for _ in groups] for a in gg]; bs.append(sum(flat)/len(flat))
    bs.sort(); ci=(bs[25],bs[974]); nonusdc=[r["realized_primary_sol"] for r in port if not r["usdc_related"]]; s5=[r["realized_stress_sol"] for r in port]
    gate=dict(episodes50=len(port)>=g["episodes_min"],tokens5=len({r["token"] for r in port})>=g["tokens_min"],EV=st["EV"]>0,PF=st["PF"]>=g["PF_min"],CI_low=ci[0]>0,days2of3=sum(1 for v in days.values() if v>0)>=g["positive_days_min"],exb1pct=st["EX_BEST_1PCT"]>0,token_share=max(toks.values())/gp<=g["token_share_max"],ev_ex_usdc=(sum(nonusdc)/len(nonusdc) if nonusdc else -1)>0,stress5=(sum(s5)/len(s5))>0)
    return dict(N=len(port),success=succ,reverted=len(port)-succ,stats=st,CI95_token_day=ci,by_day=dict(days),by_token_share=max(toks.values())/gp,gate=gate,verdict=("SLOW_ATOMIC_REVERT_ARB_HISTORICAL_PAPER_CANDIDATE" if all(gate.values()) else "SLOW_ATOMIC_REVERT_ARB_NO_VERIFIED_EDGE"))
def stage_freeze_slow():
    """ingheata SLOW_ATOMIC_REVERT_ARB (spec + hash-uri) INAINTE de orice PnL; consuma populatia secundara inghetata."""
    pop=load_frozen_secondary(); spec=dict(hypothesis="SLOW_ATOMIC_REVERT_ARB",label="POST_HOC_HISTORICAL",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        rationale="studiu general de arbitraj multipool PumpSwap pe pool-uri noncanonice pentru acelasi token (SECONDARY_ALL_NONCANONICAL: 13 token-uri, 80 pool-uri, 477 combinatii, 3.807 ferestre curate (token, slot), 3 zile UTC); NU salveaza ipoteza primara meme (inchisa: INSUFFICIENT_EXISTING_DATA_UNIQUE_TOKEN_GATE); proiectat fara a inspecta spread-uri, preturi sau PnL",
        population=dict(source=POPFILE,population="SECONDARY_ALL_NONCANONICAL",tokens=sorted(pop["tokens"]),n_tokens=len(pop["tokens"]),n_pools=sum(len(v) for v in pop["tokens"].values()),rule=pop["rule"],frozen_at=pop["frozen_at"]),
        inputs=dict(populations_sha256=sha(POPFILE),rpc_meta_sha256=sha(RPC_META),pair_events_cache_sha256=sha(CACHE2),rpc_pairs_sha256=sha(RPC_PAIRS)),
        infrastructure=dict(access="Helius WSS/RPC obisnuit, fara Jito/relay privat",decision="ultima stare completa observabila (dupa slotul s)",landing=dict(primary_slots=3,stress_slots=5),transaction="ambele leg-uri PumpSwap intr-o singura tranzactie atomica; leg-ul 2 cu garda min_out = Q + taxa semnatura + prioritate (profit >= 0)",revert="garda picata => fara pierdere de inventar; se plateste integral taxa de retea + prioritate; tranzactiile reusite si revertate raportate separat"),
        notional_sol=0.25,landing=dict(primary_slots=3,stress_slots=5),costs=dict(base_signature_fee_lamports=SIG_FEE,priority_fee_lamports=PRIO,jito_tip_lamports=0),
        fees="noncanonical 25/5/0 bps; canonical (absent in populatie) doar tier demonstrat din evenimente sau supply validat per mint; niciodata supply hardcodat",
        selection="token_episode_selection: max o decizie per token si episod de dislocare; ruta aleasa exclusiv dupa predicted net executabil; fara re-tranzactionare in sloturi consecutive pana cand toate rutele tokenului revin la predicted <= 0; combinatiile de perechi NU sunt observatii independente; cheia portofoliului = (token, episod) + max o tranzactie per slot",
        gates=dict(episodes_min=50,tokens_min=5,EV_gt=0,PF_min=1.5,CI95_cluster="token x zi UTC, limita inferioara > 0",positive_days_min=2,ex_best_1pct_gt=0,token_share_max=0.40,ev_ex_usdc_gt=0,stress_slot5_ev_gt=0,note="INGHETATE inainte de orice PnL; nu se editeaza dupa"),
        script_sha256=sha(__file__),status="FROZEN_NOT_EXECUTED")
    json.dump(spec,open(SPEC2,"w"),indent=1,ensure_ascii=False); print("SLOW_ATOMIC_REVERT_ARB spec frozen; sha",sha(SPEC2))
def stage_run_slow(dry_run=False,_loaders=None):
    """calea REALA de executie: populatia secundara inghetata + maparea RPC + evenimentele pass2 -> run_engine -> evaluate. NU se ruleaza acum (fara PnL)."""
    L=_loaders or dict(pop=load_frozen_secondary,meta=load_rpc_meta,events=load_pass2,spec=lambda:json.load(open(SPEC2)),outages=outages,truncated=truncated_tails)
    spec=L["spec"](); assert spec["status"]=="FROZEN_NOT_EXECUTED" or dry_run
    if not dry_run: assert spec["script_sha256"]==sha(__file__),"scriptul difera de spec-ul inghetat"
    pop=L["pop"](); meta=L["meta"](); ev=L["events"](); res=run_engine(pop["tokens"],meta,ev,spec,OUT_W=L["outages"](),TR=L["truncated"]()); ev_=evaluate_slow_arb(res["rows"],spec)
    if dry_run: return res,ev_
    json.dump(dict(engine=res,evaluation=ev_,label="POST_HOC_HISTORICAL"),open("research/slow_atomic_revert_arb_results.json","w"),indent=1,default=str); print("VERDICT",ev_["verdict"]); return res,ev_
def stage_freeze():
    raise SystemExit("INCHIS: ATOMIC_ARB_PRIMARY_MEME = INSUFFICIENT_EXISTING_DATA_UNIQUE_TOKEN_GATE (praguri si rezultate pastrate in atomic_same_mint_arb_populations_frozen.json); calea activa este freeze_slow/run_slow")
    inv=load_inv(); dup,_=pairs_from_inventory(inv)
    spec=dict(hypothesis="ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE",label="POST_HOC_HISTORICAL",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),inputs=dict(inventory_sha256=sha(INV),pair_events_cache_sha256=sha(CACHE2),feasibility_sha256=sha("research/atomic_same_mint_arb_feasibility.json"),remediation_sha256=sha("research/external_review_remediation.json"),tape_day_manifests=dict(SEP02="844ce65dbcd2c15b4146591287789aba1d8262b99802b50c727e30b940fd6d67",SEP03="b49738b577bd9bdeb0a9426c57eeabda9f0b4b27b31c8e27730cb97276c4545b",SEP04="3068bfa383a398824b8837a9eafb77f6b9ea583a953fbe56c6c1256280a35def")),
        population=dict(pairs=[dict(token=t,pools=sorted(set(ps))) for t,ps in sorted(dup.items())],rule="perechi STRICTE (base_mint=token, quote_mint=WSOL) cu >=2 pool-uri: din CreatePoolEvent in banda si/sau pool canonical derivat zero-RPC (PDA) cu evenimente in banda; pool-urile cu base=WSOL sunt excluse (fara normalizare); doar mint-uri cu program cunoscut (research/token_program_map.json) egal cu SPL Token clasic intra in PnL; pool-uri cu vq implicit invalid (<5 obs., negativ, IQR mare) excluse; rupturi de lant in (decizie, landing s+2] exclud starea; ferestrele care intersecteaza deconectari WSS sau segmente trunchiate sunt excluse; o singura tranzactie per episod de dislocare; max o tranzactie per slot in portofoliu"),
        canonical_rule="index==0 AND creator==PDA(['pool-authority', base_mint], pump program) AND quote==WSOL",fee_resolver="canonical: tabel pumpswap_fees.py dupa mcap (creator/protocol fractionare rotunjite in sus la bp intreg, conservator); noncanonical: lp 25 + protocol 5 + creator 0 = 30 bps; nu se copiaza bps-urile evenimentelor",
        integer_math=dict(buy="q2=Q*10000//(10000+lp+pr+cc); lpf=q2*lp//10000; tok=rb*q2//(rq+vq+q2)",sell="brut=(rq+vq)*tok//(rb+tok); out=brut-brut*lp//10000-brut*pr//10000-brut*cc//10000; out<=rq real",invariants="(rb-tok)*(rq+vq+q2)>=rb*(rq+vq); (rb+tok)*(rq+vq-brut)>=rb*(rq+vq); rezerve nenegative"),
        directions=["A: SOL->token pool_1 -> SOL pool_2","B: SOL->token pool_2 -> SOL pool_1"],notionals_sol=NOTIONALS,primary_notional_sol=PRIMARY,
        decision_landing=dict(decision_state="starea de dupa toate evenimentele cu slot<=s (sfarsitul slotului s), pentru fiecare slot s cu eveniment in oricare pool al perechii",predicted="profitul net calculat numai pe decision state",primary_landing="starea de dupa toate evenimentele cu slot<=s+1 (conservator; fara txIndex => scenariul nefavorabil)",stress_landing="slot<=s+2",selection="numai dupa predicted_net_profit; outcome-ul de landing nu participa la selectie"),
        costs=dict(base_signature_fee_lamports=SIG_FEE,priority_fee_lamports=PRIO,jito_tip_scenarios_lamports=TIPS,own_impact="inclus prin executia exacta pe ambele leg-uri",headline="BASE (priority 0.0001 SOL + tip 0.00001 SOL); ZERO_TIP nu poate fi headline"),
        dedup="max o oportunitate per (pereche, slot, notional); portofoliu global: max o tranzactie per slot, aleasa dupa cel mai mare predicted_net",
        final_gate=dict(primary=PRIMARY,N_realized_min=50,positive_days_min=2,EV_gt=0,median_gt=0,PF_min=1.5,CI95_low_gt=0,ex_best_1pct_gt=0,top1pct_max=0.40,max_day_share_max=0.60,survival_min=0.60,EV_landing_s2_gt=0,EV_STRESS_2_gt=0,zero_violations=True,segments_positive="canonical/noncanonical separat daca este segmentul candidat",no_post_hoc_choice=True),
        script_sha256="PLACEHOLDER")
    json.dump(spec,open(SPEC,"w"),indent=1,ensure_ascii=False); print("spec written (script hash placeholder)")
def stats(vals,hours=None):
    if not vals: return None
    v=sorted(vals,reverse=True); n=len(v); w=[a for a in v if a>0]; l=[a for a in v if a<=0]; gp=sum(w) or 1e-12
    st=dict(N=n,EV=sum(v)/n,median=S.median(v),PF=((sum(w)/abs(sum(l))) if (l and sum(l)<0) else (float("inf") if w else 0.0)),win_rate=len(w)/n,EX_BEST_1=(sum(v[1:])/(n-1)) if n>1 else None,EX_BEST_3=(sum(v[3:])/(n-3)) if n>3 else None,EX_BEST_1PCT=sum(v[max(1,n//100):])/max(1,n-max(1,n//100)),top1pct_contrib=sum(v[:max(1,n//100)])/gp)
    if hours:
        hb=collections.defaultdict(list); [hb[h].append(x) for x,h in zip(vals,hours)]; g=list(hb.values()); rng=random.Random(7); bs=[]
        for _ in range(1000):
            flat=[a for gg in [rng.choice(g) for _ in g] for a in gg]; bs.append(sum(flat)/len(flat))
        bs.sort(); st["CI95_cluster_hour"]=(bs[25],bs[974])
    return st
def stage_run():
    raise SystemExit("INCHIS: calea veche pair-by-pair nu se mai executa; foloseste run_slow (episoade la nivel de token, populatie secundara inghetata)")
def _legacy_stage_run():
    spec=json.load(open(SPEC)); assert spec["script_sha256"]!="PLACEHOLDER","spec neinghetata (hash script lipsa)"
    assert spec["script_sha256"]==sha(__file__),"hash-ul scriptului nu corespunde spec-ului inghetat"
    inv=load_inv(); P=derived_pool_meta(inv); E=load_pass2(); OUT_W=outages(); TR=truncated_tails(); TPM=load_token_program_map(); dup,_=pairs_from_inventory(inv); rows=[]; viol=collections.Counter(); t0=time.time()
    for tok,ps in dup.items():
        ps=sorted(set(ps)); allowed,reason=pair_allowed_for_pnl(tok,TPM)
        if not allowed: viol["PAIR_EXCLUDED_TOKEN_PROGRAM"]+=1; viol[f"PAIR_EXCLUDED_TOKEN_PROGRAM:{reason}"]+=1; continue
        if any(P[p]["quote_mint"]!=WSOL or P[p]["base_mint"]!=tok for p in ps): viol["ORIENTATION_VIOLATION"]+=1; continue
        if sum(1 for p in ps if P[p]["canonical"])>=2: viol["CANONICAL+CANONICAL_IMPOSSIBLE"]+=1; continue
        vqs={}
        for p in ps:
            ev=E.get(p,[]); vq,_=implied_vq(ev); vqs[p]=vq
        for i in range(len(ps)):
            for j in range(i+1,len(ps)):
                a,b=ps[i],ps[j]; evA=E.get(a,[]); evB=E.get(b,[])
                if not evA or not evB or vqs[a] is None or vqs[b] is None: viol["PAIR_COMBO_EXCLUDED_NO_EVENTS_OR_VQ"]+=1; continue
                vqa=int(vqs[a]); vqb=int(vqs[b]); brA=chain_breaks(evA); brB=chain_breaks(evB); ptype="CANONICAL+NONCANONICAL" if (P[a]["canonical"]!=P[b]["canonical"]) else ("NONCANONICAL+NONCANONICAL" if not P[a]["canonical"] else "CANONICAL+CANONICAL")
                slots=sorted({e[2] for e in evA}|{e[2] for e in evB}); start=max(evA[0][2],evB[0][2]); tmap={}
                for e in evA+evB: tmap[e[2]]=max(tmap.get(e[2],0),e[0])
                seen=set(); episode_open={}
                for s in slots:
                    if s<start or s in seen: continue
                    seen.add(s); t1=tmap[s]
                    if not interval_clean(t1-1,t1+2,OUT_W,TR): viol["STATE_IN_OUTAGE_OR_TRUNCATION"]+=1; continue
                    sa=state_after_slot(evA,s); sb=state_after_slot(evB,s)
                    if sa is None or sb is None: continue
                    la1=state_after_slot(evA,s+1); lb1=state_after_slot(evB,s+1); la2=state_after_slot(evA,s+2); lb2=state_after_slot(evB,s+2)
                    if not (chain_ok_between(brA,sa[2],la2[2]) and chain_ok_between(brB,sb[2],lb2[2])): viol["CHAIN_BREAK_DECISION_TO_LANDING"]+=1; continue
                    stale_a=s-evA[sa[2]][2]; stale_b=s-evB[sb[2]][2]
                    for N in NOTIONALS:
                        Q=int(N*LAMP)
                        for dname,(pa,va,sta,l1a,l2a,pb,vb,stb,l1b,l2b) in (("A",(a,vqa,sa,la1,la2,b,vqb,sb,lb1,lb2)),("B",(b,vqb,sb,lb1,lb2,a,vqa,sa,la1,la2))):
                            pred=arb(P,pa,sta[:2],va,pb,stb[:2],vb,Q)
                            if pred is None: continue
                            if not pred["invariant_ok"]: viol["INVARIANT_VIOLATION_PREDICTED"]+=1; continue
                            pred_net=pred["out"]-Q-SIG_FEE-PRIO-TIPS["BASE"]; ek=(dname,N)
                            first_in_episode=episode_first_flags([None if not episode_open.get(ek,False) else 1, pred_net])[1]==1 if False else None
                            if pred_net<=0: episode_open[ek]=False; continue
                            first_in_episode=(0 if episode_open.get(ek,False) else 1); episode_open[ek]=True   # (blocant 8) identic cu episode_first_flags (testat)
                            land=arb(P,pa,l1a[:2],va,pb,l1b[:2],vb,Q); land2=arb(P,pa,l2a[:2],va,pb,l2b[:2],vb,Q)
                            if land is None or not land["invariant_ok"]: viol["INVARIANT_VIOLATION_LANDING"]+=1; continue
                            rows.append(dict(token=tok,pool_1=pa,pool_2=pb,pair_type=ptype,direction=dname,decision_slot=s,decision_t=t1,utc_date=datetime.datetime.utcfromtimestamp(t1).strftime("%Y-%m-%d"),utc_hour=int(t1//3600),notional_sol=N,pred_out_lamports=pred["out"],pred_fee1=pred["fee1"],pred_fee2=pred["fee2"],fee1_bps=pred["fee1_bps"],fee2_bps=pred["fee2_bps"],pred_net_base=pred_net/LAMP,
                                real_out_lamports=land["out"],real_fee1=land["fee1"],real_fee2=land["fee2"],realized_net_zero_tip=(land["out"]-Q-SIG_FEE-PRIO)/LAMP,realized_net_base=(land["out"]-Q-SIG_FEE-PRIO-TIPS["BASE"])/LAMP,realized_net_stress1=(land["out"]-Q-SIG_FEE-PRIO-TIPS["STRESS_1"])/LAMP,realized_net_stress2=(land["out"]-Q-SIG_FEE-PRIO-TIPS["STRESS_2"])/LAMP,
                                realized_net_landing_s2_base=((land2["out"]-Q-SIG_FEE-PRIO-TIPS["BASE"])/LAMP) if land2 and land2["invariant_ok"] else None,landing_state_changed=int((l1a[2],l1b[2])!=(sta[2],stb[2])),staleness_slots=max(stale_a,stale_b),staleness_a=stale_a,staleness_b=stale_b,first_in_episode=int(first_in_episode),capped_by_real_reserve=int(land["capped"]),fee_anomaly_pool=int(any(inv["stats"].get(p,{}).get("zero_fee",0)>0 for p in (pa,pb)))))
        if len(rows)%1000==0 and rows: print("rows",len(rows),round(time.time()-t0),"s",flush=True)
    # dedup portofoliu global: o tranzactie per slot per notional (cel mai mare predicted)
    best={}
    for r in rows:
        if not r["first_in_episode"]: continue   # primar: doar prima stare a fiecarui episod
        k=(r["notional_sol"],r["decision_slot"])
        if k not in best or r["pred_net_base"]>best[k]["pred_net_base"]: best[k]=r
    port=list(best.values())
    with gzip.open("research/atomic_same_mint_arb_opportunities.csv.gz","wt",newline="") as f:
        cols=list(rows[0].keys()) if rows else ["none"]; w=csv.DictWriter(f,fieldnames=cols+["in_portfolio"]); w.writeheader()
        sel={id(r) for r in port}
        for r in rows: w.writerow(dict(r,in_portfolio=int(id(r) in sel)))
    R=dict(label="POST_HOC_HISTORICAL",n_candidate_rows=len(rows),n_portfolio_rows=len(port),violations=dict(viol),by_notional={})
    for N in NOTIONALS:
        pr=[r for r in port if r["notional_sol"]==N]; out={}
        for seg_name,seg in (("ALL",pr),("CANONICAL+NONCANONICAL",[r for r in pr if r["pair_type"]=="CANONICAL+NONCANONICAL"]),("NONCANONICAL+NONCANONICAL",[r for r in pr if r["pair_type"]=="NONCANONICAL+NONCANONICAL"]),("A",[r for r in pr if r["direction"]=="A"]),("B",[r for r in pr if r["direction"]=="B"]),("NO_FEE_ANOMALY_POOLS",[r for r in pr if not r["fee_anomaly_pool"]])):
            if not seg: out[seg_name]=None; continue
            hrs=[r["utc_hour"] for r in seg]; d={}
            d["predicted"]=stats([r["pred_net_base"] for r in seg]); 
            for key in ("realized_net_zero_tip","realized_net_base","realized_net_stress1","realized_net_stress2"): d[key]=stats([r[key] for r in seg],hrs)
            l2=[r["realized_net_landing_s2_base"] for r in seg if r["realized_net_landing_s2_base"] is not None]; d["realized_landing_s2_base"]=stats(l2)
            d["survival_pred_to_realized_base"]=sum(1 for r in seg if r["realized_net_base"]>0)/len(seg); d["landing_state_changed_share"]=sum(r["landing_state_changed"] for r in seg)/len(seg); d["staleness_slots_median"]=S.median([r["staleness_slots"] for r in seg])
            days=collections.defaultdict(float); [days.__setitem__(r["utc_date"],days[r["utc_date"]]+r["realized_net_base"]) for r in seg]; d["by_day_realized_base"]=dict(days); d["positive_days"]=sum(1 for v in days.values() if v>0); gp=sum(max(0,v) for v in days.values()) or 1e-12; d["max_day_share"]=max(days.values())/gp if days else None
            pairs=collections.defaultdict(float); [pairs.__setitem__(r["token"],pairs[r["token"]]+r["realized_net_base"]) for r in seg]; d["profit_per_pair_top5"]=sorted(pairs.items(),key=lambda kv:-kv[1])[:5]; d["n_pairs"]=len(pairs)
            seq=sorted(seg,key=lambda r:r["decision_t"]); eq=pk=dd=0.0
            for r in seq: eq+=r["realized_net_base"]; pk=max(pk,eq); dd=min(dd,eq-pk)
            d["max_drawdown_sol"]=dd; span_h=(seq[-1]["decision_t"]-seq[0]["decision_t"])/3600 if len(seq)>1 else None; d["profit_per_hour_sol"]=(sum(r["realized_net_base"] for r in seg)/span_h) if span_h else None
            out[seg_name]=d
        R["by_notional"][str(N)]=out
    A=(R["by_notional"][str(PRIMARY)] or {}).get("ALL"); g=None; F=json.load(open("research/atomic_same_mint_arb_feasibility.json"))
    if A and A["realized_net_base"]: g=final_gate(A,R["by_notional"][str(PRIMARY)],viol,spec,F["token_program_observability"].get("observable"))
    R["final_gate_primary_0_25"]=g; R["FINAL_VERDICT"]="ATOMIC_ARB_HISTORICAL_PAPER_CANDIDATE" if (g and all(g.values())) else "ATOMIC_ARB_NO_VERIFIED_EDGE"; R["runtime_s"]=round(time.time()-t0,1)
    json.dump(R,open("research/atomic_same_mint_arb_results.json","w"),indent=1,default=str); print("rows",len(rows),"portfolio",len(port),"viol",dict(viol)); print("VERDICT",R["FINAL_VERDICT"],g); print("RUN_DONE")
if __name__=="__main__":
    {"derive":stage_derive,"pass2":stage_pass2,"feasibility":stage_feasibility,"feasibility_rpc":stage_feasibility_rpc,"eligibility":stage_eligibility,"freeze_slow":stage_freeze_slow,"run_slow":stage_run_slow,"freeze":stage_freeze,"run":stage_run}[sys.argv[1]]()
