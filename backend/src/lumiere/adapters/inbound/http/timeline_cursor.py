import base64
import hashlib
import json
import re
from datetime import date
from typing import cast
from uuid import UUID

from lumiere.domain.errors import TimelineFailed
from lumiere.domain.timeline import TimelineCursor, valid_movie_id

_VERSION = 1
_MAX_TOKEN_BYTES = 1024
_ALPHABET = re.compile(r'[A-Za-z0-9_-]+')
_BOUNDARY_FIELDS = {'v', 'kind', 'date', 'scope'}
_ROW_FIELDS = _BOUNDARY_FIELDS | {'id'}


def _scope(profile_id: UUID) -> str:
    return hashlib.sha256(f'lumiere:timeline:v{_VERSION}:'.encode('ascii') + profile_id.bytes).hexdigest()


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError('duplicate cursor field')
    return fields


def _decode_fields(token: str) -> dict[str, object]:
    if type(token) is not str or len(token) > _MAX_TOKEN_BYTES or not _ALPHABET.fullmatch(token):
        raise TimelineFailed('invalid_cursor')
    try:
        raw = base64.b64decode(token + '=' * (-len(token) % 4), altchars=b'-_', validate=True)
        fields: object = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError):
        raise TimelineFailed('invalid_cursor') from None
    if not isinstance(fields, dict) or _base64url(raw) != token:
        raise TimelineFailed('invalid_cursor')
    return cast(dict[str, object], fields)


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise TimelineFailed('invalid_cursor')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise TimelineFailed('invalid_cursor') from None
    if parsed.isoformat() != value:
        raise TimelineFailed('invalid_cursor')
    return parsed


class Base64TimelineCursorCodec:
    def encode(self, cursor: TimelineCursor, profile_id: UUID) -> str:
        if type(cursor.release_date) is not date:
            raise TimelineFailed('invalid_cursor')
        fields: dict[str, object] = {
            'v': _VERSION, 'kind': cursor.kind, 'date': cursor.release_date.isoformat(), 'scope': _scope(profile_id),
        }
        if cursor.kind == 'row' and valid_movie_id(cursor.id):
            fields['id'] = cursor.id
        elif cursor.kind != 'future_boundary' or cursor.id is not None:
            raise TimelineFailed('invalid_cursor')
        return _base64url(json.dumps(fields, separators=(',', ':')).encode('utf-8'))

    def decode(self, token: str, profile_id: UUID) -> TimelineCursor:
        fields = _decode_fields(token)
        version = fields.get('v')
        if type(version) is not int or version != _VERSION or fields.get('scope') != _scope(profile_id):
            raise TimelineFailed('invalid_cursor')
        kind = fields.get('kind')
        if kind == 'future_boundary' and fields.keys() == _BOUNDARY_FIELDS:
            return TimelineCursor('future_boundary', _parse_date(fields['date']))
        if kind == 'row' and fields.keys() == _ROW_FIELDS:
            movie_id = fields['id']
            if valid_movie_id(movie_id):
                return TimelineCursor('row', _parse_date(fields['date']), movie_id)
        raise TimelineFailed('invalid_cursor')
