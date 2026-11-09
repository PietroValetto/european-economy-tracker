import datetime
import unittest

import _util

from eet import calendar as cal
from eet.registry import Registry
from eet.spec import Chart, Ref, Series, Tile

D = datetime.date


def fake_registry():
    reg = Registry(modules=["home", "inflation", "ecb"])
    for s in [Series("unemployment_rate", "eurostat", dataset="une_rt_m", module="home"),
              Series("hicp_headline", "eurostat", dataset="prc_hicp_minr", module="inflation"),
              Series("hicp_release", "eurostat", dataset="prc_hicp_fpd", module="inflation"),
              Series("dfr", "ecb", dataset="FM", key="D.U2.EUR.4F.KR.DFR.LEV", module="ecb"),
              Series("mpd_gdp", "ecb", dataset="MPD", key="A.U2.YER.A..0000", split=4, module="ecb")]:
        reg.series[s.id] = s
    for c in [Chart("hicp-headline-core", "inflation", "headline", 10, "t", "s",
                    series=[Ref("hicp_headline", "h", "Headline", "story")], module="inflation"),
              Chart("hicp-flash-final", "inflation", "flash", 20, "t", "s", build=lambda ctx, c: {},
                    module="inflation"),
              Chart("policy-rates", "ecb", "rates", 10, "t", "s", series=[Ref("dfr", "dfr", "DFR", "story")],
                    module="ecb"),
              Chart("staff-projections-growth", "ecb", "proj", 20, "t", "s",
                    series=[Ref("mpd_gdp__S26", "s26", "Sep", "base")], module="ecb")]:
        reg.charts[c.id] = c
    reg.tiles.append(Tile("unemployment", "Unemployment", "unemployment_rate", "%", "unemployment-rate", "labour",
                          module="home"))
    methods = [{"id": "hicp-flash-final", "sources": [{"name": "Eurostat", "dataset": "prc_hicp_fpd", "url": ""}]}]
    return reg, methods


class ICalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = cal.parse_ical(_util.fixture("eurostat_calendar_sample.ics"))

    def test_parses_recorded_sample(self):
        self.assertEqual(len(self.events), 40)
        ppi = [e for e in self.events if e["summary"].startswith("Industrial producer prices")]
        self.assertEqual(ppi[0]["summary"], "Industrial producer prices, domestic market")  # "\," unescaped
        flash = [e for e in self.events if e["summary"] == "Flash estimate inflation euro area"]
        self.assertEqual([e["date"] for e in flash], [D(2026, 11, 4), D(2026, 12, 1), D(2027, 1, 6)])
        self.assertIn(cal.EURO_INDICATORS, flash[0]["categories"])
        self.assertIsNone(flash[0]["time"])

    def test_unfolds_lines_and_reads_times(self):
        text = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:20261201T100000Z\r\nSUMMARY:Flash estimate infl\r\n"
                " ation euro area\r\nX-CATEGORY:Data release\\,Euro indicators release\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        (e,) = cal.parse_ical(text)
        self.assertEqual(e["summary"], "Flash estimate inflation euro area")
        self.assertEqual((e["date"], e["time"]), (D(2026, 12, 1), "11:00"))  # 10:00 UTC = 11:00 Brussels

    def test_filtering_tiers_and_titles(self):
        out = cal.eurostat_events(self.events, D(2026, 11, 9), D(2026, 12, 24), {})
        titles = {e["title"]: e for e in out}
        self.assertNotIn("Asylum applications", " ".join(titles))          # not euro indicator, not mapped
        self.assertNotIn("cows", " ".join(titles).lower())
        self.assertEqual(titles["Inflation (HICP), flash estimate, November"]["tier"], 1)
        self.assertEqual(titles["Unemployment, October"]["tier"], 1)
        self.assertEqual(titles["GDP and employment, flash estimate, Q3 2026"]["tier"], 1)
        self.assertEqual(titles["Inflation (HICP), final, October"]["tier"], 2)
        self.assertEqual(titles["Industrial production, September"]["tier"], 2)
        self.assertEqual(titles["Labour force survey, quarterly results, Q3 2026"]["tier"], 3)
        self.assertEqual(titles["Building permits"]["tier"], 3)
        e = titles["Inflation (HICP), flash estimate, November"]
        self.assertEqual((e["date"], e["time"], e["tz"], e["period"], e["id"]),
                         ("2026-12-01", "11:00", "Europe/Brussels", "2026-11", "2026-12-01-hicp-flash"))
        self.assertTrue(all(D(2026, 11, 9).isoformat() <= x["date"] <= "2026-12-24" for x in out))

    def test_unmapped_euro_indicator_is_tier_2(self):
        ev = [{"date": D(2026, 12, 3), "time": None, "summary": "Brand new indicator",
               "categories": ["Data release", cal.EURO_INDICATORS], "theme": "", "uid": ""}]
        (e,) = cal.eurostat_events(ev, D(2026, 12, 1), D(2026, 12, 31), {})
        self.assertEqual((e["tier"], e["datasets"], e["id"]), (2, [], "2026-12-03-brand-new-indicator"))


