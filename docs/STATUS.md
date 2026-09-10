# Project status — Modeer Personal AI Team MVP

_Last updated: 2026-09-10 · phase: hardening for a private, invite-only deployment_

---

## Latest pass — quality, security, deployment prep (2026-09-10)

**Not deployable yet.** Nothing has been published, no host or domain is chosen,
and the container stack has never been built or launched. What follows is what is
done, what is verified, and what is still open. Sections below this one describe
the earlier redesign phase and are unchanged.

### Done and verified

| Area | State |
|---|---|
| Response-quality rubric (`app/agents/rubric.py`) + 32 tests | ✅ Replaces keyword scoring — see `docs/agent-quality.md` |
| Agent prompt fixes (guardrails, Writing, Shopping, Career, Study) | ✅ 8/13 → 12/13 on the same rubric |
| Live quality run, full responses stored and reviewed | ✅ `docs/live-quality-*.json` |
| Auth on every personal-data route, enforced by a route-table sweep | ✅ `tests/test_auth.py` |
| Ask My Team: anonymous + cross-account regression tests | ✅ New |
| Session expiry, key revocation, foreign-secret cookie, origin checks | ✅ Tested |
| Live end-to-end journey on the real provider, isolated DB | ✅ 12/12 — `backend/journey_check.py` |
| Backend tests · ruff | ✅ 101 passed, lint clean |
| Frontend production build | ✅ Rebuilt, unchanged this pass |
| Backup: retention, AES-256 encryption, off-host copy, restore check | ✅ Written — ⚠️ never executed (no Docker) |
| Temporary patch/diagnostic scripts | ✅ Removed or folded into `backend/tools/` |

### Fixed this pass, worth knowing

- **`chat/stream` answered 422 before 401.** Auth ran inside the handler, after
  body validation, so an anonymous caller learned the request schema. Auth is now
  a FastAPI dependency (`core.auth.caller_id`) on both chat routes and Ask My
  Team. A test walks the real route table so a new endpoint cannot skip it.
- **Rate limits were being recorded as bad answers.** Two earlier quality runs
  had empty replies scored as quality failures; they were 429s. The eval harness
  now backs off and retries, and tells a per-minute throttle apart from a daily
  quota (`ProviderError.retry_after`) so it aborts instead of burning a run.
- **An aborted run destroyed the previous results file.** It now writes to
  `<out>.partial` and promotes only on completion.

### Still open

1. **11 of 13 cases unconfirmed on `openai/gpt-oss-120b`.** Its 200,000
   tokens-per-day budget was spent, so the complete after-run is on
   `qwen/qwen3.8-27b`. A later `gpt-oss-120b` attempt got 2 cases through before
   the cap returned; both passed, including Study — 735 words with an invented
   countdown before, 333 words and no calendar claim after. Re-run
   `python quality_check.py` on a mostly idle day.
2. **Eval variance is large and unmeasured.** One sample per agent at temperature
   0.3–0.6: across three runs Career failed on length then passed, Research came
   in under the ceiling then three words over. Sampling each case several times is
   the highest-value next step for the eval itself.
3. **The LLM judge is an aid, not a gate.** `openai/gpt-oss-20b` produces regular
   false positives. Read the stored responses.
4. **Docker cannot run here: WSL is not installed.** No image build, no PostgreSQL
   migration, no HTTPS, no persistence check, and `deploy/backup.ps1` /
   `restore-check.ps1` have never been executed. See `docs/DEPLOYMENT.md`.
5. **Browser and mobile testing was not repeated.** No browser automation is
   available in this environment; the journey was verified at the HTTP layer
   instead. The real login page, mobile reconnects and interruption-by-navigation
   still need a human with a browser.
6. **Abuse protection is unreviewed.** There is no per-user request quota or
   rate limit in the app. Invite-only keeps the blast radius small, but a single
   account can still exhaust the shared provider budget — which happened during
   this pass, to this machine.

---

## 1. Where the project is

MVP core is complete, the first milestone works end to end, and the frontend has
been rebuilt in the **“Sunshine & Ink”** visual language (§0). Product behaviour,
the API and the agents are unchanged.

