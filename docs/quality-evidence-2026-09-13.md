# Quality evidence and remediation — 2026-09-13

This ledger separates application regression tests, live model measurements,
and reviewer interpretation. Source baseline: `1ed17eb` plus the authorized
remediation working tree. No older quality artifact was overwritten or silently
regraded. A passing automated judge is not a guarantee of factual accuracy.

## Application verification

- Full backend suite: **326 passed**, one Starlette TestClient deprecation warning.
- Ruff: passed. Frontend typecheck and production build: passed. Frontend lint:
  **0 errors, 13 existing warnings**.
- `node tools/stream-check.cjs`: the real stream hook retained a completed answer
  and separately delivered the post-answer memory error. React state is mocked;
  this does not establish actual browser rendering or screen-reader behavior.
- `node tools/links-check.cjs`: eight allowed and 21 refused link cases passed.
- Recovery regression uses independent SQLite sessions and synchronized threads:
  one shared code produces one success and one 401; distinct codes produce two
  successes and two session-epoch increments. It is not a PostgreSQL measurement.
- Seven new backend cases also cover merged-profile rejection without mutation,
  bounded legacy prompt data without deletion, goal detail rejection, source
  hashing, and incompatible-resume rejection/preserved historical provenance.

Reproduce from `backend` with `.venv/Scripts/python.exe -m pytest -q` and
`.venv/Scripts/python.exe -m ruff check .`; from `frontend` run `npm run typecheck`,
`npm run lint`, `npm run build`, and the two Node checks above.

Docker was unavailable in this environment. PostgreSQL race testing, deployed
browser journeys, physical phones, assistive technology, and current-schema
off-host restoration were not rerun. The earlier review's npm audit had zero
production advisories; no new dependency audit is claimed here.

## Fresh evaluation protocol

From `backend`:

```text
.venv/Scripts/python.exe quality_check.py --samples 3 --judge-model qwen/qwen3.8-27b --out ../docs/quality-remediation-2026-09-13.json
```

The intended measurement is 13 fixtures × three samples = 39 answers across
Modeer and all nine specialists. It uses synthetic profile/shared/private
context, no real transcript history and no goals. It calls the completion path,
not the HTTP/browser streaming journey. No universal `--model` override is used.

- Provider: Groq. Default reply model: `openai/gpt-oss-120b`.
- Writing reply override and judge: `qwen/qwen3.8-27b`; Writing's judgment is
  therefore not independent of its model family.
- Reasoning effort: `low`; provider timeout: 35 seconds. Judge temperature: 0;
  judge output cap: 700 tokens. Normal pacing: 18 seconds between cases plus
  nine seconds before judging, with the runner's explicit throttle backoff.
- Per-agent output cap / temperature / prompt version: Modeer 650 / .55 / 4;
  Study 800 / .5 / 4; Career 650 / .55 / 5; Research 800 / .4 / 5;
  Writing 1600 / .3 / 4; Travel 800 / .6 / 7; Shopping 1100 / .5 / 4;
  Finance 800 / .4 / 4; Fitness 800 / .5 / 5; Email 1000 / .6 / 3.
- Source SHA-256:
  `36a1516b3762eba3e83e386069c961f7a5da953ab3c3f113d3d1241eb32b5a53`.

The hash covers backend application source/prompts/fixtures, the evaluation
runner and dependency lock. It excludes secrets, output files, docs, frontend,
installed-environment state and provider internals. Effective settings and hash
are saved both at run level and per row. This is stronger than `1ed17eb-dirty`
alone, but not an immutable container digest or provider-version guarantee.
Freeze sources during a run. Resume rejects absent/changed fingerprints unless
`--allow-code-change` is deliberately supplied; that override preserves old
row provenance and creates mixed evidence, not one consistent release run.

## Completed live results

[Raw artifact: quality-remediation-2026-09-13.json](quality-remediation-2026-09-13.json)
contains **39/39 completed responses: 33 passed, six failed, zero ungraded**.
All 39 judge calls were available; there were no provider errors, interrupted
responses or token-cap truncations. The runner exited 1 because quality failures
exist, not because the measurement was incomplete. Its progress file was promoted
to the complete artifact. All row fingerprints match the run fingerprint, which
also matches current backend source at verification.