class PeriodTests(unittest.TestCase):
    def test_reference_periods(self):
        rp = cal.reference_period
        self.assertEqual(rp("M", -2, D(2026, 11, 4)), ("2026-10", "October"))    # HICP flash
        self.assertEqual(rp("M", -2, D(2027, 1, 6)), ("2026-12", "December 2026"))
        self.assertEqual(rp("M", 25, D(2026, 12, 2)), ("2026-10", "October"))     # unemployment
        self.assertEqual(rp("M", 14, D(2026, 11, 18)), ("2026-10", "October"))    # HICP final
        self.assertEqual(rp("Q", 40, D(2026, 11, 13)), ("2026-Q3", "Q3 2026"))    # GDP flash t+45
        self.assertEqual(rp("Q", 100, D(2027, 1, 22)), ("2026-Q3", "Q3 2026"))    # government debt
        self.assertEqual(rp("A", 90, D(2026, 10, 22)), ("2025", "2025"))
        self.assertEqual(rp(None, 0, D(2026, 1, 1)), (None, None))


class MappingTests(unittest.TestCase):
    def test_dataset_index_scans_registry_methods_and_tiles(self):
        reg, methods = fake_registry()
        idx = cal.dataset_index(reg, methods)
        self.assertEqual(idx["une_rt_m"]["charts"], ["unemployment-rate"])          # from the home tile
        self.assertEqual(idx["prc_hicp_fpd"]["charts"], ["hicp-flash-final"])      # build hook, via methods
        self.assertEqual(idx["prc_hicp_minr"]["modules"], ["inflation"])
        self.assertEqual(idx["MPD"]["charts"], ["staff-projections-growth"])       # panel child resolved
        self.assertEqual(cal.charts_for(["prc_hicp_fpd", "prc_hicp_minr"], idx),
                         ["hicp-flash-final", "hicp-headline-core"])

    def test_ecb_and_ec_events(self):
        reg, methods = fake_registry()
        idx = cal.dataset_index(reg, methods)
        ecb, ec = cal.load_json("ecb_meetings.json"), cal.load_json("ec_events.json")
        evs = cal.build_events(D(2026, 11, 9), D(2026, 12, 24), [], ecb, ec, idx)
        dec = [e for e in evs if e["publisher"] == "ECB"]
        self.assertEqual([(e["date"], e["time"], e["tier"]) for e in dec],
                         [("2026-12-17", "14:15", 1), ("2026-12-17", "14:45", 2)])
        self.assertEqual(dec[0]["chart_ids"], ["policy-rates"])
        self.assertIn("Eurosystem staff", dec[1]["title"])
        esi = [e for e in evs if e["id"] == "2026-11-27-business-consumer-surveys"]
        self.assertEqual((esi[0]["time"], esi[0]["publisher"], esi[0]["period"]), ("11:00", "European Commission", "2026-11"))
        # December surveys come out on 7 January 2027: outside this window
        self.assertFalse([e for e in evs if e["date"] > "2026-12-24"])

    def test_ec_overrides_duplicate_eurostat_entry(self):
        ical = [{"date": D(2026, 11, 27), "time": None,
                 "summary": "Economic Sentiment Indicator & Business and Consumer Survey results",
                 "categories": ["Data release", cal.EURO_INDICATORS], "theme": "", "uid": ""}]
        evs = cal.build_events(D(2026, 11, 27), D(2026, 11, 27), ical, {}, cal.load_json("ec_events.json"), {})
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["publisher"], "European Commission")

    def test_ecb_meetings_are_thursdays(self):
        for m in cal.load_json("ecb_meetings.json")["meetings"]:
            self.assertEqual(D.fromisoformat(m["date"]).weekday(), 3, m["date"])


class ValidateTests(unittest.TestCase):
    def test_validate(self):
        good = {"built_at": "2026-11-09T05:00:00Z", "events": [
            {"id": "a", "date": "2026-12-01", "time": "11:00", "tz": "Europe/Brussels", "title": "x",
             "publisher": "Eurostat", "tier": 1, "datasets": [], "chart_ids": []}]}
        self.assertEqual(cal.validate(good), [])
        bad = {"built_at": "2026-11-09 05:00", "events": [dict(good["events"][0], tier=4, time="11h"),
                                                         dict(good["events"][0])]}
        errs = cal.validate(bad)
        self.assertEqual(len(errs), 4, errs)  # built_at, tier, time, duplicate id


if __name__ == "__main__":
    unittest.main()
