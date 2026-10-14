#!/usr/bin/env bash
# Public FanCue acceptance smoke test.
# Usage:
#   FANCUE_API_BASE_URL=https://fancue-api-o4r1.onrender.com bash scripts/public-smoke-test.sh
#
# This verifies HTTP surface and browser-origin CORS preflight only. It deliberately
# does not fabricate a catch-up payload: use the returned GET /matches fixture ID
# to run a real POST /catchup through the frontend or a reviewed JSON request.
set -euo pipefail

API_BASE="${FANCUE_API_BASE_URL:-https://fancue-api-o4r1.onrender.com}"
FRONTEND_ORIGIN="${FANCUE_FRONTEND_ORIGIN:-https://fan-cue.vercel.app}"

printf 'FanCue public smoke test\nAPI: %s\nOrigin: %s\n\n' "$API_BASE" "$FRONTEND_ORIGIN"

request() {
  local label="$1"
  local url="$2"
  local out status
  out="$(mktemp)"
  status="$(curl --connect-timeout 10 --max-time 90 -sS -o "$out" -w '%{http_code}' "$url")" || {
    printf 'FAIL %-16s transport error\n' "$label"
    rm -f "$out"
    return 1
  }
  printf '%-16s HTTP %s\n' "$label" "$status"
  if [[ "$status" != "200" ]]; then
    cat "$out"
    rm -f "$out"
    return 1
  fi
  cat "$out"
  printf '\n'
  rm -f "$out"
}

request healthz "$API_BASE/healthz"
request readyz "$API_BASE/readyz"

matches="$(mktemp)"
status="$(curl --connect-timeout 10 --max-time 90 -sS -o "$matches" -w '%{http_code}' "$API_BASE/matches")"
printf '%-16s HTTP %s\n' matches "$status"
if [[ "$status" != "200" ]]; then cat "$matches"; rm -f "$matches"; exit 1; fi

python - "$matches" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
matches = data.get("matches", []) if isinstance(data, dict) else []
print(f"available historical/API matches: {len(matches)}")
if not matches:
    raise SystemExit("FAIL: API returned no matches; inspect /readyz and fixture provisioning")
for item in matches[:3]:
    print(f"  match_id={item.get('match_id')} | name={item.get('name')}")
PY
rm -f "$matches"

headers="$(mktemp)"
status="$(curl --connect-timeout 10 --max-time 30 -sS -D "$headers" -o /dev/null -w '%{http_code}' \
  -X OPTIONS "$API_BASE/catchup" \
  -H "Origin: $FRONTEND_ORIGIN" \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type')"
printf 'cors preflight    HTTP %s\n' "$status"
if [[ "$status" != "200" && "$status" != "204" ]]; then
  cat "$headers"
  rm -f "$headers"
  exit 1
fi
if ! grep -qiF "access-control-allow-origin: $FRONTEND_ORIGIN" "$headers"; then
  printf 'FAIL: exact Access-Control-Allow-Origin header missing\n'
  cat "$headers"
  rm -f "$headers"
  exit 1
fi
printf 'PASS: CORS allows the configured frontend origin.\n'
rm -f "$headers"

printf '\nHTTP smoke checks passed. This is not an end-to-end catch-up test.\n'
printf 'Next: use the frontend to run a real interval and inspect explanation.generation_mode, explanation.verification_status, score delta, evidence, and browser console.\n'
