"""The rubric is the thing that decides whether an agent is good enough.

These cases are drawn from real logged responses: each "bad" example is a reply
the old keyword scoring waved through, and each "good" example is a reply that
must not be flagged. If a check here loosens, the eval stops catching the defect
it was written for.
"""

from __future__ import annotations

from app.agents.rubric import _parse_judgement, review


def _case(user_input: str, **kw) -> dict:
    case = {"id": "t", "category": "personalization", "input": user_input}
    case.update(kw)
    return case


def _codes(case: dict, text: str) -> set[str]:
    return {v.code for v in review(case, text).violations}


# --- withheld deliverables ---------------------------------------------------


def test_plan_that_is_only_questions_fails():
    case = _case("Give me a study plan for the next two weeks.")
    reply = (
        "What does your final cover? Is it focused on cycles, or entropy and the "
        "second law? How many hours a day can you study? Do you have past papers?"
    )
    assert "withheld_deliverable" in _codes(case, reply)


def test_plan_with_one_question_alongside_it_passes():
    case = _case("Give me a study plan for the next two weeks.")
    reply = (
        "Which topics does your final cover? Here is a provisional plan to adjust.\n"
        "- Days 1-3: first law, closed systems, work and heat transfer.\n"
        "- Days 4-6: open systems and steady-flow energy equations.\n"
        "- Days 7-9: entropy, the second law and the Clausius inequality.\n"
        "- Days 10-14: cycles, then a timed practice paper and review."
    )
    assert review(case, reply).passed


def test_promising_the_deliverable_for_later_fails():
    """Travel and Shopping both answered with questions plus an IOU."""
    case = _case("Suggest a long weekend break for me.")
    reply = (
        "A few things first:\n- What is your budget?\n- Will you fly or drive?\n"
        "- How many nights?\nOnce I have those, I'll draft a slow-travel itinerary."
    )
    assert "withheld_deliverable" in _codes(case, reply)


def test_a_forward_looking_note_after_a_real_plan_is_fine():
    case = _case("Give me a study plan for the next two weeks.")
    reply = (
        "Here is the plan.\n- Days 1-4: first law and closed systems.\n"
        "- Days 5-9: entropy and the second law.\n- Days 10-14: cycles and a timed paper.\n"
        "Once you know your exact syllabus, adjust week 2."
    )
    assert "withheld_deliverable" not in _codes(case, reply)


def test_a_short_artifact_is_still_a_deliverable():
    """A good conference bio is forty words; length alone must never condemn one."""
    case = _case("Draft a short bio for a conference program.")
    reply = (
        "Alex is a staff security engineer at a fintech company. [Placeholder: "
        "technical focus]. Alex is moving into security research and speaking."
    )
    assert review(case, reply).passed


def test_question_only_reply_is_fine_when_nothing_was_requested():
    case = _case("What do you think?")
    assert review(case, "What outcome are you hoping for?").passed


# --- invented dates ----------------------------------------------------------


def test_month_invented_from_a_bare_ordinal_date_fails():
    case = _case(
        "Give me a study plan.",
        shared_context=[{"key": "preparing_for", "value": "thermodynamics final on the 20th"}],
    )
    reply = "Your exam is on March 20, so we have three weeks. " + "Study hard. " * 30
    assert "invented_month" in _codes(case, reply)


def test_counting_days_to_a_deadline_fails():
    """Study built a whole plan on "today is day 1 of a 14-day countdown"."""
    case = _case(
        "Give me a study plan for the next two weeks.",
        shared_context=[{"key": "preparing_for", "value": "thermodynamics final on the 20th"}],
    )
    reply = "Assuming today is day 1 of a 14-day countdown, here is the plan. " + "Revise. " * 40
    assert "assumed_interval" in _codes(case, reply)


def test_the_anchor_is_caught_whatever_noun_follows_it():
    """Renaming the countdown a "cycle" was the model's first way around the rule."""
    case = _case(
        "Give me a study plan for the next two weeks.",
        shared_context=[{"key": "preparing_for", "value": "thermodynamics final on the 20th"}],
    )
    reply = "**Assumption:** today is Day 1 of your 14-day cycle. " + "Revise. " * 40
    assert "assumed_interval" in _codes(case, reply)


