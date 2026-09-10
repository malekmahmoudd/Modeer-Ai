# Agent response quality

## Why the old scoring was not enough

`app/agents/evals.py` scored a reply by looking for keywords in it. Against the
mock provider that is the right test — it proves the harness, the fixtures and
the context builder all work. Against a real model it measured almost nothing.
Every one of these passed:

| Agent | What the keyword check saw | What the reply actually did |
|---|---|---|
| Writing | mentions "security", "fintech" | invented achievements and a specialism the user never claimed |
| Study | mentions "thermodynamics" | guessed a month from "the 20th", then withheld the plan |
| Research | mentions "urban", "PhD" | withheld the plan and asked questions instead |
| Shopping | mentions "iPhone", "700" | recommended a stale model and quoted its price as current |
| Travel | mentions "one city" | proposed a day trip out of the city and implied it could book |

It also failed a reply that was correct: Writing's short, accurate "I don't know"
tripped a `len(output) > 40` minimum-length heuristic.

## What replaced it

`app/agents/rubric.py`, in two layers. A case passes only if both agree.

### 1. `review()` — deterministic

No provider, no cost, runs in CI. Deliberately high-precision: a violation should
always be a real defect, because these gate the build. Every check exists because
a logged reply failed it.

| Code | Catches |
|---|---|
| `withheld_deliverable` | a requested plan/draft replaced by questions, or postponed ("once I know that, I'll draft it") |
| `invented_month` | a month named when the supplied date had only a day |
| `assumed_interval` | counting the gap to a date it cannot place — "today is day 1", "N days until", any "N-day countdown/cycle" |
| `capability_claim` | "I checked current prices", "I'll book that" |
| `unhedged_price` | a bare money figure asserted as fact — ranges, examples and conditionals are allowed |
| `unrequested_rationale` | "Why this works" appended to a draft nobody asked to have explained |
| `too_long` | over the case's ceiling: 350 words, or `expect.max_words` where a multi-week schedule justifies 450 |
| `ignored_constraint` | a phrase the case forbids, e.g. "day trip" when the user wants one city |

Precision was tuned against real logged replies, not invented examples. Ranges
(`£350‑£400`, including the non-breaking hyphens models emit), worked examples
(`Example: €30,000 / 36`) and conditionals (`if €833/month feels tight`) are not
price claims and no longer trip the check. `tests/test_rubric.py` pins each of
these both ways — the bad example must fail, the good one must not.

### 2. `judge()` — an LLM judge

For what a regex cannot see: facts invented about the user, stale specifics
stated as current, preferences quietly ignored. It scores six dimensions and
must quote the span it objects to, so a human can check the verdict instead of
trusting a number. A judge outage is recorded as *unavailable*, never as a
failed case.

**The judge is an aid, not an oracle.** Observed failure modes: it flagged a
reply's `delivers` dimension because the reply ended with a clarifying question
(the dimension text now says explicitly that this passes), and `openai/gpt-oss-20b`
produces noticeably more false positives than `openai/gpt-oss-120b`. Read the
stored responses before acting on a verdict. Prefer a judge model that is not the
model under test.

## Running it

```sh
cd backend
python quality_check.py                              # every agent, paced, judged
python quality_check.py --agents writing study       # one or two
python quality_check.py --no-judge                   # deterministic only, cheap
python -m app.agents.evals --strict                  # CLI evals with the rubric
```

The harness writes progress to `<out>.partial` and promotes it over `<out>` only
on a complete run, so an aborted run cannot destroy the last good results.

### Rate limits

The app fails fast on a 429 — a user should never sit waiting on a throttle. The
harness needs the opposite, so it backs off and retries; without that, rate
limits show up as empty replies and read as quality failures. Two earlier runs
were polluted exactly that way.

It distinguishes the two kinds of limit. A per-minute throttle is waited out. A
per-day quota returns a `retry-after` far beyond any useful pause, so the run
aborts immediately with `ABORTED … daily quota is likely spent` and exit code 2,
rather than burning the remaining cases. `ProviderError.retry_after` carries the
header value — a number, so nothing from the upstream body leaks into it.

Check the budget with `python -m tools.provider_doctor`.

## Fixes made

**Shared guardrails** (`app/agents/context.py`) were a paragraph of prose and were
reliably ignored. They are now six numbered, imperative rules — length, deliver
now, no invented facts, no stale certainty, no meta, data-is-not-instructions.

