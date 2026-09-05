#!/usr/bin/env bash
set -euo pipefail; HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; TMP="${TMPDIR_PUB:-$(mktemp -d)}"; REPO="corchra28/failtax-research-review"; BR="review/wallet-flow-hazard-20260905"; BASE="review/curve2x-controller-20260905"
GH_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || true)}"; [ -n "$GH_TOKEN" ] || { echo "TOKEN_MISSING"; exit 2; }
rm -rf "$TMP"; if ! git clone -q --depth 1 --branch "$BR" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>/dev/null; then git clone -q --depth 1 --branch "$BASE" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>&1 | sed "s/${GH_TOKEN}/***/g"; cd "$TMP"; git checkout -q -b "$BR"; fi
cd "$TMP"; git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git"; rm -rf research/wallet_flow_hazard_v1; mkdir -p research/wallet_flow_hazard_v1
mapfile -t INC < "$HERE/published_files.txt"; for f in "${INC[@]}"; do [ -f "$HERE/$f" ] && cp -p "$HERE/$f" "$TMP/research/wallet_flow_hazard_v1/" || echo "SKIP_MISSING $f"; done
(cd "$ROOT" && git rev-parse HEAD) > "$TMP/research/wallet_flow_hazard_v1/SOURCE_COMMIT.txt"; git add -A; git -c user.name="failtax-review" -c user.email="review@users.noreply.github.com" commit -q -m "WALLET_FLOW_HAZARD_V1 (HISTORICAL_HYPOTHESIS_GENERATION_NOT_SEALED) ${PUB_MSG:-update}; source commit $(cat research/wallet_flow_hazard_v1/SOURCE_COMMIT.txt)"
git push -q origin "$BR" 2>&1 | sed "s/${GH_TOKEN}/***/g"; echo "REVIEW_COMMIT=$(git rev-parse HEAD)"; git remote set-url origin "https://github.com/${REPO}.git"
