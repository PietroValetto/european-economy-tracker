import datetime
import json
import os
import tempfile
import unittest

import _util

from eet import calendar as cal
from eet import http, release
from test_calendar import fake_registry

UTC = datetime.timezone.utc


def resp(body=b"", headers=None, url=""):
    return http.Response(url=url, status=200, body=body, headers=headers or {})


class StampTests(unittest.TestCase):
    def test_parse_stamp_shapes(self):
        want = datetime.datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
        for v in ["2026-11-04T11:00:00+0100", "2026-11-04T10:00:00+00:00", "2026-11-04T10:00:00Z",
                  "Wed, 04 Nov 2026 10:00:00 GMT"]:
            self.assertEqual(release.parse_stamp(v), want, v)
        self.assertEqual(release.parse_stamp("2026-11-04 11:00:00.0", tz=release.LUX), want)
        self.assertIsNone(release.parse_stamp(""))
        self.assertIsNone(release.parse_stamp("not a date"))

    def test_stored_stamp_takes_newest_panel_child(self):
        meta = {"hicp_country__DE": {"updated": "2026-11-04T11:00:00+0100"},
                "hicp_country__FR": {"updated": "2026-10-30T11:00:00+0100"},
                "hicp_countryx": {"updated": "2027-01-01T00:00:00+0000"}}
        self.assertEqual(release.stored_stamp(meta, "hicp_country"), datetime.datetime(2026, 11, 4, 10, tzinfo=UTC))
        self.assertIsNone(release.stored_stamp(meta, "missing"))

    def test_parse_recorded_rss(self):
        rss = release.parse_rss(_util.fixture("eurostat_statistics_update.rss"))
        self.assertEqual(rss["sts_sepr_m"], datetime.datetime(2026, 11, 9, 10, tzinfo=UTC))  # newest of several
        self.assertEqual(rss["prc_hicp_minr"], datetime.datetime(2026, 11, 4, 10, tzinfo=UTC))
        self.assertTrue(all(k == k.lower() for k in rss))


class FakeGet:
    """Stands in for http.get: RSS body, JSON-stat stamps, ECB answers by key."""

    def __init__(self, rss=b"", ecb=None, jsonstat=None):
        self.rss, self.ecb, self.jsonstat, self.urls = rss, ecb or {}, jsonstat or {}, []

    def __call__(self, url):
        self.urls.append(url)
        if url == release.RSS_URL:
            return resp(self.rss)
        if "data-api.ecb.europa.eu" in url:
            for key, ans in self.ecb.items():
                if key in url:
                    if ans is None:
                        raise http.FetchError("HTTP 404", status=404, url=url)
                    return resp(b"KEY,TIME_PERIOD,OBS_VALUE\n", {"Last-Modified": ans})
            raise http.FetchError("HTTP 404", status=404, url=url)
        for ds, stamp in self.jsonstat.items():
            if f"/{ds}?" in url:
                return resp(json.dumps({"updated": stamp}).encode())
        raise http.FetchError("HTTP 500", status=500, url=url)


RSS = (b"<rss><channel><item><title>PRC_HICP_MINR - \"Dataset: updated data\"</title><category>UPDATED_DATASET_DATA"
       b"</category><pubDate>2026-12-01 11:00:00.0</pubDate></item><item><title>UNE_RT_M - \"x\"</title><category>"
       b"UPDATED_DATASET_DATA</category><pubDate>2026-11-05 23:00:00.0</pubDate></item></channel></rss>")