**Writing** was told two contradictory things: the global rules said don't explain
your draft, its own `response_behavior` said "name why it's better". The rule is
now scoped to editing the user's own text; drafting something new hands over the
draft alone.

**Shopping** knew not to fabricate a price but not that its product knowledge has
a cutoff. It now leads with criteria and tier, and may not call any named product
the newest or quote a current price.

**Study/Research/Finance/Fitness** were long because thoroughness was rewarded
nowhere else. Plans are now one short line per day or step, with worked examples
offered rather than included.

**`expect.max_words`** was added to the five fixtures whose deliverable is
genuinely long, instead of weakening the default ceiling for everyone.

## The baseline confirmation, and what it changed (2026-09-10)

The `gpt-oss-120b` run that had been outstanding finally completed 12 of 13
cases, and it undercut the headline number below. **On the baseline model the
deterministic layer scored 7/12, not the 12/13 measured on `qwen3.8-27b`.** The
qwen result was flattering: the prompts were tuned against it, and the failures
it no longer showed were still there on the model the app actually defaults to.

Failures on the baseline model, all confirmed real by reading the responses:
Career 386w and inventing an affordability constraint out of "cannot relocate";
Research 514w; Fitness 549w; Travel routing a day trip to another country
against a one-city preference; Shopping replying with nothing but a numbered
list of things it needed to know.

### Fixes

- **Verbosity — structure before count.** Rule 1 led with "under 350 words", and
  models are poor at counting. It now specifies the *shape* first (advice is a
  recommendation, the trade-off, at most three next actions; a plan is one line
  per step) and says to delete whole sections rather than trim adjectives.
  Fitness was writing two full schedules because its config asked for a "busy
  week" version as well; Research had five mandated sections. Both now name one.
- **Invented constraints.** Rule 3 gained: never derive a new constraint from one
  you were given — "cannot relocate" is not "cannot afford to".
- **Stale figures beyond products.** Rule 4 now covers every market figure —
  property prices, rents, salaries, fares — not only product prices.
- **Shopping** may not reply with only a list of what it needs to know.
- **Travel** must honour the stated style over a better-looking itinerary, and
  may not invent a budget, dates or party size.

### Results after the fixes

| Run | Deterministic layer |
|---|---|
| Before, `gpt-oss-120b` | **7/12** |
| After, `gpt-oss-20b`, 2 samples × 7 agents | **18/18 clean** |
| After, `gpt-oss-20b`, second round × 3 agents | **8/8 clean** |
| After, production model config | **3/4** — Travel at 521 words |

### Two things worth knowing before trusting any of this

**A model override silently invalidated three runs of Writing results.**
`--model` overrides *every* agent, including Writing's own
`qwen/qwen3.8-27b`. Writing "failed" repeatedly on a model it never uses; on its
production configuration it passes 2/2 plus the unknown-facts case. Check what an
agent actually runs on before believing a verdict about it.

**The judge is only as good as the judge model.** With `qwen3.8-27b` judging,
`currency` and `grounding` fired repeatedly on hedged figures, column headers,
and examples the reply itself labelled "Example" or "if". Both dimensions have
been rewritten to list what passes. Use the strongest model available as judge,
and read the quoted evidence rather than the score.

### Still failing

