"""S2 POST_ARB_RESIDUAL_SPREAD (spec inghetat in cod): dupa fiecare ciclu exact verificat (recensamant), reconstruim post-starile celor doua pool-uri din evenimentele ciclului, calculam cea mai buna ruta exact-B (0,10 SOL) DOAR pe starea imediat dupa tranzactie;
daca predicted <= 0 => 'zero oportunitate' (nu se cauta mai tarziu); altfel intrare la +3 sloturi worst-of (stari ancorate din pass2), min_out = Q + cost, revert la esec; dedup pe episod la nivel de token; stres +5."""
import sys,gzip,json,collections,statistics as S,time; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"; LAMP=10**9; Q=int(0.10*LAMP); FEE=105000
spec=dict(strategy="S2_POST_ARB_RESIDUAL_SPREAD",mechanism="un arbitraj atomic real reduce dar nu elimina complet discrepanta cross-pool (marime limitata, taxe, rezerve); un al doilea participant mai lent ar putea captura reziduul",who_loses="LP-urile pool-urilor cu pret ramas divergent; nu depinde de activitatea ulterioara a botului",population="cele 500 cicluri exacte din recensamant (independent verificat), pool-urile lor din cache-ul pass2",rule="stare = post-starea ambelor pool-uri imediat dupa ciclu; rute ordonate; ruta cu predicted maxim; predicted<=0 => 0 oportunitate; intrare +3 sloturi (worst-of pre/post, stari ancorate), buy exact-B sub 0,10 SOL cu max_quote=Q, sell exact B cu min_out=Q+cost; stres +5; un episod per token pana cand predicted<=0",frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s2_frozen_spec.json",spec)
rows=[json.loads(l) for l in gzip.open(f"{C.D}/census_rows.jsonl.gz","rt")]; ex=[r for r in rows if r["cls"]=="EXACT"]; cand={}
for l in gzip.open(f"{C.D}/census_candidates.jsonl.gz","rt"): c=json.loads(l); cand[(c["sig"],c["user"],c["token"])]=c
E=A.load_pass2(); meta=A.load_rpc_meta(); out=[]; cnt=collections.Counter(); open_ep={}
for r in sorted(ex,key=lambda r:(r["slot"],r["t"])):
    c=cand[(r["sig"],r["user"],r["token"])]; post={}
    for d in c["events"]: post[d["pool"]]=(d["rb_post"],d["rq_post"])
    pools=[p for p in post if p in E and E[p]]
    if len(pools)<2: cnt["NO_PASS2_COVERAGE"]+=1; continue
    best=None
    for a in pools:
        for b in pools:
            if a==b: continue
            ia=next((i for i,e in enumerate(E[a]) if e[3]==None),None)
            # VQ din evenimentele pana la slotul ciclului
            sa=A.state_after_slot(E[a],r["slot"]); sb=A.state_after_slot(E[b],r["slot"])
            if sa is None or sb is None: continue
            va=A.implied_vq(E[a][:sa[2]+1])[0]; vb=A.implied_vq(E[b][:sb[2]+1])[0]
            if va is None or vb is None: cnt["VQ_INVALID"]+=1; continue
            fa=A.resolve_fee(meta,a,post[a][0],post[a][1],int(va),ev_tier=A.event_tier_at(E[a],sa[2])); fb=A.resolve_fee(meta,b,post[b][0],post[b][1],int(vb),ev_tier=A.event_tier_at(E[b],sb[2]))
            if fa is None or fb is None: cnt["FEE_UNRESOLVED"]+=1; continue
            B=A.max_base_for_budget(post[a][0],post[a][1],int(va),Q,*fa)
            if B<=0: continue
            bo=A.buy_exact_out(post[a][0],post[a][1],int(va),B,*fa); so=A.exec_sell(post[b][0],post[b][1],int(vb),B,*fb)[0]; pred=so-bo[0]-FEE
            if best is None or pred>best[0]: best=(pred,a,b,B,int(va),int(vb),fa,fb)
    if best is None: cnt["NO_ROUTE"]+=1; continue
    pred,a,b,B,va,vb,fa,fb=best; tok=r["token"]
    if pred<=0: cnt["ZERO_RESIDUAL_OPPORTUNITY"]+=1; open_ep[tok]=False; out.append(dict(token=tok,day=r["day"],slot=r["slot"],pred=pred/LAMP,opportunity=0)); continue
    if open_ep.get(tok): cnt["SAME_EPISODE_SKIPPED"]+=1; continue
    open_ep[tok]=True
    def land(L):
        vals=[]
        for ls in (r["slot"]+L-1,r["slot"]+L):
            sa=A.state_provable(E[a],ls); sb=A.state_provable(E[b],ls)
            if sa is None or sb is None: return None
            bo=A.buy_exact_out(sa[0],sa[1],va,B,*fa)
            if bo is None or bo[0]>Q: vals.append(-FEE); continue
            so=A.exec_sell(sb[0],sb[1],vb,B,*fb)[0]; vals.append((so-bo[0]-FEE) if so>=Q+FEE else -FEE)
        return min(vals)
    l3=land(3); l5=land(5)
    if l3 is None or l5 is None: cnt["LANDING_UNPROVABLE"]+=1; continue
    out.append(dict(token=tok,mint=tok,day=r["day"],slot=r["slot"],pred=pred/LAMP,opportunity=1,pnl=l3/LAMP,pnl5=l5/LAMP,pnlc=None))
tr=[r for r in out if r["opportunity"]==1]; test=[r for r in tr if r["day"]!=C.DAYS["DEV"]]; st=C.stats(test); bs=C.boot(test); st5=C.stats(test,"pnl5"); g,verdict=C.global_gate(st,bs,st5,st,0.05)
res=dict(spec_sha256=C.sha(f"{OUT}/s2_frozen_spec.json"),cycles=len(ex),counts=dict(cnt),residual_opportunities_total=len(tr),zero_opportunity=sum(1 for r in out if r["opportunity"]==0),dev_descriptive=C.stats([r for r in tr if r["day"]==C.DAYS["DEV"]]),test=st,bootstrap=bs,stress5=st5,predicted_mean=(S.mean([r["pred"] for r in tr]) if tr else None),gate=g,verdict=verdict,note="cost x1.25 nu se aplica separat (taxele sunt 25/5/0 fixe pe noncanonical; costul de retea e inclus); revert = -0.000105 SOL")
C.write("s2_results.json",res); print("S2",verdict,dict(cnt),"opps",len(tr),"test",{k:(st or {}).get(k) for k in ("N","mints","EV","PF")}); print("S2_DONE")
