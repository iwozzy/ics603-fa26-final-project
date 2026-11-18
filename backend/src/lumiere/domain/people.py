from dataclasses import dataclass


@dataclass(frozen=True)
class PersonSummary:
    name: str
    portrait_url: str | None = None
    department: str | None = None
    known_for: tuple[str, ...] = ()
