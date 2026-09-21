# Agent quality closeout — 2026-09-15

**Release decision: answer-quality acceptance remains open.** The completed
September 14 generation run produced 39 responses: **27 automated passes,
11 automated failures, one unavailable grade**. There were no answer-provider
errors or truncated answers. This is not a 39/39 quality pass.

## Evidence and tested configuration

- [Complete generation and original grades](quality-remediation-2026-09-14b.json).
- [Unavailable-grade retry](quality-rejudged-2026-09-14.json), preserved separately.
- [Live application journey transcript](journey-rehearsal-2026-09-14.txt).
- [Earlier measurement](quality-evidence-2026-09-13.md): 33 passes and six failures
  under an earlier rubric. Those results remain historical.

Working tree based on `1ed17eb`; executable-source/prompt/fixture/lock hash:
`f77bf299af1e2515b9d5f4817f601fc60ad9205ad00df5d5a922931c7bf4d1eb`.
The artifact records the same provenance for every row. Provider: Groq.
Default answer model: `openai/gpt-oss-120b`; Writing override and judge:
`qwen/qwen3.8-27b`. Reasoning effort: low. Timeout: 35 seconds. The initial
judge used temperature 0 and 700 output tokens; retry used 1,200 output tokens.
The artifact contains each specialist's exact temperature, output cap and prompt
version. No model substitution was made during the generation run.

Three samples were taken for each of ten personalization cases and three
unknown-personal-fact cases (Study, Career, Writing). Responses took 0.61–2.66
seconds in this paced, synthetic, single-account test. These timings exclude
judge calls and pacing, and are not concurrent-load or production latency evidence.

The first one-row [partial](quality-remediation-2026-09-14.json.partial) was
stopped after discovering conflicting Writing instructions. It was not resumed
across the configuration change. The completed `14b` run started fresh.

## Changes measured

Study and Research prompts request shorter plans. Study checks mastery
thresholds and forbids invented exercise references. Fitness is instructed to
count workouts and check equipment by day. Shopping's old instruction to claim
an item sits within an unknown budget was removed. Travel forbids invented
departure times. Writing no longer requires optional placeholders in a short bio.
The six prompt versions increased; model choices and settings remained unchanged.

The judge now covers unverified budget/support/schedule claims, equipment and
weekly frequency, unfinished artifacts and internal contradictions. This makes
the new pass count **not directly comparable** with the earlier, weaker rubric.
Prompt changes are implemented, but repeated failures show they are insufficient.

## Automated results and manual spot checks

- Modeer, Study, Research and Email personalization: three automated passes each.
  All nine unknown-fact responses passed. All 39 replies passed length limits.
- Career personalization: one pass, two failures. Sample 1 invents a stable visa
  and existing mentorship. Sample 2's judge objects to a 30% achievement example
  even though it is introduced with “e.g.”; that particular rationale is a false
  positive. The response nevertheless has an unrelated planning inconsistency:
  a proposed 12-week course is to finish by the end of next month without a
  calendar basis. Preserve both observations rather than silently upgrading it.
- Writing personalization: one pass, two failures. Samples 1–2 are a factual
  ten-word bio; the judge calls them insufficient for a conference program.
  That is a subjective completeness judgment, not fabricated personal data.
  They omit a supplied aspiration that sample 3 uses correctly. The new outputs
  avoid the earlier optional-placeholder problem, but are not uniformly useful.
- Travel personalization: one pass, two failures. Sample 2 asserts flight times,
  venue opening hours and boat departures without live evidence. Sample 1's
  judge incorrectly treats asking the user to verify possible entry rules as
  a current factual assertion. Manual inspection finds a different problem:
  it frames checks for UK citizens although only Manchester residence is known.
  Residence is not nationality. The original automated scores remain untouched.
- Shopping personalization: zero passes. All three assert an unverified fit to
  the budget; sample 2 invents a dollar currency. Sample 1 also describes older
  hardware as having the latest processor and promises future performance.
  A generic instruction to check current prices does not repair these claims.
- Finance personalization: two passes, one failure. Sample 3 asserts a current
  Dublin property-price range without a source. This is evidence of unsupported
  freshness, not proof that the quoted range is factually false.
- Fitness personalization: one pass, one failure, one unavailable grade. Sample
  3 explicitly requires a table on a no-equipment travel day. Manual inspection
  also rejects sample 1 despite its automated pass: it uses an unprovided bench,
  table/low bar and incline setup, and adds a Friday bodyweight circuit labelled
  as recovery. Sample 2 contains an unprovided bench and other equipment problems;
  its grader returned malformed JSON. The 1,200-token retry returned malformed
  JSON again. It remains **automatically ungraded**, with a documented manual
  constraint failure. The larger token budget did not resolve the parsing issue.

These are manual spot checks of consequential cases, not a blinded second
reviewer score for every dimension. The judge and Writing share a model family;
there is no independent human quality sign-off. Do not use the automated total
as a product-quality claim.

## Live application journey

All **13 checks passed** using the configured live Groq provider and a disposable
SQLite account: login, cookie properties, onboarding reply, extraction of four
synthetic facts, stored-memory retrieval, useful Study follow-up, supplied
context, separate conversations, persisted history, early client stream closure,
recorded completion state, successful retry and no unlabelled empty replies.
The temporary database was removed. No existing user data was modified.

This helper uses an in-process TestClient and a development-only synchronous
route for some steps. Its early stream closure does **not** simulate a real
network disconnect; the reply completed in the recorded run. Actual interrupted
transport and progressive delivery were checked separately through production
Caddy with a scripted upstream. See [local production rehearsal](launch-rehearsal-2026-09-14.md).
The journey is useful mechanism evidence, not broad answer-quality acceptance.

## Reproduction and next quality work

From `backend`, with the intended provider configured and sufficient quota:

```text
python quality_check.py --samples 3 --judge-model qwen/qwen3.8-27b --out ../docs/quality-NEW-ID.json
python -m tools.rejudge_quality --input ../docs/quality-NEW-ID.json --out ../docs/quality-NEW-ID-rejudged.json
python journey_check.py --db journey-NEW-ID.db
```

Use new output/database names, freeze application sources first, and retain all
original answers and judgments. The rejudge utility only retries unavailable
grades, checks source identity and records artifact/script hashes and the actual
judge budget; it never regenerates or overwrites the original answer evidence.

Priority work:

1. Add grounded contrast cases for budget currency, nationality versus residence,
   equipment by day and hypothetical versus asserted achievements. Include
   positive controls so a stricter rubric does not merely reject more answers.
2. Compare a compact, consistent instruction set and candidate model/reasoning
   settings on those cases. Avoid stacking more conflicting prompt rules or
   choosing a model from a single successful sample.
3. Resolve judge JSON reliability and calibrate false positives/negatives with
   adjudicated examples. Record unavailable grades separately at every stage.
4. Run the selected configuration on fresh held-out cases and repeat samples;
   require explicit owner acceptance criteria before beta/public quality sign-off.