Recorded failures:

- Research sample 1: 457 words, above 450.
- Shopping sample 2: unsupported current-generation processor claim.
- Study sample 3: 457 words, above 450.
- Research sample 3: 539 words, above 450.
- Writing sample 3: placeholder left in the requested conference bio.
- Travel sample 3: unverified specific train departures.

Per-agent automatic pass counts: Modeer 3/3; Study 5/6; Career 6/6;
Research 1/3; Writing 5/6; Travel 2/3; Shopping 2/3; Finance 3/3;
Fitness 3/3; Email 3/3. Study, Career and Writing have both personalization and
unknown-facts fixtures. All nine unknown-facts responses passed automatically.
These counts cover synthetic cases only; 33/39 is not a production reliability
rate and does not negate the reviewer observations below.

## Targeted reviewer observations beyond automated grading

These are source/output comparisons by the reviewing assistant, not a separate
human panel or externally verified product/health advice. They do not overwrite
the stored rubric or judge scores.

- **Research sample 1:** the rubric flags 457 words versus its 450-word ceiling.
  The judge passes it. Its two-hours-per-day schedule is explicitly an assumption,
  not saved user availability; the product should keep that distinction visible.
- **Shopping sample 1:** the automatic checks pass, but the response claims new
  units fit an unspecified-currency budget and asserts a 4–5-year software-support
  horizon without supplied listings or a browsing tool. The recommendation itself
  does not establish those market/support claims. Checking listings afterward
  does not make the preceding confident claims evidence-backed.
- **Shopping sample 2:** the judge rejects the claim that the SE (2022) gets
  Apple's "current-generation processor." Its `currency` dimension measures
  freshness/current knowledge here, not just currency symbols. The same answer
  still asserts budget fit before receiving a currency or listings.
- **Fitness sample 1:** automatic checks pass, yet the supposed no-equipment
  travel sessions require a table/chair, and home exercises introduce an incline
  bench not listed in the supplied context. The schedule adds six training days
  to a stated four-day routine and its fallback both includes and says to skip
  Thursday's circuit. These are constraint/adherence issues missed by the judge;
  no exercise safety or medical suitability assessment is claimed.
- **Study sample 3 / Research sample 3:** 457 and 539 words respectively exceed
  the 450-word ceiling. Study additionally says to aim for "≤ 90% correct,"
  an apparent reversed target missed by the judge. Named textbook examples and
  assumed time budgets are not supplied source material or saved availability.
- **Writing sample 3:** the judge rejects a conference bio containing a generic
  research-area placeholder. This is a usable-draft concern, not invented
  biography: the answer correctly avoids fabricating the unknown detail. A
  better draft can omit the unnecessary detail and still use the known role.
- **Travel sample 3:** the judge rejects specific 10 am/12 pm train departures
  asserted without live schedule evidence. The agent should express a desired
  departure window and require schedule verification, not invent a service.

These blind spots keep answer-quality acceptance open even if the automated
pass percentage is high. A subsequent prompt/evaluation change must receive
new generation evidence; do not relax a rubric merely to turn a failure green.

## Historical evidence retained

- September 12 single-sample runs: 12/13 each; historical revision/configuration.
- `quality-release-2026-09-13.json.partial`: 36/39 attempted, 32 passed and four
  failed. This predates the grounding remediation and cannot measure its outcome.
- `quality-release-2026-09-13b.json.partial`: 6/39 attempted, five stored passes
  and one Research currency-acronym false positive. Current deterministic
  regrading passes all six; it is not six new generations or evidence for the
  33 unattempted cases.

The [original review and remediation appendix](production-readiness-review-2026-09-13.md)
retain the historical findings. The [project report](PROJECT-REPORT.md) and
[launch gates](launch-fixes.md) describe current release limitations.

## Next acceptance work

Keep the current release gated. Expand the quality checks for unsupported market
and support claims, unavailable equipment and requested schedule adherence;
review the failures and rerun changed prompts against the same fixtures. Obtain
human adjudication, complete the real-runtime journey, then verify PostgreSQL
credential races and the deployed memory-failure notice. Operational release
gates remain separate from model scores.
