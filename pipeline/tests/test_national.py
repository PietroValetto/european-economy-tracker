"""National source families (Bundesbank, INSEE, CBS, ISTAT, GUS, Indeed wage tracker): parsers on
recorded responses (9 Nov 2026) and the fetch logic with a fake network."""
import datetime
import io
import tempfile
import unittest
import urllib.error
import urllib.parse

from _util import fixture

from eet import http, paths, sources, store
from eet.parsers import national
from eet.spec import Series

GUS_375 = sources.GUS_DBW + "1.1.0/variable/variable-data-section?id-zmienna=375&id-przekroj=12"


class ParserTests(unittest.TestCase):
    def test_bundesbank_csv(self):
        obs, updated = national.bundesbank(fixture("bundesbank_kurzarbeit.csv"))
        self.assertEqual(obs[0], ("2026-01", 141875.0, ""))
        self.assertEqual(obs[-1], ("2026-08", 136304.0, "p"))  # "Provisional value"
        self.assertEqual(len(obs), 8)
        self.assertTrue(updated.startswith("2026-10-30T10:11:21+0"))

    def test_bundesbank_rejects_other_csv(self):
        with self.assertRaises(national.NationalParseError):
            national.bundesbank(b"")

    def test_insee_sdmx_ml(self):
        obs, updated = national.insee(fixture("insee_payroll.xml"))
        self.assertEqual(obs[0], ("2025-Q1", 21032.1, ""))
        self.assertEqual(obs[-1], ("2026-Q3", 20931.1, ""))
        self.assertEqual([o[0] for o in obs], sorted(o[0] for o in obs))
        self.assertTrue(updated.startswith("2026-10-30"))

    def test_cbs_monthly_only(self):
        obs = national.cbs(fixture("cbs_80590ned.json"), "Seizoengecorrigeerd_4")
        self.assertEqual(obs[0], ("2026-01", 9843.0, ""))
        self.assertEqual(obs[-1], ("2026-09", 9831.0, ""))
        self.assertEqual(len(obs), 9)  # quarterly KW rows skipped
        rate = national.cbs(fixture("cbs_80590ned.json"), "Seizoengecorrigeerd_8")
        self.assertEqual(rate[-1][1], 4.0)
        with self.assertRaises(national.NationalParseError):
            national.cbs(fixture("cbs_80590ned.json"), "NoSuchTopic")

    def test_cbs_modified(self):
        self.assertTrue(national.cbs_modified(fixture("cbs_tableinfos.json")).startswith("2026-10-15T06:30:00+0"))

    def test_gus_value(self):
        body = fixture("gus_375_2026_09.json")
        self.assertEqual(national.gus_value(body, 6661598, 5), 99.2)       # y/y index
        self.assertEqual(national.gus_value(body, 6661598, 273), 6360.0)   # level, thousands
        self.assertIsNone(national.gus_value(body, 1, 5))
        self.assertEqual(national.gus_period_id(9), 255)

    def test_istat_edition_is_calendar_order(self):
        self.assertEqual(national.istat_latest_edition(fixture("istat_editions.csv")), "2026M10G29")
        self.assertEqual(national.istat_edition_date("2026M10G29"), "2026-10-29T10:00:00+0100")
        self.assertGreater(national.istat_edition_key("2026M10G1"), national.istat_edition_key("2026M9G1"))

    def test_indeed_wages(self):
        g = national.indeed_wages(fixture("indeed_wages.csv"))
        self.assertEqual(set(g), {"EA", "DE"})
        self.assertEqual(g["EA"][0], ("2019-03", 0.025420612, ""))  # NA rows dropped
        self.assertEqual(g["EA"][-1][0], "2026-09")
        self.assertEqual(national.month_label("Dec-25"), "2025-12")


