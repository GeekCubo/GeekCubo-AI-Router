#!/usr/bin/env bash
# Failover demo driver — runs the request loop the README GIF is built from.
#
# Run this in Terminal A while you record the screen. In Terminal B, when you
# want failover to happen, run:
#     scripts/demo_kill_openai.sh
#
# and watch the loop's output flip from `gpt-*` to `claude-*` mid-stream.
#
# Requires: jq, curl, a running GeekCubo server, and a sk-geek-* key.

set -euo pipefail

: "${GEEKCUBO_API_KEY:?Set GEEKCUBO_API_KEY to your sk-geek-* (printed in the server logs)}"
: "${GEEKCUBO_BASE_URL:=http://localhost:8000}"

# Sanity check
if ! curl -sf "$GEEKCUBO_BASE_URL/health" >/dev/null; then
  echo "✗ GeekCubo isn't responding at $GEEKCUBO_BASE_URL — start it first (docker compose up)"
  exit 1
fi

echo "▶ failover demo — Ctrl-C to stop"
echo "  base:  $GEEKCUBO_BASE_URL"
echo "  prompt: 'reply with just \"ok\"'"
echo

i=0
while true; do
  i=$((i+1))
  resp=$(curl -s -D /tmp/geekcubo-headers.txt "$GEEKCUBO_BASE_URL/v1/chat/completions" \
    -H "Authorization: Bearer $GEEKCUBO_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"auto","messages":[{"role":"user","content":"reply with just \"ok\""}],"temperature":0,"max_tokens":5}' \
    || echo '{}')

  resolved=$(grep -i '^x-geek-resolved-model' /tmp/geekcubo-headers.txt 2>/dev/null | awk '{print $2}' | tr -d '\r' || echo "?")
  cache=$(grep -i '^x-geek-cache' /tmp/geekcubo-headers.txt 2>/dev/null | awk '{print $2}' | tr -d '\r' || echo "?")
  text=$(echo "$resp" | jq -r '.choices[0].message.content // (.error.message // "ERR")' 2>/dev/null | head -c 60)

  printf "[%3d] %-12s  %-40s  %s\n" "$i" "${cache:-?}" "${resolved:-?}" "$text"
  sleep 1
done
