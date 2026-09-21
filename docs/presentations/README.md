# Modeer handover presentations

Prepared **2026-09-15** from branch `fixes/launch-readiness-20260911`, HEAD
`1ed17eb5748d948a541f0e76a7fabcddd094534d` **plus the uncommitted working tree**.
The latest security, data and prompt fixes (September 13–14) exist only in
that working tree. They are not a released commit.

| File | Audience | Slides |
|---|---|---|
| `PROJECT-HANDOVER.pptx` / `.pdf` | Incoming technical lead, product owner and engineers | 21 main + divider + 5 appendices (27) |
| `MOBILE-ROADMAP.pptx` / `.pdf` | Owner and incoming mobile/engineering team | 16 main + 2 appendices (18) |

Everything in the mobile deck is **proposed**. No mobile code, store account,
app ID or signing identity exists.

## Sources

Read in full: `docs/PROJECT-REPORT.md`, `docs/MOBILE-ROADMAP.md`,
`docs/production-readiness-review-2026-09-14.md` (with remediation appendix),
`docs/launch-rehearsal-2026-09-14.md` (with the September 15 closeout),
`docs/quality-evidence-2026-09-15.md`, `docs/launch-fixes.md`,
`docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`. Raw evidence inspected:
`production-verification-`, `production-rehearsal-`, `accessibility-rehearsal-`
and `operations-rehearsal-2026-09-14.json`; `quality-remediation-2026-09-14b.json`;
`quality-rejudged-2026-09-14.json`; `journey-rehearsal-2026-09-14.txt`. Agent
settings were read from `backend/app/agents/*/config.py` and design tokens
from `frontend/src/app/globals.css`. No newer review or verification report
than these was found.

Every slide's speaker notes end with its source paths and the baseline.

## Evidence limitations kept visible in the decks

- The counts **351 / 23 / 25 / 10 / 13** come from different environments
  and are never added together. All are local: localhost HTTPS with Caddy's
  local certificate, a scripted model for the browser checks, disposable
  Docker and PostgreSQL 16, and an in-process test client for the live journey.
- Answer quality: 39 live answers gave **27 automated passes, 11 failures and
  1 unavailable grade**; the grading retry also failed. Manual checks found
  both judge false positives and missed defects. The earlier 33/39 used older
  prompts and rubric and is shown only as historical.
- Not verified anywhere: the public domain and TLS, genuinely remote backups
  and scheduling, alert receipt by a person, physical phones, a human
  screen-reader pass, load or multiple workers, and a real network disconnect.
- **Screenshots** were captured on 2026-09-15 from the working tree. The setup
  was `next dev` on localhost with `tools.qa_server` (mock model, throwaway
  SQLite database, synthetic goals and facts). Chat text shows the mock
  model's placeholder, not model output. Phone views are desktop Chrome at
  390px. `next dev` auto-created `frontend/AGENTS.md` and `frontend/CLAUDE.md`;
  both were deleted, so the frontend tree is unchanged.
- **Character art** is used as found in `frontend/public/art/sunshine`
  (aspect ratios preserved; one crop of the wide Modeer hero for the team
  grid). Its documented provenance is AI generation on 2026-09-10
  (`docs/CHARACTER-ART.md`, `docs/SUNSHINE-HOME.md`). There is no licence or
  ownership inventory for the art or the fonts.
- **Mobile store rules:** the Apple (Xcode 26/iOS 26 SDK, guidelines 5.1.2(i)
  and 5.1.1(v), TestFlight), Google Play (API 36 from 2026-08-31, deletion
  page, 12 testers × 14 days, AI content reporting) and Expo (streaming fetch,
  SecureStore) claims were re-fetched from official pages on 2026-09-15, using
  automated retrieval. The React Native framework recommendation, App Privacy
  and Data safety pages were **not** rechecked and keep the 2026-09-13
  documented date. Re-read everything at submission time.
- Mobile effort ranges (12–18 weeks, or 16–24+ weeks for a single engineer)
  are planning ranges under the roadmap's staffing assumptions. They are not
  dates, quotes or budgets. Team skills are unknown.

## Unresolved questions and document discrepancies

1. `docs/PROJECT-REPORT.md` §5 lists older prompt versions than the code and
   the September 14 quality artifact. The decks use the code (Study 5,
   Research 6, Writing 5, Travel 8, Shopping 5, Fitness 6).
2. `docs/DEPLOYMENT.md` still says the rehearsal checks "20 things" (now 23),
   and still says to settle colour-contrast findings (fixed in `80cf49a`).
3. `docs/HANDOFF.md` and `docs/STATUS.md` were last updated 2026-09-13.
4. Removal of the Docker project `modeer-rehearsal-20260914` was not verified
   at closeout.
5. Owner decisions: whether and how to commit or merge the working tree,
   signup mode, the automatic-memory default, the quality acceptance bar and
   provider capacity within the free tier, retention/RPO/RTO, support and
   privacy ownership, alert recipient, asset and font rights, store account
   ownership, and mobile staffing.

## Rendering and font caveats

- The product uses Inter, Archivo Black, Permanent Marker and Caveat. None
  were installed on the build machine, so the decks use installed stand-ins:
  **Arial Black** (display), **Segoe UI / Segoe UI Semibold** (text),
  **Consolas** (code) and **Ink Free** (one annotation). The wordmark is a
  real screenshot crop. On machines without Segoe UI (e.g. macOS), PowerPoint
  or Keynote will substitute fonts and line breaks may shift. The PDFs embed
  the fonts as rendered.
- Colours are the product's tokens (`globals.css`): paper `#FFF7DF`, sun
  `#FFDA45`, pink `#FF438A`, deep pink `#CC1757`, ink `#151714`, navy
  `#202D3B`. Hard ink shadows are separate editable rectangles.
- Diagrams, tables, labels and text are native editable PowerPoint shapes.
  Screenshots and portraits are images.

## QA performed

- Generated with python-pptx 1.0.2; screenshots and portraits embedded as JPEG quality 90. Opened, exported to PDF and rendered
  slide by slide with Microsoft PowerPoint (Office 2024) on Windows.
- Every slide was inspected as a rendered image; clipping, overlaps, wrapped
  labels and title collisions were fixed over three render passes.
- Automated check: PDF page counts equal slide counts (27/27, 18/18); every
  text run and table cell of 6+ characters on each slide appears in the
  matching PDF page; every slide has speaker notes with source paths and the
  baseline.
- Colour pairs used for text meet WCAG AA contrast (ink on pink 5.5:1, white
  on deep pink 5.5:1, white on navy, ink-soft on paper and sun).
- Not done: review on macOS/Keynote or Google Slides, and projector or
  colour-blindness simulation.
