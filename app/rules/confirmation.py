"""Plain Python rules for confirming a person to follow."""


def validate_person_confirmation(
    returned_person_ids: frozenset[int], selected_person_id: int, confirmed: bool
) -> None:
    """Require explicit confirmation of a person from the returned search results."""
    if not confirmed:
        raise ValueError("The user must confirm their choice before following a person.")
    if selected_person_id not in returned_person_ids:
        raise ValueError("The selected person must appear in the returned search results.")
