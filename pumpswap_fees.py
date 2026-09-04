"""pumpswap_fees.py v1.0.0 — taxe dinamice PumpSwap dupa tier de market cap (sursa: pump-public-docs/docs/fees.png,
transcris 2026-09-01; verificat pe tranzactii reale). mcap_sol = (quote_vault + virtual_quote_reserves) * base_supply / base_vault.
Taxele (creator, protocol) se deduc din quote in afara vault-ului; LP ramane in vault. Toate in bp."""
# (prag_inferior_mcap_SOL, creator_bp, protocol_bp, lp_bp)
TIERS=[(0,30,93,2),(420,95,5,20),(1470,90,5,20),(2460,85,5,20),(3440,80,5,20),(4420,75,5,20),(9820,70,5,20),
       (14740,65,5,20),(19650,60,5,20),(24560,55,5,20),(29470,50,5,20),(34380,45,5,20),(39300,40,5,20),(44210,35,5,20),
       (49120,30,5,20),(54030,27.5,5,20),(58940,25,5,20),(63860,22.5,5,20),(68770,20,5,20),(73681,17.5,5,20),
       (78590,15,5,20),(83500,12.5,5,20),(88400,10,5,20),(93330,7.5,5,20),(98240,5,5,20)]
def mcap_sol(rb,rq,vq,supply): return (rq+vq)*supply/rb/1e9
def tier(mcap):
    t=TIERS[0]
    for x in TIERS:
        if mcap>=x[0]: t=x
    return {"creator_bp":t[1],"protocol_bp":t[2],"lp_bp":t[3],"total_bp":t[1]+t[2]+t[3],"tier_floor_sol":t[0]}
def fees_for(rb,rq,vq,supply): return tier(mcap_sol(rb,rq,vq,supply))
