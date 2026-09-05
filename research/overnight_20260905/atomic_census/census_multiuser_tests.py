"""Teste sintetice pentru excluderea multi-user PER TOKEN (spec): (a) un utilizator, un token => pastrat; (b) doi utilizatori pe ACELASI token in aceeasi tranzactie => exclus; (c) utilizatori diferiti pe token-uri DIFERITE => pastrat (users_in_tx agregat NU se foloseste)."""
import sys,json,collections; sys.path.insert(0,'research/overnight_20260905/atomic_census'); import census_analyze as CA
def mk(user,tok,users_for_token,users_in_tx):
    m=dict(base_mint=tok,quote_mint="So11111111111111111111111111111111111111112",orientation="STRICT",canonical=False,token_mint=tok)
    ev=[dict(pool="P1",user=user,is_buy=1,base=100,user_quote=1000,rb_pre=10**6,rq_pre=10**6,rb_post=10**6-100,rq_post=10**6+1000,inv_ok=True,k=0,meta=m),dict(pool="P2",user=user,is_buy=0,base=100,user_quote=1100,rb_pre=10**6,rq_pre=10**6,rb_post=10**6+100,rq_post=10**6-1100,inv_ok=True,k=1,meta=m)]
    return dict(events=ev,duplicate_event_keys=False,unknown_events_in_tx=0,users_in_tx=users_in_tx,users_for_token=users_for_token)
res={}
res["a_single_user_kept"]=CA.classify(mk("U1","T1",1,1))[0]=="EXACT"
res["b_two_users_same_token_excluded"]=CA.classify(mk("U1","T1",2,2))==("REJECT","MULTI_USER_SAME_TOKEN_IN_TX")
res["c_different_users_different_tokens_kept"]=CA.classify(mk("U1","T1",1,2))[0]=="EXACT"   # users_in_tx=2 (alt token), dar users_for_token=1 => pastrat
res["d_helper_semantics"]=(CA.multi_user_same_token(1) is False and CA.multi_user_same_token(2) is True and CA.multi_user_same_token(None) is False)
# scanner: numarul se calculeaza per (tranzactie, token) — verificare structurala pe sursa
src=open("research/overnight_20260905/atomic_census/census_scan.py").read(); res["scanner_counts_users_per_token"]=("users_per_token[tok].add(d[\"user\"])" in src and "users_for_token=len(users_per_token[tok])" in src and "or True" not in src)
print(json.dumps(res,indent=1)); print("MULTIUSER_TESTS =","PASS" if all(res.values()) else "FAIL")
