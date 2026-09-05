"""CURVE2X V2 — a doua implementare INDEPENDENTA a etichetei first-passage (FAZA 3, regula 17), scrisa separat de curve2x_lib.simulate:
construieste explicit seria valorii nete (curba + pool), apoi determina prima trecere cu o logica diferita (scanare pe sloturi grupate). Compara pe >= 500 cazuri stratificate."""
import gzip,json,sys,os,collections,random
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import curve2x_lib as L
D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; OUT="research/curve2x_v2"
def buy_tokens(vs,vt,gross,fee):
    net=gross*10000//(10000+fee); return vt-(vs*vt)//(vs+net),net
def sell_value(vs,vt,rs,h,fee):
    if h<=0 or vt<=0: return 0
    g=vs-(vs*vt)//(vt+h)-1
    if g<0: g=0
    if g>rs: g=rs
    return g*(10000-fee)//10000
def independent(rec,i,dec_ts,N,H,land=3,cost=1.0,pool=None):
    fee=int(round(125*cost)); netc=int(210000*cost); gross=int(N*10**9); T=rec["trades"]; trig=T[i]
    # intrare: ultima stare cu slot <= slot+land (scanare completa, nu incrementala)
    cand=[t for t in T if t[1]<=trig[1]+land and (t[1],t[2],t[3])>=(trig[1],trig[2],trig[3])]; st=cand[-1]
    ck=(rec["complete_slot"],rec["complete_seq"],10**9) if rec.get("complete_ts") is not None else None
    if ck is not None and ((st[1],st[2],st[3])>=ck or rec["complete_slot"]<=trig[1]+land): return "NO_FILL_MIGRATED"
    h,ds=buy_tokens(st[10],st[11],gross,fee)
    if h<=0: return "NO_FILL"
    # serie de valori: (slot, seq, k, ts, valoare_neta)
    ser=[(st[1],st[2],st[3],st[0],sell_value(st[10]+ds,st[11]-h,st[8]+ds,h,fee)-netc)]
    for t in T:
        if (t[1],t[2],t[3])<=(st[1],st[2],st[3]): continue
        if ck is not None and (t[1],t[2],t[3])>=ck: break
        if t[0]>dec_ts+H: continue
        ser.append((t[1],t[2],t[3],t[0],sell_value(t[10]+ds,t[11]-h,t[8]+ds,h,fee)-netc))
    migrated=ck is not None
    if migrated and pool is not None:
        for s in pool["states"]:
            if s[0]>dec_ts+H: continue
            rb=s[4]-h; val=((s[5]+pool["vq"])*h//(rb+h) if rb>0 else 0); val=min(val,s[5]) if rb>0 else 0; fb=int(round(s[6]*cost)); ser.append((s[1],s[2],s[3],s[0],val*(10000-fb)//10000-netc))
    ser.sort()
    # grupare pe slot: intr-un slot, daca exista vreo valoare <= 0,5x => SL; altfel daca exista >= 2x => TP (prima trecere in ordinea sloturilor)
    by=collections.OrderedDict()
    for s in ser: by.setdefault(s[0],[]).append(s)
    for slot,vals in by.items():
        if vals[0][3]>dec_ts+H: break
        # in interiorul slotului respectam ordinea: prima trecere in ordinea seq decide, dar SL castiga daca ambele apar in slot
        hit=None
        for v in vals:
            if v[4]<=0.5*gross: hit="SL_FIRST"; break
            if v[4]>=2*gross and hit is None: hit="TP_FIRST"
        if hit=="TP_FIRST" and any(v[4]<=0.5*gross for v in vals): hit="SL_FIRST"
        if hit:
            if migrated and pool is None and slot>=rec["complete_slot"]: return "UNAVAILABLE_OR_RESOLVED"
            return hit
    if migrated and pool is None: return "UNAVAILABLE_OR_RESOLVED"
    return "TIMEOUT_OTHER"
def main():
    rows=[json.loads(l) for l in gzip.open(f"{D}/curve2x_rows.jsonl.gz","rt")]; H=L.HORIZONS[L.PRIMARY_H]; N=L.PRIMARY_N; P=f"{N}|base"
    strata=collections.defaultdict(list)
    for r in rows:
        x=r["lab"][P]; st=x.get("status") if x.get("status")!="OK" else (x["15M"]["state"] or "UNAVAILABLE"); strata[(r["day"],r["landmark"],bool(x.get("migrated_in_window")),st)].append(r)
    rng=random.Random(20260905); sample=[]
    for k,v in sorted(strata.items()): sample+=rng.sample(v,min(len(v),max(3,600//max(1,len(strata)))))
    while len(sample)<600: sample.append(rng.choice(rows))
    need={r["mint"] for r in sample}; recs={}
    for line in gzip.open(f"{D}/curve2x_curves.jsonl.gz","rt"):
        m=line[9:60].split('"')[0]
        if m in need: recs[m]=json.loads(line)
    agree=0; dis=[]; strat=collections.Counter()
    for r in sample:
        rec=recs[r["mint"]]; pool=L.pool_prepare(rec.get("pool")) if rec.get("pool") else None; x=r["lab"][P]
        ref=x.get("status") if x.get("status")!="OK" else (x["15M"]["state"] or "UNAVAILABLE")
        got=independent(rec,r["i"],r["ts"],N,H,pool=pool)
        if got=="UNAVAILABLE_OR_RESOLVED": got="UNAVAILABLE"
        ok=(got==ref); agree+=ok; strat[(r["day"],r["landmark"],bool(x.get("migrated_in_window")),ref)]+=1
        if not ok and len(dis)<20: dis.append(dict(mint_id=r["mint"][:6]+"..",landmark=r["landmark"],ref=ref,got=got))
    res=dict(label="HISTORICAL_REMEDIATION_NOT_SEALED",cases=len(sample),strata=len(strat),agree=agree,LABEL_AGREEMENT=agree/len(sample),disagreements=dis)
    json.dump(res,open(f"{OUT}/label_check.json","w"),indent=1); print(json.dumps({k:v for k,v in res.items() if k!="disagreements"}),dis[:5])
if __name__=="__main__": main()
