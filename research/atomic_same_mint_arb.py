"""ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE — executor. Etape: (1) perechi duplicate din inventar (pass 1); (2) pass 2: evenimentele pool-urilor din perechi (cache);
(3) fezabilitate FARA PnL + FEASIBILITY_GATE; (4) spec inghetata + hash-uri; (5) motor atomic exact, decizie/landing fara lookahead, costuri, metrici, poarta finala.
Ruleaza: python research/atomic_same_mint_arb.py stage  (stage in: pass2 | feasibility | freeze | run)."""
import gzip,json,base64,struct,os,glob,collections,sys,time,zlib,hashlib,bisect,math,random,statistics as S,datetime,csv
sys.path.insert(0,'strategy_e'); import pda; from pda import b58e
sys.path.insert(0,'.'); import pumpswap_fees as PF
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; TAPE="strategy_m/data/tape"; WSOL="So11111111111111111111111111111111111111112"; SUPPLY=10**15
INV=f"{D}/pamm_pool_inventory.json.gz"; CACHE2=f"{D}/arb_pair_events.jsonl.gz"; SPEC="research/atomic_same_mint_arb_frozen_spec.json"
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
    return dup,info
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
    inv=load_inv(); dup,_=pairs_from_inventory(inv); want={p for ps in dup.values() for p in ps}; print("pool-uri in perechi duplicate",len(want),"perechi",len(dup),flush=True)
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
                if e["ev"]=="BuyEvent": rb_post=rb-amt; rq_post=rq+q3; cp_q=q3-lpf
                else: rb_post=rb+amt; rq_post=rq-q3; cp_q=q3+lpf
                EV[pool].append([r["t"],ts,r["slot"],seq,k,1 if e["ev"]=="BuyEvent" else 0,rb,rq,rb_post,rq_post,amt,cp_q,lpbp,prbp,r["sig"]])
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
    inv=load_inv(); P=inv["pools"]; ST=inv["stats"]; dup,pinfo=pairs_from_inventory(inv); E=load_pass2(); OUT_W=outages(); TR=truncated_tails()
    F=dict(inventory=dict(built=inv["built"],event_types=inv["event_types"],n_create_pool=inv["n_create_pool"],n_active_pools=inv["n_active_pools"],deposit_withdraw_events_present=any(k in inv["event_types"] for k in ("DepositEvent","WithdrawEvent")),n_canonical=sum(1 for m in P.values() if m["canonical"]),n_noncanonical=sum(1 for m in P.values() if not m["canonical"])),
        pairs=dict(strict_token_base_wsol_quote_pairs_with_2plus_pools=len(dup),unordered_info_only=pinfo["unordered_pairs_with_2plus"],reversed_orientation_pools_excluded=pinfo["reversed_orientation_pools_excluded"]),gaps=dict(outage_windows=len(OUT_W),truncated_segments=len(TR)))
    pairs=[]; ptype=collections.Counter(); dates=set(); n_windows=0; n_windows_gt2=0; chain_bad=0; chain_pairs=0; vq_ok=0; vq_n=0; tokprog=collections.Counter(); win_by_date=collections.Counter(); excluded=collections.Counter()
    for tok,ps in dup.items():
        ps=sorted(set(ps)); metas=[P[p] for p in ps]; canon=[p for p in ps if P[p]["canonical"]]; nonc=[p for p in ps if not P[p]["canonical"]]
        assert all(P[p]["quote_mint"]==WSOL and P[p]["base_mint"]==tok for p in ps)
        typ="CANONICAL+NONCANONICAL" if canon and nonc else ("NONCANONICAL+NONCANONICAL" if len(nonc)>=2 else "CANONICAL+CANONICAL")
        pump_mint=False; tokprog["TOKEN_PROGRAM_UNOBSERVABLE_IN_EVENTS"]+=1   # (blocant 5) nu se presupune SPL Token clasic
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
    F["pairs_detail"]=pairs; F["pair_types"]=dict(ptype); F["token_program_observability"]=dict(tokprog,observable=False,note="programul tokenului (owner-ul mint-ului) NU este capturat in evenimentele PumpSwap; fara el Token-2022 (transfer fee/hooks) nu poate fi exclus => PREREQUISITE_MISSING = token_program_per_mint; recuperare minima = 1 getAccountInfo per mint (interzis acum)")
    F["PREREQUISITE_MISSING"]="token_program_per_mint (owner-ul contului de mint)" ; F["MINIMAL_RECOVERY_REQUIRED"]="o citire getAccountInfo per mint din perechile duplicate (sau captura owner-ului la CreatePool) — NU se executa fara aprobare"
    F["overlap"]=dict(windows_total_dedup_pair_slot=n_windows,windows_gt2_slots=n_windows_gt2,windows_gt2_by_utc_date=dict(win_by_date),dates_with_pairs=sorted(dates))
    F["chain_consistency"]=dict(pairs=chain_pairs,mismatches=chain_bad,rate_ok=(1-chain_bad/chain_pairs) if chain_pairs else None); F["vq"]=dict(pools=vq_n,vq_computable=vq_ok)
    F["fee_resolver"]=json.load(open("research/external_review_remediation.json")).get("FEE_RESOLVER_VALID") if os.path.exists("research/external_review_remediation.json") else None
    gate=dict(pairs_ge_20=len(dup)>=20,windows_gt2_ge_100=n_windows_gt2>=100,dates_ge_2=len(win_by_date)>=2,reserves_and_fee_resolver_valid=bool(F["fee_resolver"]) and (F["chain_consistency"]["rate_ok"] or 0)>0.99,no_gap_in_required_interval=(n_windows_gt2>0 and True),token_program_observable=False)
    F["FEASIBILITY_GATE"]=dict(gate,PASS=all(v is True for v in gate.values()))
    json.dump(F,open("research/atomic_same_mint_arb_feasibility.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in F.items() if k!="pairs_detail"},default=str)[:2500]); print("FEASIBILITY_DONE")
# ---------------- motor ----------------
def exec_buy(rb,rq,vq,q,lp,pr,cc):
    tot=lp+pr+cc; q2=q*10000//(10000+tot); lpf=q2*lp//10000; tok=rb*q2//(rq+vq+q2); return tok,q2,lpf,q2*pr//10000,q2*cc//10000
def exec_sell(rb,rq,vq,b,lp,pr,cc):
    if rb<=0 or b<=0: return 0,0,0,0,0
    brut=(rq+vq)*b//(rb+b); lpf=brut*lp//10000; prf=brut*pr//10000; ccf=brut*cc//10000; u=brut-lpf-prf-ccf; return min(u,max(0,rq)),brut,lpf,prf,ccf
def resolve_fee(P,pool,rb,rq,vq):
    m=P[pool]
    if m["canonical"]: f=PF.fees_for(rb,rq,vq,SUPPLY); return int(f["lp_bp"]),int(math.ceil(f["protocol_bp"])),int(math.ceil(f["creator_bp"]))
    return 25,5,0
def arb(P,pa,sa,vqa,pb,sb,vqb,Q):
    """SOL Q (lamports) -> token in pool a -> SOL in pool b. Stari s=(rb,rq). Ambele pool-uri trebuie sa aiba orientarea token=base, SOL=quote (blocant 1). Returneaza dict cu out, taxe, invarianti."""
    assert P[pa]["quote_mint"]==WSOL and P[pb]["quote_mint"]==WSOL and P[pa]["base_mint"]==P[pb]["base_mint"]!=WSOL, "orientare invalida"
    rb1,rq1=sa; rb2,rq2=sb; fa=resolve_fee(P,pa,rb1,rq1,vqa); fb=resolve_fee(P,pb,rb2,rq2,vqb)
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
def stage_freeze():
    F=json.load(open("research/atomic_same_mint_arb_feasibility.json")); assert F["FEASIBILITY_GATE"]["PASS"], "feasibility gate a picat; nu se ingheata motorul"
    inv=load_inv(); dup,_=pairs_from_inventory(inv)
    spec=dict(hypothesis="ATOMIC_SAME_MINT_PUMPSWAP_ARBITRAGE",label="POST_HOC_HISTORICAL",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"),inputs=dict(inventory_sha256=sha(INV),pair_events_cache_sha256=sha(CACHE2),feasibility_sha256=sha("research/atomic_same_mint_arb_feasibility.json"),remediation_sha256=sha("research/external_review_remediation.json"),tape_day_manifests=dict(SEP02="844ce65dbcd2c15b4146591287789aba1d8262b99802b50c727e30b940fd6d67",SEP03="b49738b577bd9bdeb0a9426c57eeabda9f0b4b27b31c8e27730cb97276c4545b",SEP04="3068bfa383a398824b8837a9eafb77f6b9ea583a953fbe56c6c1256280a35def")),
        population=dict(pairs=[dict(token=t,pools=sorted(set(ps))) for t,ps in sorted(dup.items())],rule="perechi neordonate {SOL, token} cu >=2 pool-uri PumpSwap create in banda; doar mint-uri pump.fun (SPL Token clasic); pool-urile cu vq implicit necalculabil sau lant de rezerve inconsistent >1 % sunt excluse; ferestrele care intersecteaza deconectari WSS sunt excluse"),
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
    spec=json.load(open(SPEC)); assert spec["script_sha256"]!="PLACEHOLDER","spec neinghetata (hash script lipsa)"
    assert spec["script_sha256"]==sha(__file__),"hash-ul scriptului nu corespunde spec-ului inghetat"
    inv=load_inv(); P=inv["pools"]; E=load_pass2(); OUT_W=outages(); dup,_=pairs_from_inventory(inv); rows=[]; viol=collections.Counter(); t0=time.time()
    for tok,ps in dup.items():
        ps=sorted(set(ps))
        viol["PAIR_EXCLUDED_UNKNOWN_TOKEN_PROGRAM"]+=1; continue   # (blocant 5) programul tokenului nu este observabil in banda => nicio pereche nu intra in motor
        vqs={}
        for p in ps:
            ev=E.get(p,[]); vq,_=implied_vq(ev); vqs[p]=vq
        for i in range(len(ps)):
            for j in range(i+1,len(ps)):
                a,b=ps[i],ps[j]; evA=E.get(a,[]); evB=E.get(b,[])
                if not evA or not evB or vqs[a] is None or vqs[b] is None: viol["PAIR_COMBO_EXCLUDED_NO_EVENTS_OR_VQ"]+=1; continue
                vqa=int(vqs[a]); vqb=int(vqs[b]); brA=chain_breaks(evA); brB=chain_breaks(evB); ptype="CANONICAL+NONCANONICAL" if (P[a]["canonical"]!=P[b]["canonical"]) else "NONCANONICAL+NONCANONICAL"
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
                            if pred_net<=0: episode_open[ek]=False; continue
                            first_in_episode=not episode_open.get(ek,False); episode_open[ek]=True   # (blocant 8) o singura tranzactie per episod de dislocare
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
    if A and A["realized_net_base"]:
        rb_=A["realized_net_base"]; BN=R["by_notional"][str(PRIMARY)]; segs=[k for k in ("CANONICAL+NONCANONICAL","NONCANONICAL+NONCANONICAL") if BN.get(k) and BN[k]["realized_net_base"]]
        g=dict(N50=rb_["N"]>=50,days2=A["positive_days"]>=2,EV=rb_["EV"]>0,median=rb_["median"]>0,PF=rb_["PF"]>=1.5,CI_low=rb_.get("CI95_cluster_hour",(-1,0))[0]>0,exb1pct=rb_["EX_BEST_1PCT"]>0,top1=rb_["top1pct_contrib"]<=0.4,day_share=(A["max_day_share"] or 1)<=0.6,survival=A["survival_pred_to_realized_base"]>=0.6,landing_s2=((A["realized_landing_s2_base"] or {}).get("EV",-1))>0,stress2=(A["realized_net_stress2"]["EV"])>0,
            zero_violations=all(viol.get(k,0)==0 for k in ("INVARIANT_VIOLATION_PREDICTED","INVARIANT_VIOLATION_LANDING","FEE_RESOLVER_NONE","TIMING_LANDING_BEFORE_DECISION","CHAIN_BREAK_DECISION_TO_LANDING","STATE_IN_OUTAGE_OR_TRUNCATION","PAIR_COMBO_EXCLUDED_NO_EVENTS_OR_VQ","PAIR_EXCLUDED_UNKNOWN_TOKEN_PROGRAM")) and F["token_program_observability"].get("observable") is True,
            segments_positive=all(BN[k]["realized_net_base"]["EV"]>0 for k in segs) if segs else False,no_post_hoc=(spec["primary_notional_sol"]==PRIMARY and spec["notionals_sol"]==NOTIONALS and spec["final_gate"]["PF_min"]==1.5 and spec["final_gate"]["N_realized_min"]==50 and spec["costs"]["priority_fee_lamports"]==PRIO and spec["costs"]["jito_tip_scenarios_lamports"]==TIPS))
    R["final_gate_primary_0_25"]=g; R["FINAL_VERDICT"]="ATOMIC_ARB_HISTORICAL_PAPER_CANDIDATE" if (g and all(g.values())) else "ATOMIC_ARB_NO_VERIFIED_EDGE"; R["runtime_s"]=round(time.time()-t0,1)
    json.dump(R,open("research/atomic_same_mint_arb_results.json","w"),indent=1,default=str); print("rows",len(rows),"portfolio",len(port),"viol",dict(viol)); print("VERDICT",R["FINAL_VERDICT"],g); print("RUN_DONE")
if __name__=="__main__":
    {"pass2":stage_pass2,"feasibility":stage_feasibility,"freeze":stage_freeze,"run":stage_run}[sys.argv[1]]()
