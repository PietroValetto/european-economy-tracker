import unittest

import _util  # noqa: F401

from eet import registry, sources
from eet.registry import Registry, RegistryError, validate
from eet.spec import Chart, Ref, Section, Series


class RegistryTests(unittest.TestCase):
    def test_real_registry_loads(self):
        reg = registry.load()
        for m in ("home", "inflation", "financial", "ecb"):
            self.assertIn(m, reg.modules)
        self.assertEqual(len(reg.tiles), 12)
        ids = {t.chart_id for t in reg.tiles}
        self.assertTrue({"gdp-growth", "unemployment-rate", "job-vacancy-rate", "indeed-postings", "gov-debt",
                         "wage-growth"} <= ids)
        for c in reg.charts.values():
            self.assertLessEqual(sum(1 for r in c.series if r.role == "story"), 1, c.id)

    def test_urls_follow_quirks(self):
        reg = registry.load()
        for s in reg.series.values():
            url = sources.url_for(s)
            self.assertNotIn("lastTimePeriod", url, s.id)
            if s.source == "eurostat":  # Eurostat's euro area is EA21; OECD's is still EA20
                self.assertNotIn("EA20", url, s.id)
            if s.source == "ecb":
                self.assertEqual(url.count("/"), 6, s.id)  # one key per request
        self.assertIn("prc_hicp_minr", sources.url_for(reg.series["hicp_headline"]))
        self.assertIn("geo=EA21", sources.url_for(reg.series["hicp_headline"]))

    def _reg(self):
        reg = Registry()
        reg.series["a"] = Series("a", "eurostat", dataset="d")
        reg.sections[("inflation", "s")] = Section("inflation", "s", "S")
        return reg

    def test_two_stories_rejected(self):
        reg = self._reg()
        reg.charts["c"] = Chart("c", "inflation", "s", 1, "t", "s",
                                series=[Ref("a", "x", role="story"), Ref("a", "y", role="story")])
        with self.assertRaises(RegistryError):
            validate(reg)

    def test_unknown_series_page_transform(self):
        reg = self._reg()
        reg.charts["c"] = Chart("c", "nope", "s", 1, "t", "s", series=[Ref("zzz", transform="bogus")])
        with self.assertRaises(RegistryError) as cm:
            validate(reg)
        msg = str(cm.exception)
        self.assertIn("unknown page", msg)
        self.assertIn("unknown series", msg)
        self.assertIn("unknown transform", msg)


if __name__ == "__main__":
    unittest.main()
