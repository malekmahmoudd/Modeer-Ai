from quality_check import build_cases, summarize


def test_repeated_summary_separates_outages():
    def row(passed, error="", output="reply", judge=None):
        return {
            "case": "case",
            "passed": passed,
            "error": error,
            "output": output,
            "review": {"passed": passed is not False},
            "judge": judge,
        }

    result = summarize(
        [
            row(True, judge={"available": True, "passed": True}),
            row(False, judge={"available": True, "passed": False}),
            row(None, error="429", output=""),
            row(None, judge={"available": False, "passed": False}),
        ]
    )["case"]
    assert result["attempts"] == 4
    assert result["responses"] == 3
    assert result["provider_errors"] == 1
    assert result["judge_available"] == 2
    assert result["evaluated"] == 2
    assert result["pass_rate"] == 0.5


def test_all_unavailable_has_no_quality_score():
    assert (
        summarize([{"case": "x", "passed": None, "output": "", "error": "429"}])["x"]["pass_rate"]
        is None
    )


def test_full_suite_has_personalization_and_unknown_facts():
    from quality_check import DEFAULT_AGENTS

    cases = build_cases(DEFAULT_AGENTS)
    assert len(cases) == 13
    assert len({case["id"] for _, case in cases}) == 13
