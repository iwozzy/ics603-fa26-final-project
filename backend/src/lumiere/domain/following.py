from dataclasses import dataclass

from lumiere.domain.people import CatalogProvider, PersonSummary


@dataclass(frozen=True)
class PersonIdentity:
    provider: CatalogProvider
    provider_id: int


@dataclass(frozen=True)
class FollowingSnapshot:
    people: tuple[PersonSummary, ...]
    limit: int