class FakeResp(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FamilyFetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cache, paths.CACHE = paths.CACHE, self.tmp.name + "/cache"
        self._store, paths.STORE = paths.STORE, self.tmp.name + "/store"
        self._open, self._sleep = http._urlopen, http._sleep
        self._today = sources._today
        http._sleep = lambda s: None
        sources._today = lambda: datetime.date(2026, 11, 9)
        sources._last_istat[0] = 0.0
        http.reset()
        self.urls = []

    def tearDown(self):
        http._urlopen, http._sleep = self._open, self._sleep
        paths.CACHE, paths.STORE = self._cache, self._store
        sources._today = self._today
        self.tmp.cleanup()
        http.reset()

    def route(self, table):
        """Fake urlopen: the first table entry whose fragment is in the URL answers (int = HTTP error)."""
        def fake(req, timeout=None):
            url = req.full_url
            self.urls.append(url)
            for frag, body in table:
                if frag in url:
                    if isinstance(body, int):
                        raise urllib.error.HTTPError(url, body, "err", {}, io.BytesIO(b"{}"))
                    return FakeResp(body)
            raise AssertionError(f"unexpected URL {url}")
        http._urlopen = fake

    def test_family_detection_keeps_core_csv(self):
        plain = Series("x", "csv", dataset="https://example.org/data.csv")
        self.assertIsNone(sources.family(plain))
        self.assertEqual(sources.url_for(plain), "https://example.org/data.csv")
        bb = Series("b", "csv", dataset=sources.BUNDESBANK + "BBDL1/M.DE.Y.VAC.VBA000.A0000.A00.D00.0.ABA.A",
                    start="2005-01")
        self.assertEqual(sources.family(bb), "bundesbank")
        self.assertIn("startPeriod=2005-01", sources.url_for(bb))
        self.assertIn("format=csv", sources.url_for(bb))

    def test_bundesbank_fetch_and_offline(self):
        s = Series("de_kug", "csv", dataset=sources.BUNDESBANK + "BBDL1/M.DE.Y.LMP.LKA100.A0000.A02.D00.0.ABA.A",
                   start="2026-01")
        self.route([("BBDL1", fixture("bundesbank_kurzarbeit.csv"))])
        res = sources.fetch(s)
        self.assertEqual(res.obs["de_kug"][-1], ("2026-08", 136304.0, "p"))
        self.assertTrue(res.updated.startswith("2026-10-30"))
        http.reset()
        off = sources.fetch(s, offline=True)
        self.assertEqual(off.obs, res.obs)

    def test_cbs_url_and_stamp(self):
        s = Series("nl_emp", "csv", dataset=sources.CBS + "80590ned",
                   filters={"Geslacht": "T001038", "Leeftijd": "52052   "}, value_col="Seizoengecorrigeerd_4",
                   start="2026-01")
        url = sources.url_for(s)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertIn("Leeftijd eq '52052   '", q["$filter"][0])
        self.assertIn("substring(Perioden,0,4) ge '2026'", q["$filter"][0])
        self.route([("TableInfos", fixture("cbs_tableinfos.json")), ("TypedDataSet", fixture("cbs_80590ned.json"))])
        res = sources.fetch(s)
        self.assertEqual(res.obs["nl_emp"][-1], ("2026-09", 9831.0, ""))
        self.assertTrue(res.updated.startswith("2026-10-15"))

    def test_istat_discovers_newest_edition(self):
        s = Series("it_emp", "csv",
                   dataset=sources.ISTAT + "IT1,150_875,1.0/M.IT.EMP.Y.9.Y15-89.9.9.{EDITION}", start="2004-01")
        self.route([("lastNObservations", fixture("istat_editions.csv")),
                    ("9.9.2026M10G29?", fixture("istat_employment.csv"))])
        res = sources.fetch(s)
        self.assertEqual(len(self.urls), 2)
        self.assertIn("M.IT.EMP.Y.9.Y15-89.9.9.?", self.urls[0])  # edition wildcard first
        self.assertIn("2026M10G29", self.urls[1])
        self.assertEqual(res.obs["it_emp"][-1], ("2026-09", 24327.563, ""))
        self.assertEqual(res.updated, "2026-10-29T10:00:00+0100")
        http.reset()
        self.assertEqual(sources.fetch(s, offline=True).updated, "2026-10-29T10:00:00+0100")

    def test_istat_needs_placeholder(self):
        s = Series("it_x", "csv", dataset=sources.ISTAT + "IT1,150_875,1.0/M.IT.EMP")
        with self.assertRaises(ValueError):
            sources.fetch(s)

    def test_gus_month_by_month_then_incremental(self):
        body = fixture("gus_375_2026_09.json")
        s = Series("pl_emp", "csv", dataset=GUS_375, filters={"position": 6661598, "measure": 5}, start="2026-07")
        # Jul to Sep answer with the September body, October (id-okres 256) is not published yet
        self.route([("id-okres=256", 404), ("id-okres=25", body)])
        res = sources.fetch(s)
        self.assertEqual([p for p, _, _ in res.obs["pl_emp"]], ["2026-07", "2026-08", "2026-09"])
        self.assertEqual(res.obs["pl_emp"][-1][1], 99.2)
        self.assertEqual(len(self.urls), 4)  # Oct (404), Sep, Aug, Jul
        # once stored, the last GUS_REFRESH months come first, then the backfill within the budget
        s2 = Series(**{**s.__dict__, "start": "2015-01"})
        store.update("pl_emp", res.obs["pl_emp"], today="2026-11-09")
        store.save_meta({"pl_emp": {"spec": store.spec_hash(s2)}})
        months = sources._gus_months(s2)
        self.assertEqual(months[:6], ["2026-10", "2026-09", "2026-08", "2026-07", "2026-06", "2026-05"])
        self.assertEqual(months[6], "2026-04")
        self.assertEqual(len(months), sources.GUS_BUDGET)
        http.reset()
        off = sources.fetch(s, offline=True)
        self.assertEqual(off.obs, res.obs)

    def test_gus_quota_keeps_partial_result(self):
        s = Series("pl_wage", "csv", dataset=GUS_375, filters={"position": 6661598, "measure": 5}, start="2026-07")
        self.route([("id-okres=256", 404), ("id-okres=255", fixture("gus_375_2026_09.json")), ("id-okres=25", 429)])
        res = sources.fetch(s)
        self.assertEqual([p for p, _, _ in res.obs["pl_wage"]], ["2026-09"])
        http.reset()
        self.route([("id-okres", 429)])
        with self.assertRaises(http.FetchError):
            sources.fetch(Series(**{**s.__dict__, "id": "pl_other"}))

    def test_indeed_wages_panel(self):
        s = Series("iwt", "csv",
                   dataset=sources.INDEED_WAGES + "main/posted-wage-growth-by-country.csv", split="jobcountry",
                   keep=lambda c: c in {"EA"}, scale=100, value_col="posted_wage_growth_yoy_3moavg")
        self.route([("indeed-wage-tracker", fixture("indeed_wages.csv"))])
        res = sources.fetch(s)
        self.assertEqual(set(res.obs), {"iwt__EA"})
        self.assertAlmostEqual(res.obs["iwt__EA"][-1][1], 2.9608429)

    def test_insee_fetch(self):
        s = Series("fr_payroll", "csv", dataset=sources.INSEE_BDM + "SERIES_BDM/001796854", start="2025-Q1")
        self.assertTrue(sources.url_for(s).endswith("001796854?startPeriod=2025-Q1"))
        self.route([("001796854", fixture("insee_payroll.xml"))])
        res = sources.fetch(s)
        self.assertEqual(res.obs["fr_payroll"][-1], ("2026-Q3", 20931.1, ""))

    def test_empty_family_result_raises(self):
        s = Series("de_none", "csv", dataset=sources.BUNDESBANK + "BBDL1/M.DE.Y.X")
        header = b'\xef\xbb\xbf"",BBDL1.M.DE.Y.X,BBDL1.M.DE.Y.X_FLAGS\nunit,Anzahl,\n'
        self.route([("BBDL1", header)])
        with self.assertRaises(sources.EmptySeries):
            sources.fetch(s)


if __name__ == "__main__":
    unittest.main()
