import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

_DAY = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
_DAY_NAME = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_TIME = r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
_HTTP_DATE = re.compile(
    rf"(?:{_DAY}, [0-9]{{2}} {_MONTH} [0-9]{{4}} {_TIME} GMT"
    rf"|{_DAY_NAME}, [0-9]{{2}}-{_MONTH}-(?P<old_year>[0-9]{{2}}) {_TIME} GMT"
    rf"|{_DAY} {_MONTH} (?:[0-9]{{2}}| [0-9]) {_TIME} [0-9]{{4}})"
)


def _parse_http_date(raw: str, received_at: datetime) -> datetime | None:
    match = _HTTP_DATE.fullmatch(raw)
    if match is None:
        return None

    old_year = match.group("old_year")
    if old_year is None:
        return parsedate_to_datetime(raw).replace(tzinfo=UTC)

    # RFC 9110 resolves two-digit years against the receipt time.
    limit_year = min(received_at.year + 50, 9999)
    year = limit_year - (limit_year - int(old_year)) % 100
    start, end = match.span("old_year")
    retry_at = parsedate_to_datetime(raw[:start] + f"{year:04d}" + raw[end:])
    if (
        year == received_at.year + 50
        and retry_at.timetuple()[1:6] > received_at.timetuple()[1:6]
    ):
        return retry_at.replace(year=year - 100)
    return retry_at


def parse_retry_after(value: str | None, received_at: datetime) -> float | None:
    if value is None:
        return None

    raw = value.strip(" \t")
    if raw.isascii() and raw.isdecimal():
        return float(raw)

    received_at = received_at.astimezone(UTC)
    try:
        retry_at = _parse_http_date(raw, received_at)
    except ValueError:
        return None
    if retry_at is None:
        return None

    seconds = (retry_at - received_at).total_seconds()
    return seconds if seconds >= 0 else None
