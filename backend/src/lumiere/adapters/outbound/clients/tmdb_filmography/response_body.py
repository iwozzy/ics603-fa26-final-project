import zlib

import httpx

from lumiere.domain.errors import HydrationFailed

_GZIP_WINDOW_BITS = 16 + zlib.MAX_WBITS


def _check_size(size: int, max_bytes: int) -> None:
    if size > max_bytes:
        raise HydrationFailed("provider_oversize")


async def _read_gzip(response: httpx.Response, max_bytes: int) -> bytearray:
    body = bytearray()
    decoder = zlib.decompressobj(_GZIP_WINDOW_BITS)
    try:
        async for raw in response.aiter_raw(chunk_size=64 * 1024):
            while raw:
                if decoder.eof:
                    decoder = zlib.decompressobj(_GZIP_WINDOW_BITS)
                # The extra byte detects overflow while keeping inflater output bounded.
                max_output = max(1, max_bytes - len(body) + 1)
                chunk = decoder.decompress(raw, max_output)
                _check_size(len(body) + len(chunk), max_bytes)
                body.extend(chunk)
                raw = decoder.unused_data
    except zlib.error:
        raise HydrationFailed("provider_response") from None
    if not decoder.eof:
        raise HydrationFailed("provider_response")
    return body


async def read_body(response: httpx.Response, max_bytes: int) -> bytes | bytearray:
    encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
    if encoding not in ("gzip", "identity"):
        raise HydrationFailed("provider_response")
    if response.is_stream_consumed:
        # Some transports supply a response HTTPX has already read and decoded.
        _check_size(len(response.content), max_bytes)
        return response.content
    if encoding == "gzip":
        return await _read_gzip(response, max_bytes)

    body = bytearray()
    async for chunk in response.aiter_raw():
        _check_size(len(body) + len(chunk), max_bytes)
        body.extend(chunk)
    return body
