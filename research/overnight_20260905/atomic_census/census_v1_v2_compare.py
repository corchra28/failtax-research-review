"""Comparatie V1 (users_in_tx agregat, neaplicat ca excludere) vs V2 (excludere multi-user PER TOKEN conform spec). Arata daca ciclul dominant (~+10,63 SOL) ramane inclus si de ce."""
import json,gzip,hashlib,collections
AC="research/overnight_20260905/atomic_census"; D="/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/derived"; LAMP=10**9; NS="external-review-v1"
def hid(v): return hashlib.sha256(f"{NS}:{v}".encode()).hexdigest()[:32]
V1=json.load(open(f"{AC}/v1/census_results.json")); V2=json.load(open(f"{AC}/census_results_v2.json")); M1=json.load(open(f"{AC}/v1/census_manifest.json")); M2=json.load(open(f"{AC}/census_manifest_v2.json"))
r1={ (json.loads(l)["sig"],json.loads(l)["user"],json.loads(l)["token"]):json.loads(l) for l in gzip.open(f"{D}/census_rows.jsonl.gz","rt")}
r2={ (json.loads(l)["sig"],json.loads(l)["user"],json.loads(l)["token"]):json.loads(l) for l in gzip.open(f"{D}/census_rows_v2.jsonl.gz","rt")}
ex1={k for k,v in r1.items() if v["cls"]=="EXACT"}; ex2={k for k,v in r2.items() if v["cls"]=="EXACT"}
removed=[r2[k] for k in ex1-ex2]; added=[r2[k] for k in ex2-ex1]
dom=max((r1[k] for k in ex1),key=lambda r:r["net_PRIMARY"]); dk=(dom["sig"],dom["user"],dom["token"]); dom2=r2.get(dk)
def sm(V,M):
    s=V.get("net_PRIMARY") or {}; return dict(N=M["EXACT_BASE_CONSERVED_CYCLES"],users=M["UNIQUE_USERS_HASHED"],tokens=M["UNIQUE_TOKENS"],total_net_sol=s.get("total"),EV=s.get("EV"),median=s.get("median"),PF=s.get("PF"),win_rate=s.get("win_rate"),by_day={d:(v or {}).get("EV") for d,v in (V.get("by_day") or {}).items()},by_day_N=M["by_day"],top_user_share=V.get("top_user_share"),top_token_share=V.get("top_token_share"),CI_user_day=(V.get("bootstrap_user_day") or {}).get("CI95"),CI_token_day=(V.get("bootstrap_token_day") or {}).get("CI95"),gate=V.get("gate"),verdict=V.get("verdict"),rejected=M.get("rejected"))
cmp=dict(V1=sm(V1,M1),V2=sm(V2,M2),cycles_removed_by_multi_user_rule=len(removed),cycles_added=len(added),removed_examples_hashed=[dict(sig_id=hid(r["sig"]),token_id=hid(r["token"]),users_for_token=r.get("users_for_token"),net_primary_sol=r["net_PRIMARY"]/LAMP,day=r["day"]) for r in sorted(removed,key=lambda r:-r["net_PRIMARY"])[:10]],removed_total_net_sol=sum(r["net_PRIMARY"] for r in removed)/LAMP,
    dominant_cycle=dict(sig_id=hid(dom["sig"]),user_id=hid(dom["user"]),token_id=hid(dom["token"]),day=dom["day"],net_primary_sol=dom["net_PRIMARY"]/LAMP,gross_sol=dom["gross"]/LAMP,paid_sol=dom["paid"]/LAMP,recv_sol=dom["recv"]/LAMP,n_swaps=dom["n_swaps"],users_in_tx_v1=dom.get("users_in_tx"),users_for_token_v2=(dom2 or {}).get("users_for_token"),retained_in_v2=(dk in ex2),why=("retinut: un singur utilizator distinct pe tokenul ciclului in tranzactie (users_for_token=1), base conservat exact, orientare stricta, invariante valide" if dk in ex2 else f"exclus: {(dom2 or {}).get('why')}")),
    FINAL_VERDICT_CHANGED=(V1.get("verdict")!=V2.get("verdict")))
json.dump(cmp,open(f"{AC}/census_v1_v2_comparison.json","w"),indent=1,default=str); print(json.dumps({k:v for k,v in cmp.items() if k not in ("removed_examples_hashed",)},default=str)[:2500])
