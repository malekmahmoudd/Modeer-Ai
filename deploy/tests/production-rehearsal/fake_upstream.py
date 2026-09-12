"""A scripted OpenAI-compatible model for the production rehearsal.

The backend runs its real provider code against this, so every way a reply can
end — finished, cut at the token cap, dropped mid-stream, refused — travels the
real path: provider -> runtime -> database -> Caddy -> browser. The phrase in
the person's latest message picks the script:

    qa-slow          a dozen words, one every 0.35s (proves the proxy streams)
    qa-truncate      two chunks, then finish_reason "length"
    qa-drop          half a reply, then the connection closes without finishing
    qa-fail          HTTP 503 before any text
    ...-once         (with drop or fail) misbehave the first time only, so a
                     retry of the same message succeeds
    qa-links         Markdown links, safe and unsafe
    qa-recall        says whether "Cairo" reached the prompt (context check)
    anything else    a short finished reply

Standard library only. Never used outside this rehearsal.
"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEEN: set[str] = set()


def event(content: str | None = None, finish: str | None = None) -> bytes:
    delta = {"content": content} if content is not None else {}
    body = {"choices": [{"delta": delta, "finish_reason": finish}]}
    return f"data: {json.dumps(body)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # the body ends when the connection closes

    def log_message(self, fmt, *args):  # quiet: prompts are not worth logging
        pass

    def do_POST(self):  # noqa: N802 - http.server's naming
        size = int(self.headers.get("content-length") or 0)
        messages = json.loads(self.rfile.read(size) or b"{}").get("messages", [])
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        misbehave = last not in SEEN or "once" not in last
        SEEN.add(last)

        if "qa-fail" in last and misbehave:
            self.send_response(503)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        send = self.wfile.write

        if "qa-slow" in last:
            sentence = "Here is a reply that arrives one word at a time through the proxy."
            for word in sentence.split():
                send(event(word + " "))
                self.wfile.flush()
                time.sleep(0.35)
        elif "qa-truncate" in last:
            send(event("This answer is long and "))
            send(event("runs out of room", "length"))
            return
        elif "qa-drop" in last and misbehave:
            send(event("Half an answer, "))
            self.wfile.flush()
            return  # connection closes: no finish reason, no [DONE]
        elif "qa-links" in last:
            send(
                event(
                    "Links: [Memory](/memory), [docs](https://example.com/docs), "
                    "[sneaky](//evil.example), [script](javascript:alert(1)) and "
                    "[slashes](/\\evil.example)."
                )
            )
        elif "qa-recall" in last:
            send(event("Recall: " + ("Cairo" if "Cairo" in system else "nothing saved") + "."))
        else:
            send(event("A short, useful reply."))
        send(event(None, "stop"))
        send(b"data: [DONE]\n\n")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
