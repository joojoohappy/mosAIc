#!/usr/bin/env bash
# Smoke-test a deployed mosAIc website (preview, staging or production).
#
#   bash scripts/smoke.sh https://your-site.vercel.app
#   SMOKE_GENERATE=1 bash scripts/smoke.sh https://...   # also runs ONE real,
#                                                         # billable generation
#
# Read-only by default: it never calls the image model unless SMOKE_GENERATE=1.
# For a Vercel preview behind Deployment Protection, set VERCEL_BYPASS to the
# project's "Protection Bypass for Automation" secret. Without it, a protected
# deployment exits with code 3 and a message saying so.
set -uo pipefail
BASE=${1:?usage: smoke.sh <website-url>}
BASE=${BASE%/}
HDR=()
[ -n "${VERCEL_BYPASS:-}" ] && HDR=(-H "x-vercel-protection-bypass: $VERCEL_BYPASS")
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); printf '  ok    %s\n' "$1"; }
bad() { fail=$((fail+1)); printf '  FAIL  %s\n' "$1"; }
get() { curl -s "${HDR[@]}" -o "$TMP/body" -D "$TMP/head" -w '%{http_code}' --max-time 30 "$@"; }
protected() { # Vercel Deployment Protection: a 401/403 page or a redirect to its SSO
  case "$1" in
    401|403) grep -qi vercel "$TMP/body" 2>/dev/null ;;
    302|303|307|308) grep -qiE '^location: *https://(vercel\.com|[^/]*\.vercel\.(com|app))/(sso|login)' "$TMP/head" 2>/dev/null \
                       || grep -qiE '^location: .*_vercel_sso' "$TMP/head" 2>/dev/null ;;
    *) return 1 ;;
  esac
}
expect() { # name want-code url [grep-pattern]
  local code; code=$(get "$3")
  if protected "$code"; then bad "$1: blocked by Vercel Deployment Protection (set VERCEL_BYPASS)"; return; fi
  if [ "$code" != "$2" ]; then bad "$1: HTTP $code, want $2"; return; fi
  if [ -n "${4:-}" ] && ! grep -q -- "$4" "$TMP/body"; then bad "$1: body lacks $4"; return; fi
  ok "$1"
}

echo "smoke: $BASE"
code=$(get "$BASE/")
if protected "$code"; then
  echo "  This deployment is behind Vercel Deployment Protection (HTTP $code)."
  echo "  Set VERCEL_BYPASS to the project's \"Protection Bypass for Automation\" secret."
  exit 3
fi
expect "home page"                 200 "$BASE/"                    "mosAIc"
expect "privacy page"              200 "$BASE/privacy"             "隱私說明"
expect "terms page"                200 "$BASE/terms"               "使用條款"
expect "API health via website"    200 "$BASE/api/health"          '"ok":true'
if grep -q '"liveGeneration":true' "$TMP/body"; then echo "        (live generation is on)"
elif grep -q '"liveGeneration":false' "$TMP/body"; then
  echo "        (live generation is off: no model key, or no Blob store on Vercel)"
fi
expect "recipe list"               200 "$BASE/api/recipes"         '"recipes"'
cp "$TMP/body" "$TMP/recipes.json"
expect "recipe detail"             200 "$BASE/api/recipes/seed-01" '"id":"seed-01"'
expect "unknown recipe is 404"     404 "$BASE/api/recipes/seed-99" "unknown_recipe"
expect "unknown result is 404"     404 "$BASE/api/results/00000000000000000000000000000000" "unknown_result"
expect "API docs are not exposed"  404 "$BASE/api/docs"

code=$(get -X POST -F recipeId= "$BASE/api/generate")
[ "$code" = "400" ] && ok "generate validates input" || bad "generate validates input: HTTP $code"

if [ -n "${SMOKE_GENERATE:-}" ]; then
  ready=$(python3 -c "import json,sys; r=[x['id'] for x in json.load(open(sys.argv[1]))['recipes'] if x['tryReady']]; print(r[0] if r else '')" "$TMP/recipes.json")
  if [ -z "$ready" ]; then bad "real generation: no recipe has tryReady=true"; else
    python3 -c "import base64,sys; open(sys.argv[1],'wb').write(base64.b64decode('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDUooor4k+/CiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAP//Z'))" "$TMP/photo.jpg"
    code=$(get --max-time 90 -X POST -F "recipeId=$ready" -F "image=@$TMP/photo.jpg;type=image/jpeg" "$BASE/api/generate")
    rid=$(sed -n 's/.*"resultId":"\([0-9a-f]*\)".*/\1/p' "$TMP/body")
    if [ "$code" != "200" ] || [ -z "$rid" ]; then bad "real generation: HTTP $code $(head -c 200 "$TMP/body")"; else
      expect "result readable" 200 "$BASE/api/results/$rid" '"mode"'
      mode=$(sed -n 's/.*"mode":"\([a-z]*\)".*/\1/p' "$TMP/body")
      url=$(sed -n 's/.*"imageUrl":"\([^"]*\)".*/\1/p' "$TMP/body")
      echo "        mode=$mode"
      [ "$mode" = "live" ] && ok "real generation is live" || bad "real generation fell back to $mode"
      [ -n "$url" ] && expect "result image served" 200 "$BASE$url"
    fi
  fi
fi

echo; echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
