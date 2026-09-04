# H2 — SELLER_OVERHANG_DECAY_V2 — POST_HOC_HISTORICAL_RESEARCH
VERDICT = INSUFFICIENT_CLEAN_SAMPLE

Praguri DEV inghetate (thresholds_frozen.json): {"q1_decay_ratio": 0.13251662129226568, "median_remaining_inventory": 0.8045609813569526, "n_dev_eligible": 92}
Eligibile VAL+CONF: 307; semnale N = 18 pe 18 mint-uri; DEV (descriptiv) N = 10, EV = 0.00230

| Set | N | EV SOL | mediana | PF | win | ex-best-1% | max cota mint | EV 09-03 | EV 09-04 |
|---|---|---|---|---|---|---|---|---|---|
| SEMNALE | 18 | 0.01376 | 0.00356 | 1.559 | 0.611 | -0.00069 | 0.376 | 0.01376 | n/a |
| matched | 18 | -0.00988 | 0.00084 | 0.732 | 0.556 | -0.01755 | 0.247 | -0.00988 | n/a |
| complement | 289 | -0.00712 | -0.00110 | 0.720 | 0.484 | -0.00840 | 0.033 | -0.00533 | -0.01341 |
| neconditionat eligibil | 307 | -0.00590 | -0.00071 | 0.768 | 0.492 | -0.00814 | 0.043 | -0.00392 | -0.01341 |
| cost x1.25 | 18 | 0.01207 | 0.00194 | 1.480 | 0.556 | -0.00228 | 0.382 | 0.01207 | n/a |
| latenta +2 s | 18 | 0.01769 | 0.00755 | 1.698 | 0.611 | 0.00197 | 0.368 | 0.01769 | n/a |
| 120 s (descriptiv) | 17 | 0.01624 | 0.00291 | 1.397 | 0.529 | -0.01292 | 0.497 | 0.01624 | n/a |

Bootstrap 10.000 (stratificat pe zi, mint-uri reesantionate): CI95 corectat (alpha/3) = [-0.03479239516666667, 0.07296064144444445], CI95 brut = [-0.02663498622222222, 0.06185644933333331], p brut (unilateral) = 0.2813, p Bonferroni = 0.8439
Poarta: null
Adversarial: {"top5_winners": [["0cd8b3b59707536c", "2026-09-03", 0.25934], ["e31d5be091d82e67", "2026-09-03", 0.22939], ["4eeac487ba5e344b", "2026-09-03", 0.08356], ["8aadb09d600a6fde", "2026-09-03", 0.04216], ["e1ef84c5bf125273", "2026-09-03", 0.02587]], "top5_losers": [["1e80b8bf17bea216", "2026-09-03", -0.04561], ["a7c2e011d7b74d87", "2026-09-03", -0.07916], ["55c5e259b5faaf12", "2026-09-03", -0.08778], ["c64e95da1c5b1713", "2026-09-03", -0.0914], ["413cb5113179604d", "2026-09-03", -0.12401]], "ex_best_1pct_EV": -0.0006908367647058828, "ex_best_3_EV": -0.021645728466666667, "leave_one_day_out": {"2026-09-03": null}, "leave_one_mint_out_min_EV": -0.0006908367647058828, "rank_corr_feature_vs_residual_pnl_VAL_CONF": 0.01704602480613211, "rank_corr_feature_vs_raw_pnl_VAL_CONF": -0.021836214497643894}

Limitare counterfactuala directionala: tranzactiile ulterioare ale altora sunt aplicate pe starea observata, nu pe starea modificata de pozitia noastra (overlay static). Fara txIndex: intrarea/iesirea dupa toate evenimentele cu ts <= X (conservator). Starile neancorate si rupturile de lant sunt excluse.