import io
import tempfile
import unittest
import urllib.error

import _util  # noqa: F401

from eet import http, paths


class FakeResp(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cache, paths.CACHE = paths.CACHE, self.tmp.name
        self._open, self._sleep = http._urlopen, http._sleep
        http._sleep = lambda s: None
        http.reset()

    def tearDown(self):
        http._urlopen, http._sleep = self._open, self._sleep
        paths.CACHE = self._cache
        self.tmp.cleanup()
        http.reset()

    def test_retries_504_then_succeeds(self):
        calls = []

        def fake(req, timeout):
            calls.append(req.full_url)
            if len(calls) < 3:
                raise urllib.error.HTTPError(req.full_url, 504, "Gateway", {}, io.BytesIO(b"<html>"))
            return FakeResp(b"KEY,TIME_PERIOD,OBS_VALUE\n", headers={"Last-Modified": "Sat, 07 Nov 2026 12:42:00 GMT"})
        http._urlopen = fake
        r = http.get("https://example.test/a", source="ecb", cache_id="a", ext="csv")
        self.assertEqual(len(calls), 3)
        self.assertEqual(r.attempts, 3)
        self.assertEqual(r.updated, "2026-11-07T12:42:00+0000")
        cached = http.read_cache("ecb", "a", "csv")
        self.assertEqual(cached.body, r.body)
        self.assertEqual(cached.updated, r.updated)

    def test_404_not_retried(self):
        calls = []

        def fake(req, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b'{"title":"Not Found"}'))
        http._urlopen = fake
        with self.assertRaises(http.FetchError) as cm:
            http.get("https://example.test/b")
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(len(calls), 1)

    def test_timeouts_exhaust_retries(self):
        def fake(req, timeout):
            raise TimeoutError("timed out")
        http._urlopen = fake
        with self.assertRaises(http.FetchError):
            http.get("https://example.test/c", tries=2)

    def test_memo_and_jsonstat_stamp(self):
        calls = []

        def fake(req, timeout):
            calls.append(1)
            return FakeResp(b'{"updated":"2026-11-04T11:00:00+0100","id":[]}')
        http._urlopen = fake
        a = http.get("https://example.test/d")
        b = http.get("https://example.test/d")
        self.assertIs(a, b)
        self.assertEqual(len(calls), 1)
        self.assertEqual(a.updated, "2026-11-04T11:00:00+0100")

    def test_plain_user_agent(self):
        seen = {}

        def fake(req, timeout):
            seen["ua"] = req.get_header("User-agent")
            seen["timeout"] = timeout
            return FakeResp(b"x")
        http._urlopen = fake
        http.get("https://example.test/e")
        self.assertEqual(seen["ua"], "Mozilla/5.0")
        self.assertEqual(seen["timeout"], 60)


if __name__ == "__main__":
    unittest.main()
