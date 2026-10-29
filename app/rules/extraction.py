"""Plain Python validation and normalization for movie-note extraction."""

MAX_NOTE_CHARACTERS = 20_000


def validate_note(note: str) -> str:
    """Reject oversized or blank notes, then return their trimmed text."""
    if len(note) > MAX_NOTE_CHARACTERS:
        raise ValueError("Notes must contain at most 20,000 characters before trimming.")
    cleaned_note = note.strip()
    if not cleaned_note:
        raise ValueError("Notes must contain non-whitespace text.")
    return cleaned_note


def normalize_titles(titles: list[str]) -> list[str]:
    """Collapse whitespace and keep the first spelling of each casefolded title."""
    normalized_titles: list[str] = []
    seen: set[str] = set()
    for title in titles:
        cleaned_title = " ".join(title.split())
        key = cleaned_title.casefold()
        if cleaned_title and key not in seen:
            normalized_titles.append(cleaned_title)
            seen.add(key)
    return normalized_titles
