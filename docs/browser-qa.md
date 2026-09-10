# Browser QA — 2026-09-10

Executed in installed Chrome through Playwright against the running Next.js frontend and an authenticated FastAPI QA server. Both used isolated QA data, never the user's development database. The approved artwork/layout was preserved.

## Repeatable mock journey: 13 checks passed

`browser-qa-results.json` records login, onboarding completion through chat, extracted facts visible in Memory, specialist follow-up using saved context, history drawer, overflow checks on Home/Team/Memory/Goals/Study at 1440/768/390 pixels, mobile offline failure and retry, readable HTTP 429 message, incomplete SSE handling, navigation during a pending request followed by successful sending, and no uncaught page errors.

Offline mode was simulated with the browser network switch. HTTP 429 and incomplete/pending streams were injected through Playwright routing. Backend tests independently exercise actual quota rejection. This is not a physical-phone or unstable cellular-network test, nor proof of proxy streaming timing.

Run a mock QA server on port 8002 with frontend origin http://localhost:3001 and a throwaway database, then start Next.js with BACKEND_URL=http://127.0.0.1:8002 on port 3001. Run `node tools/browser-qa.cjs` from frontend with Playwright installed, or set PLAYWRIGHT_MODULE to an existing module location. QA_URL and QA_REPORT override the URL and report path. The fixture key is the public dummy key from tools.qa_server, not a production invitation. Use a fresh QA database for repeat runs to avoid intentionally enforced daily limits.

## Live mobile journey: 3 checks passed

After a successful provider health check, the QA backend was restarted with the configured Groq provider and another isolated database. At 390px, the real browser sent three personal facts to Modeer, received a completed streamed answer and memory event, displayed Alexandria in Memory, and asked Study to recall the city and subject. The response was: “You live in Alexandria, Egypt and are studying computer science.” The end event marked context_used=true. See browser-live-qa-results.json.

These two live turns verify the integrated browser/provider/memory path. They are not a full repeated agent-quality evaluation, and do not replace the outstanding baseline-model evaluation.

## Fix found

The stream client previously replaced an HTTP error's safe message with `Stream failed (429)`. It now reads the server's detail so account limits explain the wait. Existing incomplete-stream detection and navigation cancellation passed.
