"""Keys that name the same fact.

The extractor invents a key per fact, and on different days it called the
same thing "city", "location" and "lives_in" — three rows, two of them stale.
Keys in one group here are one fact: a new value under any of them updates the
row that already exists, whatever it is called.
"""

from __future__ import annotations

_GROUPS: tuple[frozenset[str], ...] = tuple(
    frozenset(group)
    for group in (
        {
            "location",
            "city",
            "current_city",
            "home_city",
            "lives_in",
            "based_in",
            "current_location",
            "residence",
            "place_of_residence",
        },
        {"field_of_study", "major", "study_field", "degree_subject", "course_of_study"},
        {"study_year", "year_of_study", "academic_year", "year_in_school"},
        {"university", "school", "college", "institution", "uni"},
        {"job_title", "job", "occupation", "current_role", "position", "profession", "current_job"},
        {"employer", "company", "workplace", "current_employer", "current_company"},
        {"native_language", "first_language", "mother_tongue"},
        {"languages", "languages_spoken", "spoken_languages"},
        # Restrictions and allergies are NOT here: "vegetarian" must never
        # overwrite "severe nut allergy". They stay separate facts.
        {"diet", "dietary_preference", "diet_preference"},
        {"preferred_name", "nickname", "name", "first_name"},
        {"age", "user_age"},
        {"timezone", "time_zone"},
    )
)
_BY_KEY = {key: group for group in _GROUPS for key in group}


def same_fact_keys(key: str) -> frozenset[str]:
    """Every key that names the same fact as ``key``, including itself."""
    return _BY_KEY.get(key, frozenset({key}))


def canonical_keys() -> list[str]:
    """One preferred key per group, for the extractor to reuse."""
    return sorted(min(group, key=_preference) for group in _GROUPS)


_PREFERRED = {
    "location",
    "field_of_study",
    "study_year",
    "university",
    "job_title",
    "employer",
    "native_language",
    "languages",
    "diet",
    "preferred_name",
    "age",
    "timezone",
}


def _preference(key: str) -> tuple[int, str]:
    return (0 if key in _PREFERRED else 1, key)
