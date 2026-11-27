import base64
import json
from datetime import date
from typing import cast
from uuid import UUID

import pytest

from lumiere.adapters.inbound.http.timeline_cursor import Base64TimelineCursorCodec
from lumiere.domain.errors import TimelineFailed
from lumiere.domain.timeline import TimelineCursor

PROFILE = UUID(int=1)
DAY = date(2024, 2, 29)


def wire(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def payload(token: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))))


@pytest.mark.parametrize('cursor,fields', [
    (TimelineCursor('row', DAY, 1), {'v', 'kind', 'date', 'id', 'scope'}),
    (TimelineCursor('row', date.min, 9007199254740991), {'v', 'kind', 'date', 'id', 'scope'}),
    (TimelineCursor('future_boundary', DAY), {'v', 'kind', 'date', 'scope'}),
])
def test_roundtrip_is_deterministic_and_uses_exact_fields(cursor: TimelineCursor, fields: set[str]) -> None:
    codec = Base64TimelineCursorCodec()
    token = codec.encode(cursor, PROFILE)
    decoded = payload(token)

    assert token == Base64TimelineCursorCodec().encode(cursor, PROFILE)
    assert '=' not in token and len(token.encode('ascii')) <= 1024
    assert set(decoded) == fields
    assert (decoded['v'], decoded['kind'], decoded['date']) == (1, cursor.kind, cursor.release_date.isoformat())
    assert codec.decode(token, PROFILE) == cursor


@pytest.mark.parametrize('changes', [
    {'v': 0}, {'v': 2}, {'v': True}, {'v': 1.0},
    {'kind': 'other'}, {'kind': 'future_boundary'}, {'kind': []},
    {'date': 20240229}, {'date': '2024-2-29'}, {'date': '20240229'},
    {'date': '2024-W09-4'}, {'date': '2023-02-29'}, {'date': '2024-02-29T00:00:00'},
    {'id': 0}, {'id': -1}, {'id': True}, {'id': 1.0}, {'id': '1'},
    {'id': 9007199254740992}, {'id': None}, {'extra': None}, {'scope': 'changed'},
])
def test_cursor_decode_rejects_noncanonical_fields(changes: dict[str, object]) -> None:
    codec = Base64TimelineCursorCodec()
    fields = payload(codec.encode(TimelineCursor('row', DAY, 1), PROFILE))

    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        codec.decode(wire(json.dumps(fields | changes).encode()), PROFILE)


@pytest.mark.parametrize('missing_field', ['v', 'kind', 'date', 'id', 'scope'])
def test_cursor_decode_requires_every_row_field(missing_field: str) -> None:
    codec = Base64TimelineCursorCodec()
    fields = payload(codec.encode(TimelineCursor('row', DAY, 1), PROFILE))
    del fields[missing_field]

    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        codec.decode(wire(json.dumps(fields).encode()), PROFILE)


@pytest.mark.parametrize('token', ['', 'a', 'ab=c', 'abc+', 'abc/', 'å', 'AAAA ', 'A' * 1025,
                                  wire(b'[]'), wire(b'null'), wire(b'\xff'), wire(b'{"v":1,"v":1}')])
def test_cursor_decode_rejects_malformed_or_oversize_input(token: str) -> None:
    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        Base64TimelineCursorCodec().decode(token, PROFILE)


def test_cursor_decode_enforces_1024_character_bound_on_valid_payload() -> None:
    codec = Base64TimelineCursorCodec()
    cursor = TimelineCursor('row', DAY, 1)
    raw = base64.urlsafe_b64decode(codec.encode(cursor, PROFILE) + '===')
    largest = wire(raw.ljust(768))
    assert len(largest) == 1024
    assert codec.decode(largest, PROFILE) == cursor

    oversized = wire(raw.ljust(769))
    assert len(oversized) > 1024
    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        codec.decode(oversized, PROFILE)


def test_cursor_decode_rejects_duplicate_key_with_otherwise_valid_fields() -> None:
    codec = Base64TimelineCursorCodec()
    token = codec.encode(TimelineCursor('row', DAY, 1), PROFILE)
    raw = base64.urlsafe_b64decode(token + '===')

    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        codec.decode(wire(raw[:-1] + b',"v":1}'), PROFILE)


def test_cursor_decode_rejects_foreign_profile() -> None:
    codec = Base64TimelineCursorCodec()
    token = codec.encode(TimelineCursor('row', DAY, 1), PROFILE)

    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        codec.decode(token, UUID(int=2))
