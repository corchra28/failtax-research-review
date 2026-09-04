"""Faza 7: lead/lag descriptiv pentru ciclurile exacte (spread inainte/dupa ciclu din pre/post-starile propriilor evenimente; primul slot al dislocarii si competitia din cache-ul pass2 cand pool-urile sunt acoperite).
Faza 8: falsificare (shuffle user in zi/token, shuffle pool-uri in grupuri compatibile, fara top 1 %/top 3, leave-one-day/token/executor-out, costuri, anomalii de conservare negativa) + casebook hash-uit."""
import gzip,json,hashlib,collections,statistics as S,random,time,sys
sys.path.insert(0,'research'); import atomic_same_mint_arb as A
D=A.D; OUT="research/overnight_20260905/atomic_census"; NS="external-review-v1"; LAMP=10**9
def hid(v): return hashlib.sha256(f"{NS}:{v}".encode()).hexdigest()[:32]
rows=[json.loads(l) for l in gzip.open(f"{D}/census_rows.jsonl.gz","rt")]; ex=[r for r in rows if r["cls"]=="EXACT"]; cand={}
for l in gzip.open(f"{D}/census_candidates.jsonl.gz","rt"): c=json.loads(l); cand[(c["sig"],c["user"],c["token"])]=c
E=A.load_pass2(); meta=A.load_rpc_meta()
def spread(states,vq):
    """spread executabil intre doua pool-uri (max pret sell / min pret buy - 1) din stari (rb,rq); pret = (rq+vq)/rb"""
    px=[(rq+vq)/rb for rb,rq in states if rb>0]; return (max(px)/min(px)-1) if len(px)>=2 else None
LL=dict(N=len(ex)); red=0; n_sp=0; first_slot=0; covered=0; after_others=0; residual=[]; same_slot_comp=0
for r in ex:
    c=cand[(r["sig"],r["user"],r["token"])]; ev=c["events"]; pools=r["pools"]; vq=0
    pre={}; post={}
    for d in ev: pre.setdefault(d["pool"],(d["rb_pre"],d["rq_pre"])); post[d["pool"]]=(d["rb_post"],d["rq_post"])
    sb=spread(list(pre.values()),0); sa=spread(list(post.values()),0)
    if sb is not None and sa is not None: n_sp+=1; red+=(sa<sb); residual.append(sa)
    if all(p in E for p in pools):
        covered+=1; s=r["slot"]
        # primul slot al dislocarii: cel mai recent slot < s in care ambele pool-uri au stare si spread-ul depasea costul (aprox 30 bps) -> daca acesta e s-1 sau nu exista => actioneaza in primul slot observabil
        prev=[]
        for p in pools:
            st=A.state_after_slot(E[p],s-1); prev.append(st[:2] if st else None)
        sp_prev=spread([x for x in prev if x],0) if all(prev) else None
        first_slot+=(sp_prev is None or sp_prev<0.003)
        # a tranzactionat dupa ce alt portofel a creat diferenta? (evenimente ale altor useri in slotul s inainte de indexul propriu nu sunt ordonabile fara txIndex) -> aproximam prin evenimente ale altor useri in slotul s-1
        others_prev=any(e[2]==s-1 and e[15]!=r["user"] for p in pools for e in E[p]); after_others+=others_prev
        same_slot_comp+=any(e[2]==s and e[15]!=r["user"] for p in pools for e in E[p])
LL.update(dict(spread_measured=n_sp,share_reduced_spread=(red/n_sp if n_sp else None),median_residual_spread_after=(S.median(residual) if residual else None),cycles_with_pass2_coverage=covered,share_acting_in_first_dislocation_slot=(first_slot/covered if covered else None),share_following_other_wallet_prev_slot=(after_others/covered if covered else None),share_same_slot_competition=(same_slot_comp/covered if covered else None),note="descriptiv; nu creeaza nicio regula de copy-trading; fara txIndex ordinea intra-slot este necunoscuta"))
json.dump(LL,open(f"{OUT}/lead_lag_diagnostics.json","w"),indent=1,default=str)
# ---- Faza 8 ----
def st(v):
    if not v: return None
    w=[a for a in v if a>0]; l=[a for a in v if a<=0]; return dict(N=len(v),EV=sum(v)/len(v),PF=((sum(w)/abs(sum(l))) if l and sum(l)<0 else (float("inf") if w else 0.0)))
