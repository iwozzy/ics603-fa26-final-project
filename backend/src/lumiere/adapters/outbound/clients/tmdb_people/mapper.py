import re
from typing import cast

from lumiere.adapters.outbound.clients.tmdb_people.dto import PersonDTO
from lumiere.domain.people import CatalogProvider, PersonSummary


def nonblank(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def profile_path(value: object) -> str | None:
    path = nonblank(value)
    if not path or not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
        return None
    if ".." in path.split("/") or not path.lstrip("/"):
        return None
    return "/" + path.lstrip("/")


def image_url(value: object) -> str | None:
    path = profile_path(value)
    return "https://image.tmdb.org/t/p/w180_and_h180_face" + path if path else None


def map_person(person: PersonDTO) -> PersonSummary | None:
    name = nonblank(person.name)
    if name is None:
        return None
    titles: list[str] = []
    if isinstance(person.known_for, list):
        for raw in cast(list[object], person.known_for):
            if not isinstance(raw, dict):
                continue
            item = cast(dict[str, object], raw)
            field = {"movie": "title", "tv": "name"}.get(str(item.get("media_type")))
            title = nonblank(item.get(field)) if field else None
            if title:
                titles.append(title)
    return PersonSummary(provider=CatalogProvider.TMDB, provider_id=person.id, name=name, known_for_department=nonblank(person.known_for_department), profile_image_url=image_url(person.profile_path), known_for=tuple(titles[:3]), provider_profile_path=profile_path(person.profile_path))
