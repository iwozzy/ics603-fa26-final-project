from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeGuard

type TimelineDirection = Literal['older', 'newer']
type TimelineMode = Literal['initial', 'older', 'newer', 'future_boundary', 'anchored']
type TimelineCursorKind = Literal['row', 'future_boundary']

MAX_MOVIE_ID = 9007199254740991


def valid_movie_id(value: object) -> TypeGuard[int]:
    return type(value) is int and 1 <= value <= MAX_MOVIE_ID


@dataclass(frozen=True)
class MovieSummary:
    id: int
    title: str
    overview: str | None
    poster_image_url: str | None
    release_date: date


@dataclass(frozen=True)
class TimelinePosition:
    release_date: date
    id: int


@dataclass(frozen=True)
class TimelineRequest:
    limit: int = 20
    cursor: str | None = None
    direction: TimelineDirection | None = None
    anchor_date: date | None = None
    anchor_id: int | None = None


@dataclass(frozen=True)
class TimelineSelection:
    mode: TimelineMode
    limit: int
    position: TimelinePosition | None = None
    boundary_date: date | None = None


@dataclass(frozen=True)
class TimelineWindow:
    items: tuple[MovieSummary, ...]
    has_older: bool
    has_newer: bool
    as_of: date | None
    anchor_index: int | None


@dataclass(frozen=True)
class TimelinePage:
    items: tuple[MovieSummary, ...]
    older_cursor: str | None
    newer_cursor: str | None
    as_of: date | None
    anchor_index: int | None


@dataclass(frozen=True)
class TimelineCursor:
    kind: TimelineCursorKind
    release_date: date
    id: int | None = None