| Area | State |
|---|---|
| Repo scaffold · DB models + migration · API · docs | ✅ Done |
| Agent runtime + registry + 10 agent configs/prompts | ✅ Done |
| Real LLM provider (Groq / OpenAI-compatible, streaming, 429 back-off) | ✅ Done |
| LLM-assisted memory extraction (rules fallback) | ✅ Done |
| **Frontend visual language: “Sunshine & Ink”** | ✅ Redesigned this pass — see §0 |
| First-run onboarding ("Meet Modeer" → chat → team) | ✅ Done |
| Agent prompt improvements (Modeer, Career, Research + global) | ✅ Done |
| Visual QA at desktop / laptop / tablet / mobile | ✅ Re-verified after the redesign |
| **Character artwork** | ⚠️ Provisional hand-authored SVG — no image generator here (§0.1) |
| Tests (58 pytest) · ruff · tsc · next build · next lint | ✅ All green |
| Priority-5 agent evals on the real model | ✅ 31/35 (89%) baseline |
| Remaining-5 agents: full eval sweep on the real model | ⏳ Rate-limited; spot-checked OK |
| **Groq API key** | ⚠️ **Daily token limit hit during testing — rotate & consider a paid tier** |

---

## 0. Sunshine & Ink redesign (this pass)

The frontend was rebuilt to match the **Concept A — “Sunshine & Ink”** reference:
warm cream paper, comic yellow, vivid pink, near-black ink, big diagonal fields,
heavy display type, black-outlined comic panels, and original human character
illustrations. **No backend, agent, API or product behaviour changed.**

### Design system
`src/app/globals.css` + `tailwind.config.ts` define one token set —
`--paper #FFF7DF`, `--sun #FFDA45`, `--pink #FF438A`, `--ink #151714`,
`--navy #202D3B`; 2px ink borders; hard offset “pop” shadows (no blur); a paper
grain / halftone texture used only on artwork and colour fields, never behind
body text.

Type: **Archivo Black** (display), **Permanent Marker** (the MODEER wordmark
only), **Caveat** (sparse handwritten margin notes — never used for chat, forms,
navigation or descriptions), **Inter** (all interface text).

### Character artwork  ⚠️ see §0.1
- `src/components/art/Portrait.tsx` — a comic portrait engine: variable-weight
  ink contours, crosshatch shading, halftone, warm colour, per-character head
  width / jaw / chin / eye geometry, 10 hairstyles, glasses, facial hair,
  wardrobe and background props.
- `src/lib/characters.ts` — the **replaceable asset map keyed by agent slug**.
  Setting `CHARACTERS.study.image = "/art/study.png"` swaps in finished artwork
  with no layout change. No interface text is baked into any artwork; every name
  and role is HTML. Each character carries meaningful `alt` text; decorative
  instances are `aria-hidden`.

### Screens
- **Home** — top nav replaces the dark sidebar. Hero: “Meet Modeer” in heavy
  display, “Your personal AI team.”, a real composer (cream, ink outline, pink
  action) that submits into the existing Modeer conversation flow, and Modeer’s
  large portrait as a cut-out over three diagonal cream/yellow/pink fields.
  Below: “Your team” with an ink rule, then illustrated panels — first desktop
  row Study, Career, Research, Writing — and a **Today** band carrying the daily
  briefing and goals.
- **Team** — Modeer as a distinct featured row, then the full nine-specialist
  roster as panels.
- **Agent workspaces** — compact illustrated identity header with a yellow
  geometric detail, cream reading surface, yellow user bubbles vs. plain ink
  prose for the assistant, small portrait per message, a quiet
  “personalised from your saved context” pill, and a persistent composer.
  Markdown (headings, lists, links, tables, quotes, code) keeps scrolling
  containers. Large artwork stays in headers and empty states.
- **Memory** — paper sections with yellow category headers; “Shared with your
  team” vs “Known by one specialist” preserved; specialist picker uses portrait
  thumbnails; edit/delete are always visible at 44px.
- **Goals** — cream rows, ink controls, priority shown as **text plus** colour.
- **Onboarding, history drawer, empty/loading/error states** all restyled; no
  dark-theme components remain.

### Verified (headless Chrome, real backend + real Groq streaming)
20/20 interaction checks pass with no console or page errors:
hero composer → Modeer → live streamed reply · history drawer open/close ·
goal create/complete/delete · memory add/edit/delete · specialist notes ·
team → specialist navigation · no horizontal overflow at 390px on any route.
Checked at **1440×900, 1280×800, 768×1024, 390×844**; screenshots in
`qa-screenshots/` (git-ignored).

`pytest` 58 passed · `ruff` clean · `tsc` clean · `next build` clean ·
`next lint` clean.

### 0.1 Remaining differences from the reference — read this

