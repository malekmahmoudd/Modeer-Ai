# Keeping track between conversations

Since 2026-09-25. Everything here works from chat and adds no provider calls,
apart from the running summary. The **Plans** page (`/plans`) lists follow-ups
(done, dismiss, add to calendar), saved plans (tick steps, "start again today",
calendar export) and check-ins (delete). Each memory row on the Memory page has
"why the team knows this", with earlier values and undo. Everything also
surfaces through the daily briefing and the notice under a reply.

| Feature | From chat | Where it shows | API |
|---|---|---|---|
| **Follow-ups** | Mention a dated thing: "interview next Thursday". The turn analysis returns it as an event with an absolute date, 0–400 days ahead. | Counting down in the owning agent's and Leo's context and in the briefing (next 7 days). Once passed, that agent asks how it went, once (`asked_at`); the briefing asks for 14 days. | `GET/POST /api/followups`, `PATCH/DELETE /api/followups/{id}`, `GET /api/followups/calendar.ics` |
| **Saved plans** | "Save this plan" keeps the previous reply; "make me a plan and save it" keeps this one. "Done with day 3" / "finished week 2" / "completed step 4" ticks steps on that agent's latest active plan. | The owning agent (and Leo) sees progress and the next step; due or overdue steps appear in the briefing. | `GET/POST /api/plans` (`{message_id}`), `GET/PATCH/DELETE /api/plans/{id}`, `PATCH /api/plans/{id}/steps/{step_id}` `{done}`, `GET /api/plans/{id}/calendar.ics` |
| **Check-ins** | Report something done: "ran 5k", "spent 40 on food". | The owning agent sees the last 14 days (up to 10 lines). | `GET /api/checkins?agent_id=&since=`, `DELETE /api/checkins/{id}` |
| **Weekly review** | Ask Leo; he is given the same data. | A "Your week" item in Monday's briefing. | `GET /api/briefings/week` |
| **Allowance** | — | The reply notice says "About N messages left today" at 3 or fewer. | `GET /api/usage/me`; also `allowance` in the `memory` event |
| **About me** | Start a message with "This is about me:" or "Here's my CV:". The paste guard is skipped for it, and the analysis gets a larger output budget. | Facts, as usual. | `POST /api/users/me/about` `{text}` |
| **Why it knows** | — | — | `GET /api/memory/{shared\|agent}/{id}/source` (the message it was learned from, and its history), `POST …/undo` (restore the value the last automatic update replaced) |
| **Running summary** | Automatic in long conversations. | Once more than 20 messages are unsummarised, all but the last 12 are folded into a ≤120-word summary. It goes in the prompt as "Earlier in this conversation"; those turns are no longer sent. | `summary` in the data export |

Plan parsing (`app/tracking/plans.py`) is deterministic. It reads list items,
numbered lines, "Day N" / "Week N" lines, and table rows (the first row is the
header). The first heading becomes the title. "Day N" and "Week N" steps are
dated from the day the plan was saved. Fewer than two steps means nothing is
saved.

Check-ins and follow-ups are automatic learning, so they stop when automatic
memory is off. Saving and ticking plans are explicit requests, so they don't.
A follow-up or check-in whose text looks sensitive is not stored automatically
(same keyword backstop as facts). Follow-ups are visible only to Leo and the
agent they belong with.

The weekly review and briefing items are built from stored data with no model
call. The review is plain counts and titles: honest, not eloquent.

Schema: migration **0006** (`followups`, `plans`, `plan_steps`, `checkins`,
`conversations.summary/summary_count`, `*_memories.source_message_id`). All of
it is in the data export and is deleted with the account.

## Council fixes (2026-09-25, later)

A 50-expert review found these in the first version. All are fixed and tested
(`backend/tests/test_tracking.py`, `test_time_team_memory.py`):

- **Sensitive data fails closed.** Follow-ups and check-ins now carry the
  model's `sensitive` flag, like facts. A missing flag counts as sensitive, and
  the keyword backstop can raise it but never lower it. The backstop
  (`memory/sensitivity.py`) now covers:
  - injuries, care and appointments
  - eating, weight and restriction; food intake, calories, fasting and body
    weight are never logged as check-ins
  - crisis terms
  - bereavement and legal proceedings
  - money trouble and Gulf ID terms
  - Arabic, matched after folding alef, taa marbuta and alef maqsura
- **Follow-ups close.**
  - The briefing asks "How did it go?" only within 3 days of the event, and
    only until an agent has asked in chat.
  - The user's answer closes the follow-up and keeps a one-line `outcome`.
  - Unanswered follow-ups are dismissed 14 days after the day.
  - A title seen again within 3 days of the same date is the same event; the
    same title weeks apart is a new one.
- **Plan requests happen before the reply.** "Save this plan", "done with day 3"
  and "shift my plan" run first. The agent is told exactly what happened, under
  "Done by the app", so it never claims a save that failed. "Make me a plan and
  save it" saves the new reply afterwards, and the agent says it *will* be
  saved.
- **Triggers ignore questions and negations.** "I haven't done day 3", "how did
  week 2 go?" and "don't save this plan" do nothing. Arabic requests work
  ("احفظ هذه الخطة", "خلصت اليوم ٣"). Leo can tick any saved plan.
- **Plan dates:**
  - "## Day 1" headings are steps, with their list folded in.
  - Weekdays are dated ("Mon — …", "Day 2 (Wed)").
  - Ranges are read as their first day ("Days 3–4").
  - `PATCH /api/plans/{id}` accepts `starts_on`, and every step is re-dated
    from it.
  - "Shift my plan" moves the remaining steps so the next one is today.
  - Missed steps read "not ticked yet", not "overdue".
- **.ics:** carriage returns are escaped and lines are folded at 75 octets.

## Trips, logs, handoffs and the week (2026-09-25, last batch)

Migration **0008** adds `followups.ends_on`, `checkins.details`,
`agent_memories.seen_at` and `users.suspended_at`. All of it is in the export.
Tests: `backend/tests/test_team_extras.py`.

- **Trips have an end date.** The analysis may return `end_date` with an event
  (after the start, at most 90 days later). A trip in progress reads
  "happening now", and Tessa asks how it went only after the last day. The
  Plans page shows "Thu 10 Nov → Mon 14 Nov". The API takes `ends_on` and
  rejects an end before the start.
- **Structured check-ins.** A check-in may carry `details`, each field checked
  against bounds in code:
  - for a workout: exercise, sets, reps, load and unit, RPE, distance, duration
  - for money: currency (a three-letter code) and direction (`out`/`in`)
  Maddie gets a "Progression from their logs" section: per exercise, the last
  session and the best load over 12 weeks.
- **Money adds up in code.** The weekly review sums spending (`direction` out)
  per currency; the model is told the totals are exact. Emma is told to show
  arithmetic inline and check it.
- **Leo's weekly review.** When the message asks about the week (English or
  Arabic), or on Mondays, Leo gets the past week and the next, spending, and
  goals quiet for 14 days or more. He answers in three parts: what moved,
  what's next, one quiet goal.
- **Handoff notes are picked up and expire.** A note is marked seen when its
  teammate first replies with it in context; others see "picked up" or "not
  yet seen". Seen notes go after 14 days, unseen ones after 30.
- **Memory ranking.** Past the memory ceiling, facts are ordered pinned first,
  then by word overlap with the message, then by recency, so the relevant old
  fact isn't the one cut.

