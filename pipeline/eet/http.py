"""HTTP GET for every publisher: urllib, plain User-Agent, retries, raw cache, update stamps.

Quirks applied (research/03_api_verification.md):

* ECB returns HTTP 504 after about 30 s at random, also for valid keys: retry with exponential
  backoff on 5xx and on timeouts, with a 60 s socket timeout.
* Eurostat SDMX endpoints send gzip bodies without a Content-Encoding header: sniff the magic bytes.
* The IMF CDN rejects descriptive custom User-Agents: send a plain one.
* "No data" is a fast 404 at the ECB and an empty 200 at Eurostat; 4xx is never retried.

Every response body is written to ``pipeline/.cache/<source>/<cache_id>.<ext>`` with a
``.meta.json`` sidecar (url, status, fetched_at, publisher update stamp). Identical URLs are
fetched once per process (memo), which lets several series share one request.
"""
import datetime
import email.utils
import gzip
import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import paths

USER_AGENT = "Mozilla/5.0"
TIMEOUT = 60
TRIES = 4
BACKOFF = 2.0  # seconds; doubled after each failed attempt
RETRY_STATUS = {500, 502, 503, 504}


class FetchError(RuntimeError):
    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


@dataclass
class Response:
    url: str
    status: int
    body: bytes
    headers: dict = field(default_factory=dict)
    updated: str | None = None
    secs: float = 0.0
    attempts: int = 1
    from_cache: bool = False


_memo = {}
_sleep = time.sleep
_urlopen = urllib.request.urlopen


def reset():
    """Forget the per-process memo (tests, or a second build in one process)."""
    _memo.clear()


def ungzip(body):
    """Decompress if the body starts with the gzip magic bytes, whatever the headers say."""
    if body[:2] == b"\x1f\x8b":
        return gzip.decompress(body)
    return body


def http_date_to_iso(value):
    """'Sat, 07 Nov 2026 12:42:00 GMT' -> '2026-11-07T12:42:00+0000'. None if unparsable."""
    if not value:
        return None
    try:
        d = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S%z")


def extract_updated(body, headers):
    """Publisher update stamp: JSON-stat ``updated`` if present, else the Last-Modified header."""
    head = body[:1].strip() if body else b""
    if head == b"{":
        try:
            d = json.loads(body)
            if isinstance(d, dict) and d.get("updated"):
                return str(d["updated"])
        except ValueError:
            pass
    lower = {k.lower(): v for k, v in (headers or {}).items()}
    return http_date_to_iso(lower.get("last-modified"))


def _cache_paths(source, cache_id, ext):
    d = os.path.join(paths.CACHE, source)
    return os.path.join(d, f"{cache_id}.{ext}"), os.path.join(d, f"{cache_id}.meta.json")


def write_cache(resp, source, cache_id, ext):
    body_path, meta_path = _cache_paths(source, cache_id, ext)
    os.makedirs(os.path.dirname(body_path), exist_ok=True)
    with open(body_path, "wb") as fh:
        fh.write(resp.body)
    meta = {"url": resp.url, "status": resp.status, "updated": resp.updated, "secs": resp.secs,
            "attempts": resp.attempts,
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)


def read_cache(source, cache_id, ext):
    """Return the cached Response or None."""
    body_path, meta_path = _cache_paths(source, cache_id, ext)
    if not os.path.exists(body_path):
        return None
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
    with open(body_path, "rb") as fh:
        body = fh.read()
    return Response(url=meta.get("url", ""), status=meta.get("status", 200), body=body,
                    updated=meta.get("updated"), from_cache=True)


def get(url, source="misc", cache_id=None, ext="txt", timeout=TIMEOUT, tries=TRIES, backoff=BACKOFF,
        cache=True):
    """GET ``url`` and return a Response with status 200, or raise FetchError.

    Retries 5xx and network timeouts ``tries`` times with exponential backoff. Does not retry 4xx.
    """
    if url in _memo:
        return _memo[url]
    last_err = None
    t0 = time.time()
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
        try:
            with _urlopen(req, timeout=timeout) as r:
                status, body, headers = r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            status, body, headers = e.code, (e.read() or b""), dict(e.headers or {})
            e.close()
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
            last_err = FetchError(f"network error: {e!r}", url=url)
            if attempt < tries:
                _sleep(backoff * 2 ** (attempt - 1))
            continue
        body = ungzip(body)
        if status in RETRY_STATUS:
            last_err = FetchError(f"HTTP {status}", status=status, url=url)
            if attempt < tries:
                _sleep(backoff * 2 ** (attempt - 1))
            continue
        if status != 200:
            snippet = body[:160].decode("utf-8", "replace").replace("\n", " ")
            raise FetchError(f"HTTP {status}: {snippet}", status=status, url=url)
        resp = Response(url=url, status=status, body=body, headers=headers,
                        updated=extract_updated(body, headers), secs=round(time.time() - t0, 2),
                        attempts=attempt)
        if cache and cache_id:
            write_cache(resp, source, cache_id, ext)
        _memo[url] = resp
        return resp
    raise last_err or FetchError("no attempt made", url=url)