**This environment has no image generator** (no AI image tool, no MCP image
server, no diffusers/ImageMagick/Inkscape — checked before starting). The
reference’s characters are rendered comic illustrations; ours are **hand-authored
SVG**, so:

- Faces are cleaner and flatter than the reference’s inked, textured rendering.
  Crosshatch, halftone and contour shading are present but simpler.
- Poses are frontal busts. The reference’s Modeer leans on one hand; there are no
  hands, arms or props held by the characters.
- Backgrounds are simplified flat shapes rather than detailed scenes.
- Everyone shares one underlying face construction, varied by geometry, hair,
  skin, wardrobe and expression — distinct people, but a narrower range than
  drawn art would give.

Other differences: the reference’s decorative slogans were deliberately not all
reproduced (the brief asked for sparse annotations, and some concept text is
accidental); nine specialists means the 4-column Home grid leaves one panel on
its own row.

**Provisional assets to refine later** (all in `src/lib/characters.ts`):
`modeer`, `study`, `career`, `research`, `writing`, `travel`, `shopping`,
`finance`, `fitness`, `email`.

---

## 0b. Earlier visual / interaction QA

Inspected via headless Chrome (Playwright driving the installed browser) at
**1440×900, 1280×800, 768×1024, 390×844** with a realistic seeded profile
(6 shared memories, 3 specialist notes, 5 goals, a 4-message Career thread with
a markdown table, a Study thread with code + a comprehension check).

**Bugs found and fixed**

