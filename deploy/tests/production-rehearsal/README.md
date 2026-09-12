# Production rehearsal

The production images, run on this machine only, and checked in a real browser.

What is real: the backend image built from `requirements.lock`, running with
`ENVIRONMENT=production`; the frontend's production build; Caddy with
`deploy/Caddyfile` itself (HTTPS, security headers, the Content Security Policy,
streaming); PostgreSQL with the Alembic migrations; the real provider code.

What is not: the database is throwaway, the secrets are public dummies (keys
`q`×40 and `r`×40, as in `backend/tools/qa_server.py`; account A is also the
admin), open signup is switched on so it can be exercised, the port is bound to
127.0.0.1, TLS comes from Caddy's local CA, and the model is `fake_upstream.py`,
a scripted OpenAI-compatible server. Scripting it is the point: it makes replies
finish, hit the token cap, drop mid-stream or fail on demand, so each
completion state goes the whole way to the browser. It says nothing about the
real model's quality — that is `backend/quality_check.py`.

Never point this at real data or a real provider key.

## Run

Docker running, Chrome installed, Playwright available (set `PLAYWRIGHT_MODULE`
to an existing install's `node_modules/playwright` if it is not on the path).

```sh
cd deploy/tests/production-rehearsal
docker compose up -d --build
# wait until https://localhost:8443/api/health/detail answers 200, then:
docker compose exec -T -e PYTHONPATH=/app backend python /rehearsal/seed_users.py
REHEARSAL_REPORT=../../../docs/production-rehearsal-results.json node browser-check.cjs
# optional, needs axe-core (npm install axe-core in any folder; set AXE_MODULE to it):
A11Y_REPORT=../../../docs/accessibility-results.json node accessibility-check.cjs
docker compose down -v
```

PowerShell: `$env:REHEARSAL_REPORT = "..."; node browser-check.cjs`.

Start from `docker compose down -v` for every run: the checks expect fresh
accounts (the conversation-deletion and account-switching checks count rows).

## What it checks

`browser-check.cjs`, in order:

1. Pages carry a per-request nonce CSP (`frontend/src/proxy.ts`) with
   `'strict-dynamic'` and no `'unsafe-inline'` for scripts, a different nonce
   each request; API responses carry the fallback CSP in `deploy/Caddyfile`.
   Plus HSTS, `X-Frame-Options`, `nosniff`, COOP, `Permissions-Policy`, and no
   `X-Powered-By`.
2. Sign-in over HTTPS sets an httpOnly, Secure, SameSite=Strict cookie.
3. Home, Team, Memory, Goals, Account, Privacy, a chat, Login, Signup and
   Recover render with images, self-hosted fonts and stylesheets loaded and no
   CSP violation.
4. Onboarding with Modeer saves a fact, Memory shows it, a specialist's prompt
   contains it.
5. A reply streams through Caddy word by word (a buffering proxy fails this).
6. Truncated: text kept, labelled, still labelled after reload; Continue works.
7. Dropped mid-stream: labelled; Try again replaces it, no duplicate message.
8. Provider refused (503): recorded as failed; one Try again recovers it.
9. Markdown links: only `/memory` and `https://…` become links; `//host`,
   `javascript:` and `/\host` stay plain words.
10. The browser goes offline mid-reply: after reconnecting, a reload shows what
    arrived, labelled, and Try again finishes it.
11. Blank messages: 422 from the API, send disabled in the UI.
12. Deleting a conversation removes it (404 afterwards).
13. Switching accounts: each sees only their own memory and conversations.
14. Readiness through Caddy: an admin sees production and a current schema;
    anonymous callers get only status, database and schema_current; liveness
    only status and database; agent detail shows no model settings; the
    synchronous chat route is not served.
15. Open signup: a refused email gets a readable message; an account is
    created signed in with ten recovery codes, and Continue waits for "I've
    saved these codes".
16. Sign-in with email and password.
17. Account page: a wrong current password is answered in place (no redirect);
    the automatic-memory switch turns off and the API agrees.
18. A recovery code resets the password; the old password stops working.
19. At 390px: no horizontal overflow; the notice and the recovery button fit.
20. No CSP violations and no uncaught page errors over the whole run.

`accessibility-check.cjs` runs axe-core (WCAG 2.2 A/AA and best practice) on
every page at desktop and phone width, tabs through each page checking that
every stop is on screen with a focus indicator, and goes from signup to a first
message without a mouse. It is automated evidence, not a screen-reader pass.

Also worth running while the stack is up — API docs are off in the production
image itself, not only unrouted by Caddy:

```sh
docker compose exec -T backend python -c "import urllib.request as u, urllib.error as e
for p in ('/docs', '/redoc', '/openapi.json'):
    try: u.urlopen('http://localhost:8000' + p); print(p, 'SERVED')
    except e.HTTPError as x: print(p, x.code)"
```
