# Prompt: create the Fareeq handover presentations

**Agent-name update — 2026-09-15:** Leo is the team leader; Nova (Study), Harvey (Career), Clara (Research), Alex (Writing), Tessa (Travel), Nate (Shopping), Emma (Finance), Maddie (Fitness), and Nora (Email) are the specialists. Fareeq is the product name. See [current naming and compatibility](AGENT-NAMES.md). Historical screenshots, decks and quality artifacts retain the names used when recorded; the earlier live evaluations predate the renamed prompts.

Create two professional, editable presentations from this repository for a third
party taking over the product. Produce the actual presentation files, not only
outlines or slide text. Do not implement features, modify the frontend, change
application code, deploy, create accounts, or spend live model-provider quota.
Write presentation deliverables under `docs/presentations/` using new filenames
if existing files would be overwritten.

## Establish the evidence baseline

Record the current Git revision, working-tree state and preparation date. Read
these files in full before outlining either deck:

1. `docs/PROJECT-REPORT.md`
2. `docs/MOBILE-ROADMAP.md`
3. `docs/production-readiness-review-2026-09-14.md`, including its remediation appendix
4. `docs/launch-rehearsal-2026-09-14.md`, including its September 15 closeout
5. `docs/quality-evidence-2026-09-15.md`
6. `docs/launch-fixes.md`, `docs/DEPLOYMENT.md`, and `docs/OPERATIONS.md`

Look for newer independent reviews, handoffs or verification reports. Inspect
the code references and raw artifacts supporting material claims, particularly:

- `docs/production-verification-2026-09-14.json`
- `docs/production-rehearsal-2026-09-14.json`
- `docs/accessibility-rehearsal-2026-09-14.json`
- `docs/operations-rehearsal-2026-09-14.json`
- `docs/quality-remediation-2026-09-14b.json`
- `docs/quality-rejudged-2026-09-14.json`
- `docs/journey-rehearsal-2026-09-14.txt`

These filenames identify the current handover baseline, not a guarantee that
they will be newest when you execute this prompt. Reconcile contradictions with
the underlying implementation and scoped evidence. A newer report supersedes an
older one only for the behavior/configuration it actually examined. State any
unresolved disagreement. Do not silently manufacture a reconciled result.

Distinguish **implemented**, **verified in a named environment**, **historically
completed**, **proposed**, **unresolved defect**, **coverage gap**, **operational
gate**, and **owner decision**. Label original findings separately from subsequent
remediation. A working-tree implementation is not a released commit. Cite source
paths and revisions where available in slide footers or speaker notes.

## Presentation 1: product and engineering handover

Audience: incoming technical lead, product owner and competent engineers who
have never seen Fareeq. Aim for 16–20 main slides plus focused appendices; adjust
the count to preserve readability and coverage.

Tell a coherent story covering:

- Purpose, intended users, use cases, differentiators and current release status.
- Complete user journey: account access/onboarding, team selection, chat, shared
  and specialist memory, goals, account controls and failure recovery.
- The approved comic visual identity, real character artwork, responsive behavior
  and accessibility evidence. Identify provenance/rights gaps where documented.
- Architecture and deployment boundaries: browser, Next.js, Caddy, FastAPI,
  PostgreSQL/SQLite, providers and operational jobs. Explain the principal request
  and data flows with diagrams.
- Agent architecture: Leo and nine specialists, routing, prompts/models,
  context construction, privacy boundaries and Ask My Team's actual status.
- Data ownership/lifecycle, consent, extraction, export, deletion and migrations.
- Authentication, authorization, session revocation, recovery codes, quotas,
  streaming completion states, retry behavior and important limitations.
- Completed milestones and latest fixes, with evidence rather than a commit dump.
- Security, reliability, encrypted backups/restoration, alerts and operator duties.
- Testing and evaluations with their exact environment/configuration and limits.
- Separate readiness decisions for local use, invite-only beta and public release;
  remaining defects, decisions, launch gates and an ordered takeover checklist.