| # | Problem | Fix |
|---|---|---|
| 1 | `.btn-primary/.btn-accent/.btn-secondary/.btn-ghost` never included the `.btn` base — "Add goal", "+ New", "Add something" rendered as unstyled text | each now `@apply btn` |
| 2 | Native `<select>` showed the OS control | custom chevron + option colours for `select.field` |
| 3 | Modeer hero had a hollow empty right half on desktop | two-column layout (identity + summary + composer \| Today's focus) |
| 4 | Agent workspace: conversation pushed off-centre by a mostly-empty rail | rail removed; history is a bottom-sheet (mobile) / right drawer (desktop); conversation centred |
| 5 | Chat opened scrolled to the top of a thread | auto-scrolls to the latest message on load |
| 6 | Last message hidden behind the composer; composer under the mobile tab bar | scroll padding + `pb-[calc(56px+safe-area)]` on the footer |
| 7 | Memory / Goals: a narrow column floating in a wide empty area | constrained + left-aligned to the nav gutter; denser rows; edit/delete visible at rest |
| 8 | Specialist empty state floated high with a void below | vertically centred; larger starter chips |
| 9 | Mobile agent page showed the app top bar **and** the agent header | app top bar hidden in the workspace |
| 10 | Tablet (768) with the desktop sidebar → cramped, truncated taglines | sidebar now appears at `lg` (1024); tablet gets the mobile layout; grid is 1/2/3-col at base/`md`/`xl` |
| 11 | Next.js dev "N" badge sat on top of the user avatar | `devIndicators: false` |
| 12 | `humanizeKey` → "MI internship" | acronyms (ml, gpa, cv, …) upper-cased |
| 13 | Briefing rows had a redundant dot **and** emoji **and** coloured name | dropped the emoji; generic CTA row filtered out |

**Still weak / minor (not blocking)**

- Short conversations leave empty space above the composer (expected — content is
  top-aligned so you read from the top; matches ChatGPT/Claude).
- Memory/Goals pages are short — noticeable empty space below the content on tall
  desktop screens.
- Agent glyphs are OS colour emoji in an accent-tinted tile. Consistent and
  legible, but a bespoke icon set would feel more "designed"; deferred (10 icons,
  higher risk than reward right now).
- Markdown tables are readable but tight on a 390px phone (they wrap; wider ones
  scroll).
- Edit/delete hit targets on Memory rows are ~28px — fine with a mouse, a touch
  bump would be nicer.

**Not verifiable without you**

The QA used headless screenshots, not hands-on interaction. Please still click
through once for *feel*: streaming cadence, focus states, the mobile keyboard
pushing the composer, drawer open/close animation, and hover states (screenshots
can't show those).

---

## 2. What changed this pass

### Phase 1 — Real model
- Added `LLM_PROVIDER=groq` / `openai` support: a single OpenAI-compatible
  streaming provider (`app/llm/openai_compat_provider.py`) with **429 rate-limit
  back-off** (honours `retry-after` / "try again in Ns"). Your `.env` was pointing
  at Groq `openai/gpt-oss-120b`; that now works.
- **Security fix:** your Groq key was in `backend/.env.example` (a git-tracked
  template — though not yet committed). Moved it to `backend/.env` (git-ignored)
  and restored the template to placeholders. **Rotate that key** — it was shared
  in plaintext. See §4.
- Streaming, context injection, Modeer, specialists and memory all verified
  against the real model over HTTP.
- Eval harness: added `--delay` (throttle) and `--show`; per-case failures no
  longer abort the run.

### Phase 3 — Agent performance (real-model eval: 31/35 on the priority 5)
Fixed the real problems the eval surfaced:
- **Modeer** now hands off clearly when a request is squarely a specialist's job
  ("the Fitness Assistant is built for this — want to take it there?"), instead
  of quietly doing the specialist's whole job.
- **Career** — a refusal to fabricate credentials now *pivots* to the honest move
  (reframe real experience, quantify impact) instead of a bare "I can't help."
- **Research** — states up front it can't pull/verify live sources and won't
  invent citations, then stays useful (what to search, where).
- **Global guardrail** (all agents): personal context is background, not a
  checklist — use a fact only when it changes the answer; never open with a
  recap of what you know. (Phase 4.)
- Two eval cases were harness false-negatives (a correct JARVIS refusal, a
  correct citation refusal) — expectations corrected.
- Spot-checked Fitness / Finance / Email on the real model: each shows its
  domain framework (Fitness asks background + injuries first; Finance leads with
  "education, not advice"; Email is BLUF with a subject line). Not shallow.

### Phase 4 — Context & memory quality
- **LLM-assisted extraction** (`app/memory/llm_extraction.py`): when a real
  provider is set, one short JSON call per user message proposes durable facts;
  the **same conservative gates** as the rule-based path then decide what's
  stored (sensitive dropped unless opted in, low-confidence dropped, agent-scoped
  facts kept only in-domain). Falls back to rules on any bad output. Rules still
  run for `mock` / tests, so the suite stays deterministic.
  - Before: "I'm a third-year CS student at Cairo University, goal is an ML
    internship next summer" → 2 poor facts (`level = "computer science"`).
  - After: 5 clean facts — field of study, year, institution, inferred location,
    and the ML-internship **goal**; powerlifting "4×/week" routed to the Fitness
    agent's private notes; "my salary is …" + "diagnosed with asthma" flagged
    sensitive and **not stored**.
- 8 new deterministic tests (`tests/test_llm_extraction.py`) cover parsing,
  gates, scope routing and fallback.
- Runtime now emits `end` (answer done) then a trailing `memory` event, so the
  reply renders instantly and the "saved to your context" confirmation follows.

### Phase 5 — First-run experience
- New users land on **"Meet Modeer"** (not a form): one line of context → "Start
  with Modeer" → a guided first message. Onboarding completes itself once Modeer
  has learned ~3 durable facts (or after a few exchanges with ≥1 fact), and the
  workspace shows a "Your team is set up" banner linking to the team.

### Phase 2 / UI — full redesign
New token-based design system (`globals.css` + `tailwind.config.ts`): calmer
near-black palette, one subtle ambient wash (no gradient soup), hairline borders
used sparingly, a real type/spacing/radius scale, restrained motion
(`prefers-reduced-motion` respected), inline SVG icon set.

- **Home** — greeting by name; **Modeer hero panel** (distinct from the grid) with
  the daily briefing as tappable rows tinted by the related specialist's accent,
  an inline "Message Modeer…" composer, and an active-goals chip. Below: the team
  as one-line roster cards (name · tagline · accent — no paragraphs).
- **Team** — Modeer as a wide feature row, then the nine specialists.
- **Agent workspace** — clean identity header with a per-agent accent hairline,
  agent-specific empty-state question + starter chips, agent-specific composer
  placeholder, auto-growing composer, a small "Personalized from your saved
  context" link (no token counts / model names / internals). Conversation history
  is a drawer (bottom-sheet on mobile, right-side on desktop). A proper markdown
  renderer (headings, lists, tables, code, quotes) replaces the previous naive
  one. _Rail replaced with the drawer in the QA pass — see §0._
- **Memory** — "Shared with your team" grouped by human category; "Known by
  specific agents" behind an accent-chip picker; rows read as labelled facts, not
  raw key/value; inline add / edit / delete; a trust line about sensitive data.
- **Goals** — restyled, still lightweight (no kanban/dependencies).
- **Nav** — slim left rail on desktop (no promo clutter), **bottom tab bar** on
  mobile. Presentation fields (`tagline`, `composer_placeholder`, `empty_prompt`,
  `starters`) live in each agent's `config.py`, served by the API — the UI stays
  config-driven.

---

## 3. What you need to do

### A. The Groq key — rotate it, and mind the limits
- It was pasted into a git-tracked template and into this session in plaintext.
  It now lives only in git-ignored `backend/.env`. **Revoke it** at
  <https://console.groq.com/keys>, make a new one, put it in `backend/.env`
  (never `.env.example`).
- Testing this session **exhausted the free tier's daily token budget**
  (200k tokens/day). Real chat will 502 until it resets (~24h) or you upgrade.
  The provider already retries on 429; a daily cap it can't retry around.
- While the key was capped, this pass's UI screenshots were taken with the
  backend on `LLM_PROVIDER=mock` (your `.env` is back on `groq`, untouched).

### B. Run it
```bash
# backend  (venv + deps already installed locally)
cd backend && .venv\Scripts\activate
uvicorn app.main:app --reload            # :8000

# frontend
cd frontend && npm run dev               # :3000
```
SQLite is the default DB — no setup. The dev DB (`backend/modeer.db`, git-ignored)
currently holds a **seeded demo profile** from QA (memories, goals, two example
conversations); `rm backend/modeer.db` for a clean slate.

> The Next **dev** server intermittently 500s with "Cannot find module
> './xxx.js'" after many hot-reloads (a known Next 15 dev-cache bug on Windows).
> `rm -rf frontend/.next` and restart. `npm run build` is unaffected — the QA
> screenshots were taken against `npm run start` for exactly this reason.

### C. Hands-on interaction check (small, ~10 min)
Screenshots covered layout at all four widths; they can't show *feel*. Click
through once for: streaming cadence, focus rings, the phone keyboard pushing the
composer, the history drawer open/close, hover states on the team cards, and the
"saved to your context" confirmation after a real message.

### D. Decisions still yours
| # | What | Why it needs you |
|---|---|---|
| 1 | Groq tier | Free tier: ~8k tokens/min **and 200k/day**. A paid tier (or a 2nd key) is needed for full eval sweeps and heavy use. |
| 2 | Auth strategy | Still a single local "demo user". Decide before multi-user. |
| 3 | Model choice | `openai/gpt-oss-120b` is solid in testing. Confirm it's what you want, or switch `LLM_MODEL`. |
| 4 | Deployment target | No hosting/CI yet (out of MVP scope). |

---

## 4. Known limitations / tech debt

- Visual QA done via headless screenshots; hands-on interaction check still
  wanted (§3C).
- **Remaining-5 agents**: only spot-checked on the real model; the full eval
  sweep was rate-limited. Re-run `python -m app.agents.evals travel shopping
  finance fitness email --delay 22` when the Groq budget allows.
- **LLM extraction adds one short model call per user message** (after the reply
  streams, so no perceived latency). Set `MEMORY_EXTRACTION=rules` to disable.
- `next lint` prints a deprecation notice (works; Next 16 removes it).
- The markdown renderer is deliberately small — headings, lists, tables, code,
  quotes, bold/italic/links; not full CommonMark.
- No pagination on conversation / memory / goal lists (fine at MVP scale).
- Minor visual items in §0 ("still weak / minor").

---

## 5. Suggested next phase

1. **Hands-on interaction check** (§3C) — fix anything that feels off.
2. **Finish the real-model eval sweep** for all 10 agents once the Groq budget
   resets; iterate on any prompt below ~80%.
3. **"Ask My Team" front end** — the API (`POST /api/team/ask`) and synthesis
   exist; there's no screen yet. The natural next feature once UI/UX and agent
   quality are signed off.
4. Optional: briefing history view; a real profile/settings screen; auth.

Do not start #3 before #1–#2 are done.

---

## 6. Quick reference

| Task | Command (from the folder shown) |
|---|---|
| Run backend / frontend | `uvicorn app.main:app --reload` / `npm run dev` |
| Backend tests / lint | `python -m pytest -q` / `ruff check .` |
| Frontend checks | `npm run build` · `npm run lint` · `npm run typecheck` |
| Agent evals (real model) | `python -m app.agents.evals <slugs> --delay 22 --show` |
| Force rule-based memory | `MEMORY_EXTRACTION=rules` in `backend/.env` |
| DB migrate (Postgres) | `alembic upgrade head` |

More detail: `README.md`, `docs/{product,architecture,agents,memory}.md`.