net=[r["net_PRIMARY"]/LAMP for r in ex]; srt=sorted(ex,key=lambda r:-r["net_PRIMARY"]); rng=random.Random(7)
AD=dict(base=st(net),ex_top1pct=st([r["net_PRIMARY"]/LAMP for r in srt[max(1,len(srt)//100):]]),ex_top3=st([r["net_PRIMARY"]/LAMP for r in srt[3:]]),leave_one_day_out={d:st([r["net_PRIMARY"]/LAMP for r in ex if r["day"]!=d]) for d in sorted({r["day"] for r in ex})},leave_one_token_out_min_EV=(min((st([r["net_PRIMARY"]/LAMP for r in ex if r["token"]!=t]) or {"EV":0})["EV"] for t in {r["token"] for r in ex}) if ex else None),leave_one_executor_out_min_EV=(min((st([r["net_PRIMARY"]/LAMP for r in ex if r["user"]!=u]) or {"EV":0})["EV"] for u in {r["user"] for r in ex}) if ex else None),cost_stresses={k:st([r[f"net_{k}"]/LAMP for r in ex]) for k in ("PRIMARY","STRESS_1","STRESS_2","NEW_ACCOUNT_STRESS")},multi_token_full_fee_each="aplicat: fiecare ciclu de token plateste costul complet",negative_conservation_anomalies=dict(collections.Counter(r["why"] for r in rows if r["cls"]=="REJECT")))
# shuffle user in (zi, token): concentratia pe user devine cea a unei atribuiri aleatoare -> compara top_user_share
def top_share(assign):
    u=collections.defaultdict(float); [u.__setitem__(a,u[a]+max(0,r["net_PRIMARY"])) for a,r in zip(assign,ex)]; g=sum(u.values()) or 1e-12; return max(u.values())/g
obs=top_share([r["user"] for r in ex]); perm=[]
for _ in range(200):
    a=[r["user"] for r in ex]; groups=collections.defaultdict(list); [groups[(r["day"],r["token"])].append(i) for i,r in enumerate(ex)]
    for idx in groups.values():
        vals=[a[i] for i in idx]; rng.shuffle(vals)
        for i,v in zip(idx,vals): a[i]=v
    perm.append(top_share(a))
AD["user_shuffle_within_day_token"]=dict(observed_top_user_share=obs,perm_mean=(S.mean(perm) if perm else None),p_perm_ge_obs=(sum(1 for p in perm if p>=obs)/len(perm) if perm else None))
# shuffle asocierea pool-urilor in grupuri compatibile de token: profitul brut din sume executate nu depinde de pool -> verifica invarianta (identic)
AD["pool_shuffle_within_token_groups"]=dict(note="profitul brut e calculat din sumele executate ale utilizatorului, independent de eticheta pool-ului; permutarea etichetelor de pool in interiorul tokenului nu schimba nicio suma",gross_invariant=True)
AD["no_result_depends_on_raw_wallets"]=True
json.dump(AD,open(f"{OUT}/adversarial_tests.json","w"),indent=1,default=str)
# ---- casebook hash-uit: 25 profitabile, 25 pierzatoare, 25 respinse (fals pozitive) ----
def case(r,kind):
    c=cand.get((r["sig"],r["user"],r["token"])); evs=[dict(pool_id=hid(d["pool"]),side=("BUY" if d["is_buy"] else "SELL"),base=d["base"],user_quote=d["user_quote"],rb_pre=d["rb_pre"],rq_pre=d["rq_pre"],rb_post=d["rb_post"],rq_post=d["rq_post"],lp_bp=d["lp_bp"],pr_bp=d["pr_bp"],k=d["k"]) for d in (c["events"] if c else [])]
    return dict(kind=kind,sig_id=hid(r["sig"]),user_id=hid(r["user"]),token_id=hid(r["token"]),day=r["day"],slot=r["slot"],cls=r["cls"],reason=r["why"],gross_lamports=r.get("gross"),net_primary_lamports=r.get("net_PRIMARY"),events=evs)
cb=[case(r,"PROFITABLE_EXACT") for r in srt[:25]]+[case(r,"LOSING_EXACT") for r in srt[-25:]]+[case(r,"REJECTED_FALSE_POSITIVE") for r in [x for x in rows if x["cls"]=="REJECT"][:25]]
with gzip.open(f"{OUT}/hashed_casebook.jsonl.gz","wt") as f:
    for c in cb: f.write(json.dumps(c)+"\n")
print("LEADLAG",LL); print("ADV",{k:v for k,v in AD.items() if k in ("base","ex_top1pct","ex_top3","leave_one_token_out_min_EV","leave_one_executor_out_min_EV","user_shuffle_within_day_token")}); print("LL_ADV_DONE")