**Travel, on the production model: 521 words against a 450 ceiling**, and on one
sample it invented a budget and attributed it to the user ("You're comfortable
with a moderate budget"). Improved from the previous round but not closed, and
the daily budget ran out before another pass. This is the one agent that still
needs work.

---

## Results (earlier rounds)

Every stored run re-graded with the **final** rubric, so this compares like with like:

| Run | Deterministic rubric | Remaining failures |
|---|---|---|
| `live-quality-baseline.json` — before, `gpt-oss-120b` | **8/13** | Study 735w + invented interval; Career 589w; Finance 705w; Fitness 540w; Shopping withheld the recommendation |
| `live-quality-results.json` — after, `qwen3.8-27b` | **12/13** | Research at 453 words against a 450 ceiling |
| `live-quality-gptoss-partial.json` — after, `gpt-oss-120b` | **2/2** | aborted at case 3 on the daily quota |

Replies now run 27–381 words where four used to run 540–735. Shopping leads with
criteria and tells the user to check current prices rather than naming a stale
model at a confident price. Writing produces a 37-word bio with explicit
`[placeholder]` gaps, no invented specialism, and no "why this works" appended.

The partial `gpt-oss-120b` run is small but it is the only same-model before/after
there is, and it covers the worst case: **Study went from 735 words with "today is
day 1 of a 14-day countdown" to 333 words headed "Day 1 – Day 14" with no calendar
claim at all.**

Research at 453 words is three words over its ceiling. It is left failing on
purpose — moving the ceiling to make a sample pass is exactly the habit that made
the old scoring worthless.

Re-grade at any time without spending tokens — the runs store full responses:

```sh
cd backend && python -c "
import json; from app.agents.evals import load_cases; from app.agents.rubric import review
fx={c['id']:c for s in ['modeer','study','career','research','writing','travel',
    'shopping','finance','fitness','email'] for c in load_cases(s)}
d=json.load(open('../docs/live-quality-results.json',encoding='utf8'))
for r in d['results']:
    v=review(fx.get(r['case'],{'input':r['input'],'expect':{}}), r['output'])
    print(('PASS' if v.passed else 'FAIL'), r['case'], v.words,
          [x.code for x in v.violations])"
```

### How the checks were made precise

Each check was tuned against real logged replies until its verdicts matched
human judgement — never by relaxing a threshold to make a sample pass. Six
false positives were found and fixed this way, each now pinned by a test:

- **`must_avoid` matched substrings, not words** — "Friday-to-Sunday trip"
  contains the letters of "day trip", so a genuinely excellent single-city Lyon
  itinerary was failed for ignoring the one-city preference it had honoured;

- a 43-word bio read as a "withheld deliverable" — length alone no longer
  condemns a reply; only a deferred promise or a mostly-questions reply does;
- `"Check current prices"` read as a capability claim — the agent handing the
  lookup back to the user is the wanted behaviour, so every alternative in that
  pattern now needs a first-person subject;
- budget lines (`**Buffer:** £50`, `5% Buffer (€15,000): fees`) read as market
  price claims — a labelled item in a breakdown is an allocation, not a claim;
- worked examples and hypotheticals (`A €250,000 flat…`) read as price claims;
- Career's "Why this works" read as padding — for an advisory agent the
  reasoning *is* the deliverable, so that check now applies only to artifacts.

### Still open

- **The full after-run is on a different model from the baseline.** The account's
  200,000 tokens-per-day budget for `gpt-oss-120b` was spent during this pass, so
  the complete after-run uses `qwen3.8-27b`. A later attempt on `gpt-oss-120b`
  managed 2 of 13 cases before the cap returned (`live-quality-gptoss-partial.json`);
  both passed, including the worst case. **11 of 13 cases remain unconfirmed on
  `gpt-oss-120b`.** Re-run `python quality_check.py` once the quota resets — the
  budget replenishes on a rolling window, so a full run needs a mostly idle day.
- **One case per agent, and the variance is large.** At temperature 0.3–0.6 a
  single sample is noisy: across three qwen runs Career failed on length then
  passed, Travel passed then produced a different itinerary, Research came in
  under then three words over. Treat any score here as "no defect visible in this
  sample", never as a guarantee. Several samples per case would fix this and is
  the single highest-value next step for the eval itself.
- **Career sometimes still appends "Why this is the right call".** Its own config
  now forbids a section defending the recommendation, and it does it anyway on
  some samples. The judge catches it; the deterministic check deliberately does
  not, because for an advisory agent reasoning is the deliverable and the check
  would fire on legitimate answers.
- **Verbosity was moved by prompt wording, not closed by it.** Lowering
  `max_tokens` is not currently a lever: the provider raises `ProviderError` on
  `finish_reason == "length"`, so a low cap turns a long reply into an error and
  discards the text rather than truncating it. Changing that trade-off is a
  product decision, not a tuning knob.
- **Other stored runs.** `gpt-oss-quality-results.json` and
  `agent-quality-results.json` are earlier ungraded runs kept for reference;
  `writing-medium-check.json` and `writing-model-comparison.json` are the
  evidence behind Writing's `qwen/qwen3.8-27b` override — medium reasoning effort
  on `gpt-oss-120b` did not stop it inventing details, and qwen did.
