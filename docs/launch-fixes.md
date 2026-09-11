# Launch fixes and verification — 2026-09-11

The repository fixes below are implemented. Public production is not signed off.
No deployment or main-branch merge was performed. The approved comic design and
character artwork are unchanged.

## Application fixes

- Account export handles the stored briefing date string; it previously failed
  after a briefing existed.
- Account lets users download their data, sign out every device, or permanently
  delete their account after typing DELETE. The public privacy notice is linked
  from login and Account. Conversation history has a confirmed deletion action.
- Shared preferences now reach specialists. The previous category filter omitted
  them even though evaluation fixtures supplied them directly. Live requests and
  evaluations now use the same filtering function; other specialists' private
  notes remain excluded.
- Exceptions log route templates, incident IDs, types and stack locations without
  exception text, chained values or SQL parameters. Production server access logs
  and HTTP-client URL logs cannot expose private routes or alert credentials.
- Long provider waits are displayed accurately. Readiness returns 503 for active
  quota blocks, recent provider failures, recent repeated server errors, or the
  wrong production schema. Successful replies clear the affected model's state.
- Repeated errors share a stable alert cooldown key. Alert channels are attempted
  independently. An operator test reports failure unless an endpoint accepted it.

## Operations fixes

Linux backups require a key and an existing copy destination, reject overlap,
encrypt with native OpenSSL, compare the copied bytes, clean transient plaintext,
and prune matching archives from both destinations. The nightly job verifies the
copied archive immediately and alerts on failure. The watchdog reads readiness,
not basic liveness, and retries notifications that failed to deliver. Cron recipes
are single physical lines and use a private environment file.

The Linux rehearsal used PostgreSQL 16 at revision 0003, with synthetic user,
briefing and usage-ledger data. It verified encryption/decryption/restore,
missing-key and wrong-key failures, retention on both destinations, degraded and
recovered readiness, delivery retries, and nightly-job failure alerts. Notifications
went only to a local test endpoint. The copied archive was on the same development
machine: this does not prove physical off-host disaster recovery.

## Verification evidence

- `account-qa-results.json`: nine Chrome checks with an authenticated mock backend,
  including export after a briefing, visible export failure, cancellation and
  deletion, 390/768/1440 layouts, second-device revocation, account deletion and
  rejection of the deleted account's old key. No uncaught browser errors.
- `linux-operations-results.json`: eight Linux operations checks.
- Backend: 154 passing tests and clean Ruff checks.
- Frontend: production build (including type checking) and lint passed.
- Prior everyday-journey evidence remains in `browser-qa.md`; it covers onboarding,
  memory follow-up, offline retry and interrupted streams. It was not rerun against
  the final production frontend in this pass: automatic approval review rejected
  startup with only "blocked by policy". The account checks ran against the
  development frontend. Physical-device and real-domain streaming remain unverified.

## Agent quality

The completed generation reports contain three samples of thirteen cases: ten
personalized specialist/leader tasks plus unknown-fact checks for Study, Career
and Writing. All fixtures are synthetic. Writing retains qwen/qwen3.8-27b; the
other agents use the selected default. Timings measure provider completion in the
harness, not end-to-end browser latency or load capacity.

The original grader did not see the name/profile passed to the agent and could
accept incomplete or nonboolean grades. Version 2 fixes those defects, permits
advice to use an in-app specialist, and retries short grader rate limits. Raw
results are retained. Regrading changes scores, not saved answers. An unavailable
grade is never a pass. A same-model grade for Writing is not independent evidence.

The raw generation reports are:
`quality-production-launch.json` and `quality-candidate-20b-launch.json`.

The 20b candidate, preserving Writing's qwen override, completed 39 responses:
31 passes, 6 failed answers, and 2 unavailable grades. It had no deterministic
length failures. It is **not promoted**: sample 3 Shopping recommended Android
while ignoring the supplied iPhone/Apple Watch context; Fitness invented which
weekdays remained. A manual check also found Finance's sample 3 incorrectly
turning a EUR 40,000 goal over four years into EUR 1,000/month (40,000 / 48 is
about 833.33). These are substantive failures, not formatting preferences.

