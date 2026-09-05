#!/usr/bin/env bash
# Publicare sanitizata a CURVE2X V2 in repo-ul de review (clona temporara independenta; NICIODATA remote pe failtax). Token citit din fisier in variabila, niciodata afisat.
set -euo pipefail; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; SRC="$ROOT/research/curve2x_v2"; TMP="${TMPDIR_PUB:-/tmp/claude-1000/-home-rares/9402e14b-8644-49bd-ba9f-068396501bcc/scratchpad/review_pub}"
BR="review/curve2x-remediation-20260905"; BASE="review/atomic-remediation-20260904"; REPO="corchra28/failtax-research-review"
GH_TOKEN="$(grep -oE 'gh[pousr]_[A-Za-z0-9]{20,}' "/home/rares/Desktop/env github token" | head -1)"; [ -n "$GH_TOKEN" ] || { echo "TOKEN_MISSING"; exit 2; }
rm -rf "$TMP"; git clone -q --depth 1 --branch "$BASE" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>&1 | sed "s/${GH_TOKEN}/***/g"
cd "$TMP"; git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git"; git checkout -q -b "$BR"
mkdir -p research/curve2x_v2; cd "$SRC"
# include: cod, teste, spec inghetat, rezultate agregate, model card, tabele, ablatiuni, terminal summary, automatizare, SHA256SUMS, SOURCE_COMMIT. Exclude: cache-uri, semnale cu ID, sqlite, jurnale, model cu ID-uri (model_artifact contine doar parametri numerici, fara ID-uri -> INCLUS).
INC=(curve2x_lib.py tape_pass.py build_dataset.py model_stage.py test_curve2x.py label_check.py leakage_mutation.py determinism_check.py freeze.py make_docs.py publish_prep.py publish.sh curve2x_train.py curve2x_replay.py curve2x_paper_watcher.py curve2x_status.py curve2x_supervisor.sh curve2x-paper.service.example schema.sql config.example.json README_AUTOMATION.md frozen_spec.json amendments.md audit_v1.md audit_v1.json build_manifest.json test_results.json label_check.json leakage_mutation.json determinism_check.json replay_check.json results_public.json model_card.md calibration_tables.csv ablations.csv policy_grid_cal.csv terminal_summary.txt final_summary.json model_artifact.json reproducibility_manifest.json SHA256SUMS.txt TAPE_SHA256SUMS.txt)
for f in "${INC[@]}"; do [ -f "$f" ] && cp -p "$f" "$TMP/research/curve2x_v2/" || echo "SKIP_MISSING $f"; done
cd "$ROOT"; git rev-parse HEAD > "$TMP/research/curve2x_v2/SOURCE_COMMIT.txt"; cd "$TMP"
git add -A; git -c user.name="failtax-review" -c user.email="review@users.noreply.github.com" commit -q -m "CURVE2X V2 remediation (HISTORICAL_REMEDIATION_NOT_SEALED): first-passage labels, progress landmarks, one decision per mint, paper-only replay automation; source commit $(cat research/curve2x_v2/SOURCE_COMMIT.txt)"
git push -q origin "$BR" 2>&1 | sed "s/${GH_TOKEN}/***/g"; echo "REVIEW_COMMIT=$(git rev-parse HEAD)"; git remote set-url origin "https://github.com/${REPO}.git"