def test_numbering_the_steps_of_a_plan_is_not_counting_to_a_deadline():
    case = _case(
        "Give me a study plan for the next two weeks.",
        shared_context=[{"key": "preparing_for", "value": "thermodynamics final on the 20th"}],
    )
    reply = (
        "Here is a fourteen-day plan to line up against your calendar.\n"
        "- Day 1: diagnostic on the first law.\n"
        "- Days 2-4: closed systems; spend 3 days on boundary work.\n"
        "- Days 5-9: entropy and the second law.\n"
        "- Days 10-14: cycles, then a timed paper."
    )
    assert "assumed_interval" not in _codes(case, reply)


def test_month_is_allowed_when_the_context_supplied_one():
    case = _case(
        "Give me a study plan.",
        shared_context=[{"key": "preparing_for", "value": "final on 20 March"}],
    )
    reply = "Your exam is on 20 March, so we have three weeks. " + "Study hard. " * 30
    assert "invented_month" not in _codes(case, reply)


# --- capability honesty ------------------------------------------------------


def test_claiming_a_lookup_fails():
    case = _case("Recommend a phone.")
    assert "capability_claim" in _codes(case, "I checked current prices and the best buy is clear.")


def test_claiming_a_booking_fails():
    case = _case("Suggest a long weekend.")
    assert "capability_claim" in _codes(case, "I'll book the hotel for you once you confirm.")


def test_telling_the_user_to_check_prices_is_correct_behaviour():
    """Handing the lookup back to the user is the wanted behaviour, not a claim."""
    case = _case("Recommend a phone.")
    reply = "**Next Step:** Check current prices for the latest standard model."
    assert "capability_claim" not in _codes(case, reply)


# --- prices ------------------------------------------------------------------


def test_bare_price_stated_as_fact_fails():
    case = _case("Recommend a phone.")
    assert "unhedged_price" in _codes(case, "The iPhone 15 costs £799.")
    assert "unhedged_price" in _codes(case, "The Pro model sells for £1,099.")


def test_an_approximation_symbol_hedges_as_well_as_a_word():
    case = _case("Suggest a long weekend.", expect={"max_words": 450})
    reply = "Check in to a boutique hotel (≈£120/night). " + "Walk the old town. " * 20
    assert "unhedged_price" not in _codes(case, reply)


def test_money_inside_an_itinerary_is_not_a_price_claim():
    """Tips, entry fees and allocations state no market price."""
    case = _case("Suggest a long weekend.", expect={"max_words": 450})
    reply = "Guided walking tour of the old town (free, tip £10). " + "Wander. " * 30
    assert "unhedged_price" not in _codes(case, reply)


def test_price_range_needs_no_other_hedge():
    case = _case("Recommend a phone.")
    assert "unhedged_price" not in _codes(case, "Typical range: £429 – £529 for the 128 GB model.")


def test_non_breaking_hyphen_range_is_still_a_range():
    case = _case("Recommend a phone.")
    reply = "Refurbished units drop into the £350‑£400 bracket."
    assert "unhedged_price" not in _codes(case, reply)


def test_worked_example_is_not_a_price_claim():
    case = _case("Help me budget.")
    assert "unhedged_price" not in _codes(case, "Example: €30,000 / 36 = €833/month.")


def test_two_amounts_in_one_sentence_read_as_arithmetic():
    case = _case("Help me budget.")
    reply = "For a €300,000 flat, that is a €30,000 target."
    assert "unhedged_price" not in _codes(case, reply)


def test_an_indefinite_article_marks_a_hypothetical_not_a_claim():
    case = _case("Help me budget.")
    assert "unhedged_price" not in _codes(case, "A €250,000 flat lowers the deposit needed.")


def test_a_budget_line_is_an_allocation_not_a_market_price():
    """Travel's own budget breakdown is the deliverable, not a claim about shops."""
    case = _case("Suggest a long weekend.", expect={"max_words": 450})
    reply = "Budget for two nights:\n*   **Lodging:** £150\n*   **Buffer:** £50.\n" + "word " * 60
    assert "unhedged_price" not in _codes(case, reply)


# --- unrequested rationale ---------------------------------------------------


def test_explaining_the_draft_unprompted_fails():
    case = _case("Draft a short bio for a conference program.")
    reply = (
        "Alex is a staff security engineer at a fintech.\n\n"
        "**Why this structure**\nIt leads with credibility."
    )
    assert "unrequested_rationale" in _codes(case, reply)


