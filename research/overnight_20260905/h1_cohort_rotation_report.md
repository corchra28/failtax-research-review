# H1 — COHORT_ROTATION_V2 — POST_HOC_HISTORICAL_RESEARCH
VERDICT = FAIL

Praguri DEV inghetate (thresholds_frozen.json): {"selectivity_threshold_prior_mints": 6.0, "q3_rotation_score": 110.7831835865112, "n_dev_eligible": 235}
Eligibile VAL+CONF: 670; semnale N = 54 pe 54 mint-uri; DEV (descriptiv) N = 50, EV = -0.00661

| Set | N | EV SOL | mediana | PF | win | ex-best-1% | max cota mint | EV 09-03 | EV 09-04 |
|---|---|---|---|---|---|---|---|---|---|
| SEMNALE | 54 | -0.01364 | -0.00731 | 0.536 | 0.370 | -0.01723 | 0.208 | -0.01288 | -0.01743 |
| matched | 54 | -0.01347 | -0.00131 | 0.621 | 0.463 | -0.01862 | 0.217 | -0.00613 | -0.05018 |
| complement | 616 | -0.00601 | -0.00092 | 0.649 | 0.336 | -0.00872 | 0.060 | -0.00613 | -0.00569 |
| neconditionat eligibil | 670 | -0.00663 | -0.00095 | 0.634 | 0.339 | -0.00912 | 0.053 | -0.00674 | -0.00631 |
| cost x1.25 | 54 | -0.01501 | -0.00882 | 0.502 | 0.352 | -0.01858 | 0.213 | -0.01425 | -0.01882 |
| latenta +2 s | 54 | -0.00894 | -0.00510 | 0.695 | 0.426 | -0.01311 | 0.193 | -0.00793 | -0.01396 |
| 120 s (descriptiv) | 49 | -0.01775 | -0.00710 | 0.583 | 0.408 | -0.02201 | 0.154 | -0.01060 | -0.04951 |

Bootstrap 10.000 (stratificat pe zi, mint-uri reesantionate): CI95 corectat (alpha/3) = [-0.03270863672222221, 0.006237918222222218], CI95 brut = [-0.029413933351851853, 0.002661263685185184], p brut (unilateral) = 0.9513, p Bonferroni = 1.0
Poarta: {"N50": true, "mints20": true, "EV": false, "PF": false, "CI_low": false, "p": false, "both_days": false, "vs_matched": false, "vs_complement": false, "exb1pct": false, "mint_share": false, "cost125": false, "lat2": false, "no_violations": true}
Adversarial: {"top5_winners": [["6166838b0c9fbdfb", "2026-09-03", 0.17671], ["695424719e116bb5", "2026-09-03", 0.11299], ["4eeac487ba5e344b", "2026-09-03", 0.08356], ["2c822288f6ab68f2", "2026-09-03", 0.05815], ["f8ee1e6641bd2295", "2026-09-04", 0.05721]], "top5_losers": [["c64e95da1c5b1713", "2026-09-03", -0.0914], ["979c8d9136d3b4c2", "2026-09-03", -0.11257], ["d016139da187458c", "2026-09-04", -0.1133], ["38c0f1918b736a56", "2026-09-03", -0.1429], ["89176739958b20af", "2026-09-03", -0.16789]], "ex_best_1pct_EV": -0.017230881320754718, "ex_best_3_EV": -0.02176038617647059, "leave_one_day_out": {"2026-09-03": -0.017432170555555557, "2026-09-04": -0.01288090037777778}, "leave_one_mint_out_min_EV": -0.017230881320754718, "rank_corr_feature_vs_residual_pnl_VAL_CONF": -0.08001828553462795, "rank_corr_feature_vs_raw_pnl_VAL_CONF": -0.035634030365438385}

Limitare counterfactuala directionala: tranzactiile ulterioare ale altora sunt aplicate pe starea observata, nu pe starea modificata de pozitia noastra (overlay static). Fara txIndex: intrarea/iesirea dupa toate evenimentele cu ts <= X (conservator). Starile neancorate si rupturile de lant sunt excluse.