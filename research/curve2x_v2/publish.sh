#!/usr/bin/env bash
# Publicare sanitizata (COMPLIANCE_ONLY: token exclusiv din GITHUB_TOKEN sau gh auth; fara cai de fisiere cu secrete) a CURVE2X V2 in repo-ul de review (clona temporara independenta; NICIODATA remote pe failtax). Token citit din fisier in variabila, niciodata afisat.
set -euo pipefail; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; SRC="$ROOT/research/curve2x_v2"; TMP="${TMPDIR_PUB:-$(mktemp -d)}"
BR="review/curve2x-remediation-20260905"; BASE="review/atomic-remediation-20260904"; REPO="corchra28/failtax-research-review"
GH_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || true)}"; [ -n "$GH_TOKEN" ] || { echo "TOKEN_MISSING (seteaza GITHUB_TOKEN sau gh auth login)"; exit 2; }
rm -rf "$TMP"
if ! git clone -q --depth 1 --branch "$BR" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>/dev/null; then
  git clone -q --depth 1 --branch "$BASE" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>&1 | sed "s/${GH_TOKEN}/***/g"; cd "$TMP"; git checkout -q -b "$BR"
fi
cd "$TMP"; git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git"
rm -rf research/curve2x_v2; mkdir -p research/curve2x_v2; cd "$SRC"
# include: cod, teste, spec inghetat, rezultate agregate, model card, tabele, ablatiuni, terminal summary, automatizare, SHA256SUMS, SOURCE_COMMIT. Exclude: cache-uri, semnale cu ID, sqlite, jurnale, model cu ID-uri (model_artifact contine doar parametri numerici, fara ID-uri -> INCLUS).
mapfile -t INC < "$SRC/published_files.txt"
for f in "${INC[@]}"; do [ -f "$f" ] && cp -p "$f" "$TMP/research/curve2x_v2/" || echo "SKIP_MISSING $f"; done
cd "$ROOT"; git rev-parse HEAD > "$TMP/research/curve2x_v2/SOURCE_COMMIT.txt"; cd "$TMP"
git add -A; git -c user.name="failtax-review" -c user.email="review@users.noreply.github.com" commit -q -m "CURVE2X V2 (HISTORICAL_REMEDIATION_NOT_SEALED) ${PUB_MSG:-update}; source commit $(cat research/curve2x_v2/SOURCE_COMMIT.txt)"
git push -q origin "$BR" 2>&1 | sed "s/${GH_TOKEN}/***/g"; echo "REVIEW_COMMIT=$(git rev-parse HEAD)"; git remote set-url origin "https://github.com/${REPO}.git"
