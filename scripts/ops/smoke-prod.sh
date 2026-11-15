#!/usr/bin/env bash
# Production smoke test: checks the deployed API end to end with the public demo account.
#
# Required environment:
#   SMOKE_EMAIL     demo account email (public by design, still never hardcoded here)
#   SMOKE_PASSWORD  demo account password
# Requires: curl, jq. Exit code 0 when every check passes, 1 otherwise.
# The access token is never printed.

set -u

API_URL="https://api.chimeraflow.linguasolution.com"
WEB_ORIGIN="https://chimeraflow.linguasolution.com"
EXPECTED_PREDEFINED_RULES=5

missing=""
[ -n "${SMOKE_EMAIL:-}" ] || missing="${missing} SMOKE_EMAIL"
[ -n "${SMOKE_PASSWORD:-}" ] || missing="${missing} SMOKE_PASSWORD"
if [ -n "$missing" ]; then
  echo "Missing required environment variable(s):${missing} (demo account credentials)" >&2
  exit 2
fi
for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing required tool: ${tool}" >&2; exit 2; }
done

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
body="${workdir}/body.json"
headers="${workdir}/headers.txt"
auth_header="${workdir}/auth.txt"

passed=0
failed=0
failures=()

pass() { passed=$((passed + 1)); echo "[ OK ] $1"; }
fail() { failed=$((failed + 1)); failures+=("$1"); echo "[FAIL] $1"; }

# http METHOD PATH [extra curl args...]; sets $status, writes $body and $headers
http() {
  local method="$1" path="$2"
  shift 2
  status=$(curl -s -o "$body" -D "$headers" -w '%{http_code}' --max-time 30 -X "$method" "$@" "${API_URL}${path}" || true)
  status="${status:-000}"
}

expect_status() { # label expected
  if [ "$status" = "$2" ]; then pass "$1 (HTTP $status)"; else fail "$1: expected HTTP $2, got $status"; fi
}

# 1. Health
http GET /health
expect_status "GET /health" 200
if [ "$(jq -r '.status // empty' "$body" 2>/dev/null)" = "ok" ]; then pass "health status is ok"; else fail "health status is not ok"; fi

# 2. Interactive docs must not be published
http GET /docs
expect_status "GET /docs is not exposed" 404

# 3. Protected routes refuse anonymous requests
http GET /api/v1/sources
expect_status "GET /api/v1/sources without token" 401

# 4. Login (the body goes through a temp file so the password never appears in a process list)
jq -n --arg email "$SMOKE_EMAIL" --arg password "$SMOKE_PASSWORD" '{email: $email, password: $password}' > "${workdir}/login.json"
http POST /api/v1/auth/login -H 'Content-Type: application/json' --data-binary "@${workdir}/login.json"
expect_status "POST /api/v1/auth/login" 200
token=$(jq -r '.access_token // empty' "$body" 2>/dev/null)
if [ -z "$token" ]; then
  fail "login returned no access token"
  echo
  echo "Smoke test aborted: ${passed} passed, ${failed} failed"
  printf ' - %s\n' "${failures[@]}"
  exit 1
fi
printf 'Authorization: Bearer %s' "$token" > "$auth_header"
unset token
rm -f "${workdir}/login.json"

# 5. Authenticated identity
http GET /api/v1/auth/me -H "@${auth_header}"
expect_status "GET /api/v1/auth/me" 200
if [ "$(jq -r '.email // empty' "$body" 2>/dev/null)" = "$SMOKE_EMAIL" ]; then pass "/auth/me returns the demo account"; else fail "/auth/me does not return the demo account"; fi

# 6. Sources: all four connectors healthy
http GET /api/v1/sources -H "@${auth_header}"
expect_status "GET /api/v1/sources" 200
source_count=$(jq -r '.sources | length' "$body" 2>/dev/null || echo 0)
not_ok=$(jq -r '[.sources[] | select(.status != "ok")] | length' "$body" 2>/dev/null || echo 1)
if [ "$source_count" = "4" ] && [ "$not_ok" = "0" ]; then
  pass "4 sources, all ok"
else
  fail "sources: expected 4 all ok, got ${source_count} with ${not_ok} not ok"
fi

# 7. Predefined rules
http GET /api/v1/rules/predefined -H "@${auth_header}"
expect_status "GET /api/v1/rules/predefined" 200
rule_count=$(jq -r 'length' "$body" 2>/dev/null || echo "?")
if [ "$rule_count" = "$EXPECTED_PREDEFINED_RULES" ]; then
  pass "${rule_count} predefined rules"
else
  fail "predefined rules: expected ${EXPECTED_PREDEFINED_RULES}, got ${rule_count}"
fi

# 8. Correlation engine run
http POST /api/v1/correlations/execute -H "@${auth_header}"
expect_status "POST /api/v1/correlations/execute" 200
run_status=$(jq -r '.status // empty' "$body" 2>/dev/null)
rules_failed=$(jq -r '.rules_failed // "?"' "$body" 2>/dev/null)
rules_executed=$(jq -r '.rules_executed // "?"' "$body" 2>/dev/null)
found=$(jq -r '.correlations_found // "?"' "$body" 2>/dev/null)
if [ "$run_status" = "success" ] && [ "$rules_failed" = "0" ]; then
  pass "execution success: ${rules_executed} rules executed, 0 failed, ${found} correlations"
else
  fail "execution: status=${run_status:-none}, rules_failed=${rules_failed}"
fi

# 9. Correlations listing
http GET /api/v1/correlations -H "@${auth_header}"
expect_status "GET /api/v1/correlations" 200
if [ "$(jq -r 'type' "$body" 2>/dev/null)" = "array" ]; then
  pass "$(jq -r 'length' "$body") correlations listed"
else
  fail "correlations response is not a JSON array"
fi

# 10. CORS: the frontend origin is allowed, another origin is not
http OPTIONS /api/v1/sources -H "Origin: ${WEB_ORIGIN}" -H 'Access-Control-Request-Method: GET' -H 'Access-Control-Request-Headers: authorization'
allowed=$(grep -i '^access-control-allow-origin:' "$headers" | tr -d '\r' | awk '{print $2}')
if [ "$status" = "200" ] && [ "$allowed" = "$WEB_ORIGIN" ]; then
  pass "CORS preflight allows ${WEB_ORIGIN}"
else
  fail "CORS preflight for ${WEB_ORIGIN}: HTTP ${status}, allow-origin='${allowed}'"
fi
http OPTIONS /api/v1/sources -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: GET'
foreign=$(grep -i '^access-control-allow-origin:' "$headers" | tr -d '\r' | awk '{print $2}')
if [ -z "$foreign" ]; then pass "CORS preflight refuses a foreign origin"; else fail "CORS allows a foreign origin ('${foreign}')"; fi

echo
echo "Smoke test: ${passed} passed, ${failed} failed"
if [ "$failed" -gt 0 ]; then
  printf ' - %s\n' "${failures[@]}"
  exit 1
fi