Put API details, environment-variable names without values, reproducible commands,
and expanded technical explanations in speaker notes or appendices. Do not omit
them merely because they do not fit on a main slide.

## Presentation 2: practical iOS and Android delivery roadmap

Audience: the owner and incoming mobile/engineering team. Aim for 12–16 main
slides plus appendices. Present the mobile app as proposed work.

Cover mobile MVP journeys mapped to existing web capabilities; React Native/Expo,
Flutter and separate native trade-offs; the documented recommendation and its
staffing assumptions; reusable backend capabilities versus required API work;
mobile authentication/storage/revocation/deep links/deletion; streaming,
cancellation, reconnects, background transitions and duplicate prevention;
offline/cache/sync/privacy rules; comic-design adaptation and accessibility;
notifications only where justified; load/quotas/observability; device and network
testing; signing, beta distribution, store submission and privacy requirements;
phases, dependencies, deliverables, acceptance criteria, risks and release gates;
effort ranges with explicit scope/staffing assumptions; a prioritized backlog and
the recommended first milestone.

Keep optional features separate from launch requirements. Do not translate effort
ranges into promised dates or invented budgets. Do not invent owner preferences,
staffing, store-account ownership or infrastructure decisions. Verify time-sensitive
Apple, Google, Expo and React Native claims against official documentation if
presenting them as current; date the verification and cite the exact supporting
pages. If verification is unavailable, retain their documented date and limitation.

## Mandatory evidence distinctions

Unless newer verified artifacts replace them, the handover baseline is:

- 351 backend tests in the locked production image; two recovery-race cases use
  PostgreSQL, while most tests use SQLite.
- 23 local HTTPS browser checks, 25 automated accessibility scans with zero
  findings, ten local operations checks and 13 live application journey checks.
- 39 live answer generations: 27 automated passes, 11 failures and one unavailable
  grade. The separate grading retry remained unavailable. Manual spot checks
  expose both false positives and missed defects. The earlier 33/39 result used
  different prompts/rubric and is historical, not the current acceptance result.

Do not add these counts into a misleading overall quality score. Local Caddy TLS
does not verify the public domain. A second local backup directory is not remote
disaster recovery. A synthetic alert receiver is not operator receipt. Emulated
phone widths and axe scans are not physical-device or human screen-reader sign-off.
The live journey's TestClient closure is not a real transport-disconnect test.
Fast response timings under paced tests are not a concurrency/load guarantee.
There is no evidence-based basis to announce public production readiness yet.

## Visual direction and delivery

Use the existing mature comic-book identity: cream/paper, warm yellow, pink, ink
and navy; strong display titles; crisp panel borders; restrained hard shadows;
subtle texture only outside reading areas. Inspect current design tokens rather
than guessing. Reuse suitable artwork from `frontend/public/art/sunshine/` and
current screenshots where supported by documented provenance. Preserve aspect
ratios and approved character appearances. Do not substitute generic cartoons or
invent screenshots of unimplemented features. Label conceptual mobile screens.

Use readable 16:9 slides, one clear message per slide, generous spacing, and
editable text/diagrams wherever practical. Keep long explanations in detailed
speaker notes. Explain technical concepts in plain language without removing the
engineering detail a successor needs. Use diagrams for architecture, memory
scope, streaming states and milestone dependencies. Avoid dense report pages
pasted onto slides, decorative stock imagery, unsupported marketing claims or
tiny footnote text.

Deliver:

1. `docs/presentations/PROJECT-HANDOVER.pptx` and matching PDF.
2. `docs/presentations/MOBILE-ROADMAP.pptx` and matching PDF.
3. A concise `docs/presentations/README.md` with audience, source revision/date,
   evidence limitations, unresolved questions and any rendering/font caveats.

Render and inspect every slide. Fix clipping, overflow, unreadable text, broken
images, contrast problems and misleading charts. Check that exported PDFs agree
with the editable decks and that speaker notes contain source references. Report
what was actually verified. If required export tooling is unavailable, say so
clearly and provide the best editable alternative; do not claim files exist that
were not created. Finish with links to the deliverables and a brief QA summary.
