from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import PersonSummary, normalize_query


@pytest.mark.parametrize(("raw", "expected"), [(" x ", "x"), ("😀" * 200, "😀" * 200), (" Timothée O'Neil & 李😀 ", "Timothée O'Neil & 李😀")])
def test_query_codepoint_boundaries(raw: str, expected: str) -> None:
    assert normalize_query(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "😀" * 201])
def test_invalid_query(raw: str) -> None:
    with pytest.raises(SearchFailed, match="invalid_query"):
        normalize_query(raw)


def test_summaries_are_immutable() -> None:
    p = PersonSummary("Tom", None, None, ())
    with pytest.raises(FrozenInstanceError):
        setattr(p, "name", "Changed")  # noqa: B010 — exercising frozen assignment


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_policy_requires_positive_integers(value: object) -> None:
    values = dict.fromkeys(UsagePolicy.__dataclass_fields__, 10)
    values["ip_provider_total"] = cast(int, value)
    with pytest.raises(ValueError):
        UsagePolicy(**values)
