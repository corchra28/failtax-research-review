"""S4 RECURRING_WALLET_SWARM_V1 (spec inghetat in cod): graf de co-aparitie DOAR din DEV (09-02): portofele care cumpara acelasi mint intr-o fereastra de 10 s (cumparari post-migrare din m_pools), legatura recurenta pe >= 3 mint-uri DEV distincte;
excluse portofelele cu > 50 lansari in DEV (spam) si perechile din aceeasi semnatura; clustere = componente conexe; calitatea clusterului = EV mediu al intrarii fixe (decizie la a 3-a cumparare + 3 sloturi, 0,10 SOL, +60 s) pe mint-urile DEV ale clusterului (outcome-uri DEV complet anterioare); clustere eligibile = calitate > 0, inghetate.
Semnal pe VAL/PH: >= 3 membri ai unui cluster eligibil cumpara un mint nou; intrare dupa al 3-lea cumparator + 3 sloturi; iesire +60 s; stres +5; cost x1.25."""
import sys,gzip,json,collections,statistics as S,time,bisect; sys.path.insert(0,'research/overnight_20260905/strategies'); import common as C; A=C.A
OUT="research/overnight_20260905/strategies"; LAMP=10**9; W=10; SPAM=50
spec=dict(strategy="S4_RECURRING_WALLET_SWARM_V1",mechanism="un grup recurent de portofele care au aparut impreuna inaintea unor miscari reusite anterioare contine mai multa informatie decat breadth-ul brut",who_loses="vanzatorii care ofera lichiditate inaintea cererii coordonate; noi intram dupa al 3-lea membru",graph="DEV only; muchie = doua portofele cumpara acelasi mint la <= 10 s distanta; recurenta pe >= 3 mint-uri DEV; excluse portofele cu > 50 lansari DEV si perechi cu aceeasi semnatura (indisponibil in m_pools => excludem cumparari in acelasi slot ale perechii); clustere = componente conexe cu >= 3 membri",quality="EV mediu DEV al intrarii fixe pe mint-urile in care >= 3 membri au cumparat (fara mint-ul testat); eligibil daca > 0; inghetat",signal="VAL/PH: al 3-lea membru distinct al unui cluster eligibil cumpara mint-ul; intrare la slotul cumpararii + 3 sloturi (worst-of), 0,10 SOL; iesire +60 s; stres +5; cost x1.25; max o pozitie per slot",rejects=["un portofel/cluster/token domina rezultatele"],frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
C.write("s4_frozen_spec.json",spec)
X={}
for l in gzip.open(f"{C.D}/m_pools.jsonl.gz","rt"): x=json.loads(l); X[x["mint"]]=x
dev=[x for x in X.values() if x["day"]==C.DAYS["DEV"]]
launch_cnt=collections.Counter(); pair_m=collections.defaultdict(set)
for x in dev:
    buys=[(e[1],e[2],e[15]) for e in x["ev"] if e[5]==1]; seen=set()
    for t,s,u in buys: seen.add(u)
    for u in seen: launch_cnt[u]+=1
for x in dev:
    buys=sorted((e[1],e[2],e[15]) for e in x["ev"] if e[5]==1); first={}
    for t,s,u in buys: first.setdefault(u,(t,s))
    us=[(t,s,u) for u,(t,s) in first.items()]; us.sort()
    for i in range(len(us)):
        for j in range(i+1,len(us)):
            if us[j][0]-us[i][0]>W: break
            if us[i][1]==us[j][1]: continue   # acelasi slot ~ potential aceeasi semnatura/bundle
            a,b=sorted((us[i][2],us[j][2])); pair_m[(a,b)].add(x["mint"])
edges=[(a,b) for (a,b),ms in pair_m.items() if len(ms)>=3 and launch_cnt[a]<=SPAM and launch_cnt[b]<=SPAM]
adj=collections.defaultdict(set)
for a,b in edges: adj[a].add(b); adj[b].add(a)
seen=set(); clusters=[]
for u in adj:
    if u in seen: continue
    comp=set(); stack=[u]
    while stack:
        v=stack.pop()
        if v in comp: continue
        comp.add(v); stack+=list(adj[v]-comp)
    seen|=comp
    if len(comp)>=3: clusters.append(sorted(comp))
def third_buy_slot(x,members):
    buys=sorted((e[1],e[2],e[15]) for e in x["ev"] if e[5]==1 and e[15] in members); seen=[]
    for t,s,u in buys:
        if u not in seen: seen.append(u)
        if len(seen)==3: return s
    return None
def trade(x,slot,L=3,fm=1.0,hold=60): return C.execute_at(x["ev"],x["vq"],slot,L,0.10,hold,fee_mult=fm)
qual={}
for ci,cl in enumerate(clusters):
    m=set(cl); ev_=[]
    for x in dev:
        s=third_buy_slot(x,m)
        if s is None: continue
        o=trade(x,s)
        if o["status"]=="OK": ev_.append(o["pnl"])
    qual[ci]=dict(size=len(cl),dev_mints=len(ev_),dev_EV=(S.mean(ev_) if ev_ else None))
elig={ci for ci,q in qual.items() if q["dev_EV"] is not None and q["dev_EV"]>0 and q["dev_mints"]>=2}
C.write("s4_clusters_frozen.json",dict(n_clusters=len(clusters),eligible=sorted(elig),quality={str(k):v for k,v in qual.items()},members_hashed={str(ci):[C.hid(u) for u in cl] for ci,cl in enumerate(clusters)},spam_threshold=SPAM,window_s=W,frozen_at=time.strftime("%Y-%m-%d %H:%M:%S")))
out=[]
for x in X.values():
    if x["day"]==C.DAYS["DEV"]: continue
    best=None
    for ci in elig:
        s=third_buy_slot(x,set(clusters[ci]))
        if s is not None and (best is None or s<best[0]): best=(s,ci)
    if best is None: continue
    s,ci=best; o=trade(x,s); o5=trade(x,s,L=5); oc=trade(x,s,fm=1.25)
    out.append(dict(mint=x["mint"],day=x["day"],cluster=ci,slot=s,status=o["status"],pnl=o.get("pnl"),pnl5=o5.get("pnl"),pnlc=oc.get("pnl")))
st=C.stats(out); bs=C.boot(out); st5=C.stats(out,"pnl5"); stc=C.stats(out,"pnlc"); g,verdict=C.global_gate(st,bs,st5,stc,0.05)
cl_share=None
if out:
    pos=collections.defaultdict(float); [pos.__setitem__(r["cluster"],pos[r["cluster"]]+max(0,r["pnl"] or 0)) for r in out]; gp=sum(pos.values()) or 1e-12; cl_share=max(pos.values())/gp
    if verdict.startswith("PASS") and cl_share>=0.4: verdict="FAIL_CLUSTER_DOMINANCE"
res=dict(spec_sha256=C.sha(f"{OUT}/s4_frozen_spec.json"),graph=dict(dev_mints=len(dev),edges=len(edges),clusters=len(clusters),eligible_clusters=len(elig)),signals=len(out),test=st,bootstrap=bs,stress5=st5,cost125=stc,top_cluster_share=cl_share,status_counts=dict(collections.Counter(r["status"] for r in out)),gate=g,verdict=verdict)
C.write("s4_results.json",res); print("S4",verdict,res["graph"],"signals",len(out),{k:(st or {}).get(k) for k in ("N","mints","EV","PF")}); print("S4_DONE")
