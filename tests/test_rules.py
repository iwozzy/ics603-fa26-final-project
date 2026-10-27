import pytest

from app import rules


@pytest.mark.parametrize("selected_person_id", [10, 20])
def test_person_confirmation_accepts_confirmed_returned_person(
    selected_person_id: int,
) -> None:
    rules.validate_person_confirmation(
        returned_person_ids=frozenset({10, 20}),
        selected_person_id=selected_person_id,
        confirmed=True,
    )


def test_person_confirmation_rejects_unconfirmed_returned_person() -> None:
    with pytest.raises(ValueError):
        rules.validate_person_confirmation(
            returned_person_ids=frozenset({10, 20}),
            selected_person_id=20,
            confirmed=False,
        )


@pytest.mark.parametrize("returned_person_ids", [frozenset(), frozenset({10, 20})])
@pytest.mark.parametrize("confirmed", [False, True])
def test_person_confirmation_rejects_person_not_in_results(
    returned_person_ids: frozenset[int], confirmed: bool
) -> None:
    with pytest.raises(ValueError):
        rules.validate_person_confirmation(
            returned_person_ids=returned_person_ids,
            selected_person_id=30,
            confirmed=confirmed,
        )
