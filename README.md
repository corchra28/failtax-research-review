# failtax-research-review — external review bundle (2026-09-04)

Purpose: **external, independent review only**. Historical paper research on PumpSwap BOOST migrations (2026-09-01..04). No live trading, no strategy in production, no capital involved. This repository carries no project history: it contains only the review package.

- `research/external_review_bundle/` — the complete package (README, data dictionary, pool master, point-in-time feature panel, exact outcomes, shadow ledger, regime blocks, executed trades, summaries, trial ledger, integrity checks, casebook, reproduction code, `validate_bundle.py`).
- `research/external_review_bundle.tar.gz` — the same package as one archive. SHA-256: `43b3a032403694894241bdfb055bbae44174f8a8322bbb5ca7b195239115b0b7`
- `research/external_review_bundle_manifest.json` — SHA-256 and byte size of every file in the package.

BUNDLE_VALIDATION = PASS (`python research/external_review_bundle/validate_bundle.py research/external_review_bundle`).

The package contains no private keys, API tokens, environment variables, private configuration or raw on-chain addresses: mint, pool and wallet identifiers are deterministic SHA-256 hashes (namespace `external-review-v1`), joinable across files but not invertible. Regime verdict under the frozen specification: REGIME_GATE_INSUFFICIENT_SAMPLE; global research verdict: NO_VERIFIED_EDGE_IN_EXISTING_DATA. Nothing here is a claim of profitability.
