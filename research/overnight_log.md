
## 2026-09-04 20:54:54 EEST — stage 0 INTEGRITY
commit fe55a933f127c5f8c1e193a8b346889ef5b37a15; tape manifests SEP02/03/04 verified in audit; m_cache 7f38b246725e67d4…; regime cache 2842d7062cdffe07…; no SLOW PnL; RPC 0; validators PASS.

## 2026-09-04 21:00:30 EEST — stage 1 running; scripts for stages 2-6 written (commit 7c18db1 + pending)

## 2026-09-04 21:09:06 EEST — stages 2-6 complete
panel 946 rows (leakage PASS 200/200), outcomes OK 888/946, thresholds frozen from DEV (H1 q3 110.78, sel thr 6; H2 q1 0.1325, med rem 0.8046; H3 q3 0.6567), evaluation VAL+CONF: H1 FAIL (N54 EV -0.0136 PF 0.54), H2 INSUFFICIENT (N18), H3 FAIL (N57 EV +0.0048 PF 1.28 CI incl. 0), adversarial: determinism OK, no discrepancies, wallet-shuffle p 0.07 (H3), placebo +180 negative. Technical fix once: None-safe stats (no rule change).

## 2026-09-04 21:29:01 EEST — resume: protocol re-received; fixed queue already complete (commit 8ea20e68 / review 48c0abb5); integrity re-verified read-only; no stages repeated; no RPC.

## 2026-09-04 23:29:27 EEST — census scan 42.27M swaps (379 s), 5,945 candidate groups, 500 EXACT (all 2-swap), 1 DUST, 5,444 rejected non-strict orientation; economics: EV +0.0252 SOL/cycle, PF 295, win 8.2%, top user/token share 84% => NOT_CONFIRMED; persistence INSUFFICIENT (19 subsequent cycles); slow capture: 0 profitable states in frozen population; lead/lag: 99.6% of cycles reduced spread, 100% same-slot competition; S1 FAIL (N 33,638, EV -0.0067), S6 NOT_CONFIRMED (best pool = default), S7 NO_VALUE.

## 2026-09-04 23:34:23 EEST — S2 INSUFFICIENT (0 residual opps), S3 INSUFFICIENT (N=2), S4 INSUFFICIENT (N=23), S5 done, independent census agrees (500/500, gross lamport-exact, sample 100/100), property tests PASS (3000 cases), final docs + global Holm written.
