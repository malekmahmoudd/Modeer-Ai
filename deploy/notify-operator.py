"""Send an operator-supplied, content-free host event; no third-party packages."""
import json
import os
import sys
import urllib.request


def main(message):
    channels = []
    if url := os.environ.get("ALERT_WEBHOOK_URL"):
        channels.append((url, {"content": message, "text": message}))
    token, chat = os.environ.get("ALERT_TELEGRAM_BOT_TOKEN"), os.environ.get("ALERT_TELEGRAM_CHAT_ID")
    if token and chat:
        channels.append((f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat, "text": message}))
    delivered = False
    for url, payload in channels:
        try:
            request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=10) as response:
                delivered = 200 <= response.status < 300 or delivered
        except Exception as exc:
            print(f"Operator alert failed ({type(exc).__name__})", file=sys.stderr)
    return 0 if delivered else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