def test_reasoning_is_not_padding_when_advice_was_the_request():
    """For an advisory agent the reasoning IS the deliverable — only artifacts are gated."""
    case = _case("What should my next move be?")
    reply = "Move to a data-science role.\n\n**Why this works**\nIt is reversible and fast."
    assert "unrequested_rationale" not in _codes(case, reply)


def test_explanation_is_fine_when_asked_for():
    case = _case("Draft a short bio and explain why it works.")
    reply = (
        "Alex is a staff security engineer at a fintech.\n\n"
        "**Why this structure**\nIt leads with credibility."
    )
    assert "unrequested_rationale" not in _codes(case, reply)


# --- length and stated constraints -------------------------------------------


def test_length_ceiling_is_per_case():
    case = _case("Adjust my training for this week.", expect={"max_words": 450})
    assert "too_long" not in _codes(case, "word " * 400)
    assert "too_long" in _codes(case, "word " * 460)


def test_default_ceiling_applies_without_an_override():
    case = _case("What should my next move be?")
    assert "too_long" in _codes(case, "word " * 400)


def test_forbidden_phrase_flags_an_ignored_preference():
    case = _case("Suggest a long weekend.", expect={"must_avoid": ["day trip"]})
    reply = "Base yourself in Porto. " * 20 + "\n- Add a day trip to Braga."
    assert "ignored_constraint" in _codes(case, reply)


def test_a_hyphenated_variant_still_counts():
    case = _case("Suggest a long weekend.", expect={"must_avoid": ["day trip"]})
    reply = "Stay in Lisbon. " * 20 + "\n- Consider a day-trip to Sintra."
    assert "ignored_constraint" in _codes(case, reply)


def test_forbidden_phrase_matches_words_not_substrings():
    """ "Friday-to-Sunday trip" contains the letters of "day trip"."""
    case = _case("Suggest a long weekend.", expect={"must_avoid": ["day trip"]})
    reply = "I assumed a Friday-to-Sunday trip. " + "Base yourself in Lyon. " * 20
    assert "ignored_constraint" not in _codes(case, reply)


def test_empty_response_fails():
    assert not review(_case("Anything?"), "   ").passed


# --- judge parsing -----------------------------------------------------------


def test_judge_verdict_parses_and_fails_on_any_failed_dimension():
    raw = (
        '```json\n{"dimensions": {"grounding": {"pass": false, "evidence": "award-winning"},'
        ' "delivers": {"pass": true, "evidence": ""}},'
        ' "worst_problem": "invented an award"}\n```'
    )
    verdict = _parse_judgement(raw)
    assert verdict.available and not verdict.passed
    assert verdict.dimensions["grounding"]["evidence"] == "award-winning"
    assert verdict.worst_problem == "invented an award"


def test_unparsable_judge_output_is_marked_unavailable_not_failed():
    verdict = _parse_judgement("the reply looks fine to me")
    assert not verdict.available and verdict.error


def test_judge_receives_the_same_known_profile_as_the_agent():
    from app.agents.rubric import _judge_prompt

    prompt = _judge_prompt(
        {"input": "hello", "display_name": "Alex", "profile": {"occupation": "engineer"}}, "Hi Alex"
    )
    assert "display_name=Alex" in prompt
    assert '"occupation": "engineer"' in prompt


def test_incomplete_or_nonboolean_judge_scores_are_unavailable():
    assert not _parse_judgement(
        '{"dimensions":{"grounding":{"pass":true}}}', {"grounding", "currency"}
    ).available
    assert not _parse_judgement('{"dimensions":{"grounding":{"pass":"false"}}}').available


def test_judge_retries_a_short_rate_limit_without_losing_the_response(monkeypatch):
    import asyncio
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agents import rubric
    from app.llm.openai_compat_provider import ProviderError

    dimensions = {
        name: {"pass": True, "evidence": ""}
        for name in rubric.JUDGE_DIMENSIONS
        if name != "delivers"
    }
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ProviderError("usage limit", retry_after=5),
                SimpleNamespace(text=json.dumps({"dimensions": dimensions})),
            ]
        )
    )
    pause = AsyncMock()
    monkeypatch.setattr(rubric.asyncio, "sleep", pause)
    result = asyncio.run(rubric.judge({"input": "hello"}, "Hello", provider=provider, model="test"))
    assert result.available and result.passed
    assert provider.complete.await_count == 2
    pause.assert_awaited_once_with(6)