The configured 120b run initially hit a long provider quota wait after 32 cases;
it was resumed after capacity returned to finish all 39. Eleven answers exceeded
the existing word ceilings. Its raw automated scores include the old grader's
limitations, so use `quality-production-launch-regraded.json` for corrected scores.
The original raw file is retained for traceability. Some judge findings can still
be false positives; inspect the quoted evidence rather than treating a score as
proof. No model setting was changed on the strength of these results.

With the corrected grader, the configured 120b run scored **25/39 passes**,
14 failed answers and 0 unavailable grades. All 39 saved responses were
regraded. This confirms a quality blocker independently of the original quota
interruption. The full corrected evidence is in
`quality-production-launch-regraded.json`.

## Answer-length fix — 2026-09-11 (gate 1)

Eleven of the fourteen regraded failures were `too_long`; the grounding findings
were three. It was one dominant problem, and partly ours rather than the model's:
the prompt said "under 350 words" while `max_tokens` handed the agent 1200–1400
tokens, roughly 900–1050 words. The budget is the louder signal. `max_tokens`
could not be used as a control either, because hitting the cap raised
`ProviderError` and discarded the whole reply — the cap could only destroy an
answer, never shorten one.

Three changes:

- **Truncation is graceful.** Running to the cap now keeps what has already
  streamed and ends the reply; only a cap consumed with nothing emitted is still
  an error. Counted as `length_stops` in readiness so a rising count shows the
  cap fighting the prompt.
- **Caps match the stated ceiling.** Plan agents 1200–1400 → 800, advice agents
  → 650. Comfortably above the 450-word ceiling, far below the previous ~900.
- **Limits the model can count.** At most three headings, one table, one line per
  row or day; no "Why this works", "Downside test" or "Assumptions" block. Those
  sections were exactly what Study and Finance padded with.

Two further conflicts, the same bug class as Writing's rationale rule — a
per-agent instruction contradicting a global rule, which the model resolves by
doing the forbidden thing:

- Travel was told "show the budget split" unconditionally *and* "never invent a
  budget". It invented budgets so it had a split to show. The split is now
  conditional on a budget having been given.
- Travel was told to "note assumptions the user must confirm" while the global
  rule forbids an Assumptions block. It produced one, filled with invented
  personal facts ("You're traveling solo", "flexible budget"). Now scoped to
  external items — visa, weather, seasons — inline, with nothing about the person.

Rule 3 also now covers **which model or version of a thing someone owns**:
Shopping turned "already on iPhone" into "your iPhone 13/14".

### Measured on `openai/gpt-oss-120b`

| | Deterministic | `too_long` | Word range |
|---|---|---|---|
| Before (39 responses, regraded) | 28/39 | **11** | 9–803 |
| After length fix (18 responses) | 18/18 | **0** | 9–428 |
| After travel/shopping fixes (6) | 6/6 | **0** | 229–345 |

With the judge, the 18-response run scored 17/18 and the travel/shopping run
5/6. Every reply ended on a complete sentence — the lower caps shortened answers
by choice, not by truncation.

**Not yet measured:** the owned-model/version rule was added after the last run,
and a full 39-case run directly comparable to the 25/39 baseline did not
complete — the provider's daily budget ran out after four cases. Resume it with
`python quality_check.py --samples 3 --resume` on a fresh budget before treating
gate 1 as closed.

## Remaining launch gates

1. Address the measured answer-quality failures and repeat tests on the exact
   intended model configuration. Free-provider quotas remain shared across all
   users and can stop replies even when the app works correctly.
2. Choose/provision the real host and domain; confirm TLS, secure cookies,
   cross-account denial, streamed replies and interrupted reconnection there.
3. Install the documented scheduler, confirm the destination is genuinely remote,
   verify its retention/version-history rules, and restore from that storage.
4. Configure an actual operator recipient and verify receipt of an outage,
   recovery, backup-failure and test notification. Local endpoint acceptance is
   not proof of delivery to a person.
5. Run the final production-browser journey after startup is allowed. Invite-only
   beta is the current account model; unrestricted public signup is not built.
