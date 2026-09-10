#!/usr/bin/env sh
# Notice that Modeer has stopped answering, and say so.
#
# The application alerts on its own errors and on provider quota, but a process
# that has died cannot tell you it has died. This is the outside check.
#
# Run it from cron every few minutes:
#
#   */5 * * * * MODEER_URL=https://modeer.example \
#               ALERT_WEBHOOK_URL=https://... \
#               /srv/modeer/deploy/watchdog.sh >> /var/log/modeer-watchdog.log 2>&1
#
# WHERE you run it decides what it can catch:
#   - on the app host: catches the container dying, the app hanging, the
#     database being unreachable. Not the host dying or losing its network.
#   - somewhere else (another VPS, a home machine, a free uptime service):
#     catches all of the above plus the host itself.
# Running it on the app host is much better than nothing and takes one line.
# A second copy elsewhere is what makes it complete.
#
# Alerts only on a CHANGE of state, so a long outage is one message and its
# recovery is another, rather than one message every five minutes.
set -eu

URL="${MODEER_URL:-http://localhost:8000}"
STATE_FILE="${MODEER_WATCHDOG_STATE:-/tmp/modeer-watchdog.state}"
TIMEOUT="${MODEER_WATCHDOG_TIMEOUT:-15}"
WEBHOOK="${ALERT_WEBHOOK_URL:-}"
TG_TOKEN="${ALERT_TELEGRAM_BOT_TOKEN:-}"
TG_CHAT="${ALERT_TELEGRAM_CHAT_ID:-}"

send() {
  message="$1"
  echo "$(date -u +%FT%TZ) $message"
  if [ -n "$WEBHOOK" ]; then
    body=$(printf '{"content":%s,"text":%s}' "\"$message\"" "\"$message\"")
    curl -fsS -m "$TIMEOUT" -H 'Content-Type: application/json' \
      -d "$body" "$WEBHOOK" >/dev/null 2>&1 || echo "  (webhook delivery failed)"
  fi
  if [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ]; then
    curl -fsS -m "$TIMEOUT" \
      -d "chat_id=$TG_CHAT" --data-urlencode "text=$message" \
      "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1 \
      || echo "  (telegram delivery failed)"
  fi
}

previous="up"
[ -f "$STATE_FILE" ] && previous="$(cat "$STATE_FILE")"

# --fail makes curl exit non-zero on 5xx, which is what "degraded" looks like.
if body="$(curl -fsS -m "$TIMEOUT" "$URL/api/health" 2>/dev/null)"; then
  case "$body" in
    *'"status":"ok"'*) current="up" ;;
    *)                 current="degraded" ;;
  esac
else
  current="down"
fi

if [ "$current" != "$previous" ]; then
  case "$current" in
    up)       send "Modeer RECOVERED: $URL is answering normally again." ;;
    degraded) send "Modeer DEGRADED: $URL answered but reports a problem. Check /api/health/detail." ;;
    down)     send "Modeer DOWN: $URL did not answer within ${TIMEOUT}s." ;;
  esac
fi

printf '%s' "$current" > "$STATE_FILE"
[ "$current" = "up" ] || exit 1
