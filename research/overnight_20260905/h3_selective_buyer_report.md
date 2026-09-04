# H3 — SELECTIVE_BUYER_QUALITY_V1 — POST_HOC_HISTORICAL_RESEARCH
VERDICT = FAIL

Praguri DEV inghetate (thresholds_frozen.json): {"q3_quality": 0.6567375886524823, "n_dev_eligible": 235}
Eligibile VAL+CONF: 670; semnale N = 57 pe 57 mint-uri; DEV (descriptiv) N = 49, EV = -0.01765

| Set | N | EV SOL | mediana | PF | win | ex-best-1% | max cota mint | EV 09-03 | EV 09-04 |
|---|---|---|---|---|---|---|---|---|---|
| SEMNALE | 57 | 0.00484 | 0.00022 | 1.282 | 0.509 | 0.00177 | 0.141 | 0.00378 | 0.01583 |
| matched | 57 | -0.00283 | 0.00270 | 0.912 | 0.561 | -0.00751 | 0.155 | 0.00327 | -0.06630 |
| complement | 613 | -0.00770 | -0.00095 | 0.577 | 0.323 | -0.01043 | 0.063 | -0.00796 | -0.00697 |
| neconditionat eligibil | 670 | -0.00663 | -0.00095 | 0.634 | 0.339 | -0.00912 | 0.053 | -0.00674 | -0.00631 |
| cost x1.25 | 57 | 0.00325 | -0.00133 | 1.182 | 0.491 | 0.00021 | 0.145 | 0.00220 | 0.01425 |
| latenta +2 s | 57 | 0.00899 | 0.00578 | 1.543 | 0.561 | 0.00535 | 0.146 | 0.00731 | 0.02641 |
| 120 s (descriptiv) | 45 | 0.00216 | 0.00464 | 1.086 | 0.533 | -0.00203 | 0.151 | -0.00032 | 0.02200 |

Bootstrap 10.000 (stratificat pe zi, mint-uri reesantionate): CI95 corectat (alpha/3) = [-0.013710104017543861, 0.022694704350877185], CI95 brut = [-0.01042566580701754, 0.01956102826315789], p brut (unilateral) = 0.2637, p Bonferroni = 0.7910999999999999
Poarta: {"N50": true, "mints20": true, "EV": true, "PF": false, "CI_low": false, "p": false, "both_days": true, "vs_matched": true, "vs_complement": true, "exb1pct": true, "mint_share": true, "cost125": true, "lat2": true, "no_violations": true}
Adversarial: {"top5_winners": [["6166838b0c9fbdfb", "2026-09-03", 0.17671], ["695424719e116bb5", "2026-09-03", 0.11299], ["0ca6bab3d80122c4", "2026-09-03", 0.11045], ["f9bb1cb76f7e9da0", "2026-09-03", 0.10265], ["4eeac487ba5e344b", "2026-09-03", 0.08356]], "top5_losers": [["f2fc4a465b341730", "2026-09-03", -0.05351], ["be0910bf736ce2e2", "2026-09-03", -0.06353], ["4985a96eb8bbbf47", "2026-09-03", -0.10607], ["979c8d9136d3b4c2", "2026-09-03", -0.11257], ["0d0bf6a27ef72a3c", "2026-09-03", -0.20345]], "ex_best_1pct_EV": 0.001768406839285714, "ex_best_3_EV": -0.0023037931111111114, "leave_one_day_out": {"2026-09-03": 0.015825427, "2026-09-04": 0.003780967423076923}, "leave_one_mint_out_min_EV": 0.001768406839285714, "rank_corr_feature_vs_residual_pnl_VAL_CONF": -0.04461464971361274, "rank_corr_feature_vs_raw_pnl_VAL_CONF": 0.004853965588044221}

Limitare counterfactuala directionala: tranzactiile ulterioare ale altora sunt aplicate pe starea observata, nu pe starea modificata de pozitia noastra (overlay static). Fara txIndex: intrarea/iesirea dupa toate evenimentele cu ts <= X (conservator). Starile neancorate si rupturile de lant sunt excluse.