META = {"hicp_headline": {"updated": "2026-11-18T11:00:00+0100"},
        "unemployment_rate": {"updated": "2026-11-05T23:00:00+0100"},
        "hicp_release": {"updated": "2026-11-18T11:00:00+0100"},
        "dfr": {"updated": "2026-10-29T13:15:00+0000"},
        "mpd_gdp__S26": {"updated": "2026-09-10T13:48:39+0000"}}


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.reg, methods = fake_registry()
        self.index = cal.dataset_index(self.reg, methods)
        self.events = cal.build_events(datetime.date(2026, 12, 1), datetime.date(2026, 12, 2), [
            {"date": datetime.date(2026, 12, 1), "time": None, "summary": "Flash estimate inflation euro area",
             "categories": ["Data release", cal.EURO_INDICATORS], "theme": "", "uid": ""},
            {"date": datetime.date(2026, 12, 2), "time": None, "summary": "Unemployment",
             "categories": ["Data release", cal.EURO_INDICATORS], "theme": "", "uid": ""}], {}, {}, self.index)

    def test_eurostat_rss_change_and_jsonstat_fallback(self):
        get = FakeGet(rss=RSS, jsonstat={"prc_hicp_fpd": "2026-12-01T11:00:00+0100"})
        st = release.detect(datetime.date(2026, 12, 1), self.events, self.reg, META, self.index,
                            release.Poller(get, log=lambda *a: None))
        flash, unemp = st["releases"]
        by = {r["series"]: r for r in flash["series"]}
        self.assertEqual(by["hicp_headline"]["status"], "changed")
        self.assertEqual(by["hicp_headline"]["how"], "rss")
        self.assertEqual(by["hicp_release"]["how"], "json-stat")      # not in the RSS
        self.assertEqual(by["hicp_release"]["status"], "changed")
        self.assertEqual(unemp["series"][0]["status"], "unchanged")   # same stamp as stored
        self.assertTrue(st["changed"])
        self.assertEqual(st["modules"], ["inflation"])
        self.assertEqual(flash["charts"], ["hicp-headline-core", "hicp-flash-final"])  # direct users first
        self.assertEqual(get.urls.count(release.RSS_URL), 1)

    def test_ecb_updated_after(self):
        day = datetime.date(2026, 12, 17)
        evs = cal.build_events(day, day, [], cal.load_json("ecb_meetings.json"), {}, self.index)
        quiet = release.detect(day, evs, self.reg, META, self.index,
                               release.Poller(FakeGet(ecb={"DFR": None, "YER": None}), log=lambda *a: None))
        self.assertFalse(quiet["changed"])
        get = FakeGet(ecb={"DFR": "Thu, 17 Dec 2026 13:15:02 GMT", "YER": None})
        moved = release.detect(day, evs, self.reg, META, self.index, release.Poller(get, log=lambda *a: None))
        self.assertTrue(moved["changed"])
        self.assertEqual(moved["modules"], ["ecb"])
        url = [u for u in get.urls if "DFR" in u][0]
        self.assertIn("updatedAfter=2026-10-29T13%3A15%3A01Z", url)  # stored stamp + 1 s (inclusive)

    def test_errors_never_count_as_changes(self):
        st = release.detect(datetime.date(2026, 12, 1), self.events, self.reg, META, self.index,
                            release.Poller(FakeGet(rss=b""), log=lambda *a: None))  # JSON-stat answers 500
        self.assertFalse(st["changed"])
        self.assertTrue(all(r["status"] == "error" for rel in st["releases"] for r in rel["series"]))


class AlertTests(unittest.TestCase):
    BUNDLE = {"id": "hicp-headline-core", "page": "inflation", "title": "Inflation", "subtitle": "Euro area HICP, % y/y",
              "units": "%", "format": "pct", "decimals": 1,
              "series": [{"key": "headline", "label": "Headline"}, {"key": "core", "label": "Core"}],
              "latest": {"period": "2026-11", "values": {"headline": 4.1, "core": 2.6}},
              "previous": {"period": "2026-10", "values": {"headline": 4.0, "core": 2.6}},
              "source": "Eurostat, HICP (prc_hicp_minr)", "data_updated": "2026-12-01T11:00:00+0100"}

    def test_render_numbers_only_note(self):
        rel = {"event": {"id": "2026-12-01-hicp-flash", "title": "Inflation (HICP), flash estimate, November",
                         "date": "2026-12-01", "time": "11:00", "publisher": "Eurostat", "tier": 1, "period": "2026-11"},
               "changed": ["hicp_headline"], "charts": ["hicp-headline-core", "missing-chart"]}
        md = release.render_alert(rel, {"hicp-headline-core": self.BUNDLE})
        self.assertIn("| Headline | 2026-11 | 4.1 | 4.0 | +0.1 pp |", md)
        self.assertIn("| Core | 2026-11 | 2.6 | 2.6 | 0.0 pp |", md)
        self.assertIn("Chart: https://pietrovaletto.github.io/european-economy-tracker/inflation/#hicp-headline-core", md)
        self.assertIn("Source: Eurostat, HICP (prc_hicp_minr)", md)

    def test_write_alerts_only_for_changed_tier_1_and_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            charts = os.path.join(tmp, "charts")
            os.makedirs(charts)
            with open(os.path.join(charts, "hicp-headline-core.json"), "w") as fh:
                json.dump(self.BUNDLE, fh)
            ev = {"id": "2026-12-01-hicp-flash", "title": "x", "date": "2026-12-01", "tier": 1}
            state = {"checked_at": "2026-12-01T10:05:00Z", "releases": [
                {"event": ev, "changed": ["hicp_headline"], "charts": ["hicp-headline-core"]},
                {"event": dict(ev, id="2026-12-01-building-permits", tier=3), "changed": ["x"], "charts": []},
                {"event": dict(ev, id="2026-12-01-retail-trade", tier=2), "changed": [], "charts": []}]}
            out = os.path.join(tmp, "outbox")
            written = release.write_alerts(state, charts_dir=charts, outbox=out, log=lambda *a: None)
            self.assertEqual([os.path.basename(p) for p in written], ["2026-12-01-hicp-flash.md"])


if __name__ == "__main__":
    unittest.main()
