"""Validation shared by PATCH models with required stored fields."""

from typing import Any


def reject_null(value: Any) -> Any:
    """Omission leaves a field alone; an explicit null is not a valid value."""
    if value is None:
        raise ValueError("must not be null")
    return value
