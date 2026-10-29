import pytest

from app.rules.extraction import normalize_titles, validate_note


def test_normalize_titles_preserves_first_cleaned_spelling_and_order() -> None:
    assert normalize_titles(
        [
            "  The  Spectacular Now ",
            "the spectacular now",
            "",
            " \n ",
            "Amélie",
            "AMÉLIE",
            "It",
            "It Chapter Two",
        ]
    ) == ["The Spectacular Now", "Amélie", "It", "It Chapter Two"]


def test_normalize_titles_collapses_whitespace_and_casefolds_unicode() -> None:
    assert normalize_titles(["Straße\tFilm\n", "STRASSE FILM"]) == ["Straße Film"]


def test_normalize_titles_accepts_empty_list() -> None:
    assert normalize_titles([]) == []


def test_validate_note_trims_outer_whitespace() -> None:
    assert validate_note(" \nInterstellar\n ") == "Interstellar"


def test_validate_note_accepts_character_limit() -> None:
    assert validate_note("x" * 20_000) == "x" * 20_000


@pytest.mark.parametrize("note", ["", " \n\t "])
def test_validate_note_rejects_blank_input(note: str) -> None:
    with pytest.raises(ValueError):
        validate_note(note)


@pytest.mark.parametrize(
    "note",
    ["x" * 20_001, " " + "x" * 20_000],
    ids=["oversized-text", "oversized-before-trimming"],
)
def test_validate_note_rejects_oversized_input_before_trimming(note: str) -> None:
    with pytest.raises(ValueError):
        validate_note(note)
