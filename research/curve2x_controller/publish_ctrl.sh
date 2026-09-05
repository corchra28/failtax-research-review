#!/usr/bin/env bash
# Publicare sanitizata a controller-ului (fara state/, fara cache-uri, fara adrese brute). Token exclusiv din GITHUB_TOKEN sau gh auth token.
set -euo pipefail; HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; TMP="${TMPDIR_PUB:-$(mktemp -d)}"; REPO="corchra28/failtax-research-review"; BR="review/curve2x-controller-20260905"; BASE="review/curve2x-v3-reclaim-20260905"
GH_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || true)}"; [ -n "$GH_TOKEN" ] || { echo "TOKEN_MISSING"; exit 2; }
rm -rf "$TMP"
if ! git clone -q --depth 1 --branch "$BR" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>/dev/null; then git clone -q --depth 1 --branch "$BASE" "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$TMP" 2>&1 | sed "s/${GH_TOKEN}/***/g"; cd "$TMP"; git checkout -q -b "$BR"; fi
cd "$TMP"; git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git"; rm -rf research/curve2x_controller; mkdir -p research/curve2x_controller
for f in controller_lib.py controller.py promote.py tests_controller.py prep_ctrl.py freeze_forward.py publish_ctrl.sh validate_public.py controller_spec.json forward_spec.json README.md champion.json test_results.json evaluation_report_public.json SHA256SUMS.txt .gitignore; do [ -f "$HERE/$f" ] && cp -p "$HERE/$f" "$TMP/research/curve2x_controller/" || echo "SKIP_MISSING $f"; done
(cd "$ROOT" && git rev-parse HEAD) > "$TMP/research/curve2x_controller/SOURCE_COMMIT.txt"; echo "${ORIGIN_COMMIT:-}" > "$TMP/research/curve2x_controller/ORIGIN_COMMIT.txt"
git add -A; git -c user.name="failtax-review" -c user.email="review@users.noreply.github.com" commit -q -m "CURVE2X controller (paper/shadow only) ${PUB_MSG:-update}; source commit $(cat research/curve2x_controller/SOURCE_COMMIT.txt)"
git push -q origin "$BR" 2>&1 | sed "s/${GH_TOKEN}/***/g"; echo "REVIEW_COMMIT=$(git rev-parse HEAD)"; git remote set-url origin "https://github.com/${REPO}.git"
