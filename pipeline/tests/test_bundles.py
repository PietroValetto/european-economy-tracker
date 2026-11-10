import copy
import json
import os
import tempfile
import unittest

import _util  # noqa: F401

from eet import builders, bundles, check, paths, sources
from eet.context import BuildContext, Missing
from eet.registry import Registry, validate
from eet.spec import Chart, Derived, Ref, Section, Series, Tile
from eet import transforms


def monthly(values, start="2024-01", flag_last=""):
    from eet import periods as P
    out, p = [], start
    for i, v in enumerate(values):
        out.append((p, v, flag_last if i == len(values) - 1 else ""))
        p = P.shift(p, 1)
    return out


DATA = {
    "h": monthly([2.0 + i / 10 for i in range(30)], flag_last="e"),
    "c": monthly([2.5] * 29),
    "idx": monthly([100 + i for i in range(30)]),
    "dfr": [("2024-06-12", 3.75, ""), ("2026-09-16", 2.5, "")],
    "p__DE": monthly([1.0, 2.0, 3.0]),
    "p__FR": monthly([3.0, 2.0, 1.0]),
    "empty": [],
}


def make_registry():
    reg = Registry()
    for sid in ("h", "c", "idx", "empty"):
        reg.series[sid] = Series(sid, "eurostat", dataset="prc_hicp_minr", label=sid.upper(), module="t")
    reg.series["dfr"] = Series("dfr", "ecb", dataset="FM", key="B.U2.EUR.4F.KR.DFR.LEV", freq="D", decimals=2,
                               event=True, module="t")
    reg.series["p"] = Series("p", "eurostat", dataset="x", split="geo", module="t")
    reg.derived["gap"] = Derived("gap", ["h", "c"], transforms.spread, label="Gap", module="t")
    reg.sections[("inflation", "s")] = Section("inflation", "s", "S", "", 1, module="t")
    reg.charts["line-chart"] = Chart("line-chart", "inflation", "s", 1, "Title", "Sub",
                                     series=[Ref("h", "h", role="base"), Ref("c", "c", role="story"),
                                             Ref("gap", "gap", role="context"), Ref("empty", "gone")],
                                     reference_lines=[{"axis": "y", "value": 2, "label": "Target"}], module="t")
    reg.charts["step-chart"] = Chart("step-chart", "inflation", "s", 2, "Rates", "Sub", decimals=2,
                                     series=[Ref("dfr", "dfr", role="story", transform="step")], module="t")
    reg.charts["bank"] = Chart("bank", "inflation", "s", 3, "Bank", "Sub", type="table", module="t",
                               build=builders.transform_table(
                                   [("m3", "3m", "pct"), ("m12", "12m", "pct")],
                                   [("Headline", {"m3": ("idx", "ann3m"), "m12": ("h", None)}),
                                    ("Core", {"m12": ("c", None)}),
                                    ("Nothing", {"m12": ("empty", None)})], period_from="m12"))
    reg.charts["heat"] = Chart("heat", "inflation", "s", 4, "Heat", "Sub", type="heatmap", module="t",
                               build=builders.heatmap(["p__*"], last_n=2, midpoint=2))
    reg.tiles.append(Tile("t1", "Inflation", "h", "%", "line-chart", "inflation", "none", module="t"))
    validate(reg)
    return reg


def make_ctx(reg):
    return BuildContext(reg, lambda s: DATA.get(s, []),
                        lambda parent: sorted(k for k in DATA if k.startswith(parent + "__")),
                        lambda s: {"h": "2026-11-04T11:00:00+0100", "dfr": "2026-09-10T14:22:33+0000"}.get(s),
                        "2026-11-09", "2026-11-09T06:00:00Z")


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.reg = make_registry()
        self.ctx = make_ctx(self.reg)

    def test_line_bundle_fields_and_rounding(self):
        b, used, dropped = bundles.build_chart(self.ctx, self.reg.charts["line-chart"])
        self.assertEqual([s["key"] for s in b["series"]], ["h", "c", "gap"])
        self.assertEqual(dropped[0][0], "empty")
        self.assertEqual(b["latest"]["period"], "2026-06")
        self.assertEqual(b["latest"]["values"]["h"], 4.9)
        self.assertEqual(b["latest"]["flag"], None)  # flag of the story series
        self.assertEqual(b["latest"]["periods"]["c"], "2026-05")
        self.assertEqual(b["series"][0]["flags"], {"2026-06": "e"})
        self.assertEqual(b["data_updated"], "2026-11-04T11:00:00+0100")
        self.assertIn("Eurostat (prc_hicp_minr)", b["source"])
        self.assertEqual(b["built_at"], "2026-11-09T06:00:00Z")
        for s in b["series"]:
            for p, v in s["points"]:
                self.assertEqual(v, round(v, 1))
        self.assertIn("gap", used)

    def test_step_series_gets_curve(self):
        b, _, _ = bundles.build_chart(self.ctx, self.reg.charts["step-chart"])
        s = b["series"][0]
        self.assertEqual(s["curve"], "step-after")
        self.assertEqual(s["points"][-1], ["2026-11-09", 2.5])
        self.assertEqual(b["latest"]["values"]["dfr"], 2.5)
        self.assertEqual(b["previous"]["values"]["dfr"], 3.75)

    def test_table_and_heatmap(self):
        b, _, _ = bundles.build_chart(self.ctx, self.reg.charts["bank"])
        self.assertEqual([r["label"] for r in b["rows"]], ["Headline", "Core (May 2026)"])
        self.assertEqual(b["rows"][0]["values"]["m12"], 4.9)
        self.assertIsNone(b["rows"][1]["values"]["m3"])
        self.assertEqual(b["latest"]["period"], "2026-06")
        h, _, _ = bundles.build_chart(self.ctx, self.reg.charts["heat"])
        self.assertEqual(h["columns"], ["2024-02", "2024-03"])
        self.assertEqual(h["rows"], ["Germany", "France"])  # sorted by latest value
        self.assertEqual(h["midpoint"], 2)

    def test_missing_series_everywhere_raises(self):
        reg = make_registry()
        reg.charts["x"] = Chart("x", "inflation", "s", 9, "X", "Y", series=[Ref("empty")], module="t")
        with self.assertRaises(bundles.ChartError):
            bundles.build_chart(make_ctx(reg), reg.charts["x"])

    def test_tile(self):
        t = bundles.tile_entry(self.ctx, self.reg.tiles[0])
        self.assertEqual((t["value"], t["previous"], t["period"], t["flag"], t["decimals"]), (4.9, 4.8, "2026-06", "e", 1))

    def test_round(self):
        self.assertEqual(bundles.rnd(-0.04, 1), 0.0)
        self.assertEqual(bundles.rnd(2.345, 0), 2)
        self.assertIsNone(bundles.rnd(None, 2))


class SiteFilesTests(unittest.TestCase):
    """Write a whole site/data into a temp dir and validate it with eet.check."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (paths.SITE_DATA, paths.CHARTS)
        paths.SITE_DATA = self.tmp.name
        paths.CHARTS = os.path.join(self.tmp.name, "charts")

    def tearDown(self):
        paths.SITE_DATA, paths.CHARTS = self.saved
        self.tmp.cleanup()

    def test_build_site_passes_check(self):
        from eet import build
        reg = make_registry()
        ctx = make_ctx(reg)
        failed = [{"id": "empty", "error": "no observations returned"}]
        built, errors, strip, _ = build.build_site(reg, ctx, sorted(reg.charts), failed, full=True, log=lambda *a: None)
        self.assertEqual(set(built), set(reg.charts))
        rep, n = check.run(self.tmp.name)
        self.assertEqual(rep.errors, [])
        self.assertEqual(n, 4)
        with open(os.path.join(self.tmp.name, "index.json")) as fh:
            idx = json.load(fh)
        self.assertEqual([p["id"] for p in idx["pages"]], [p for p in check.pages.PAGE_IDS])
        self.assertEqual(idx["failed"][0]["chart_ids"], ["bank", "line-chart"])
        self.assertEqual(idx["strip"][0]["decimals"], 1)
        sec = idx["pages"][3]["sections"][0]
        self.assertEqual(sec["tables"], ["bank"])
        self.assertIn("heat", sec["charts"])
        with open(os.path.join(self.tmp.name, "snapshot.csv")) as fh:
            self.assertTrue(fh.readline().startswith("id,label,value"))

    def test_check_catches_errors(self):
        from eet import build
        reg = make_registry()
        build.build_site(reg, make_ctx(reg), sorted(reg.charts), [], full=True, log=lambda *a: None)
        p = os.path.join(self.tmp.name, "charts", "line-chart.json")
        with open(p) as fh:
            b = json.load(fh)
        bad = copy.deepcopy(b)
        bad["series"][0]["role"] = "story"                      # two stories
        bad["series"][1]["points"].append(["2026-Q3", 1.0])    # mixed periods
        bad["series"][2]["curve"] = "smooth"
        bad["built_at"] = "2026-11-09 06:00"
        with open(p, "w") as fh:
            json.dump(bad, fh)
        rep, _ = check.run(self.tmp.name)
        text = "\n".join(rep.errors)
        self.assertIn("2 story series", text)
        self.assertIn("mixed period formats", text)
        self.assertIn("curve", text)
        self.assertIn("built_at", text)

    def test_check_table_formats_and_categorical_bars(self):
        rep = check.Report()
        b = {"id": "debt", "page": "fiscal", "section": "s", "order": 1, "title": "t", "kicker": "", "subtitle": "",
             "type": "bar", "units": "%", "frequency": "A", "geo": "EA21", "reference_lines": [], "markers": [],
             "default_window": "max", "source": "", "source_url": "", "notes": "", "methods_id": "debt",
             "original": False, "built_at": "2026-11-09T06:00:00Z", "y_domain": None, "data_updated": None,
             "highlight": "IT",
             "series": [{"key": "debt", "label": "Debt", "role": "base", "points": [["Italy", 137.1], ["France", 116.0]]}],
             "latest": {"period": "2025", "values": {"debt": 137.1}, "flag": None}, "previous": None}
        check.check_bundle(b, "debt.json", rep)
        self.assertEqual(rep.errors, [])
        t = dict(b, id="tab", methods_id="tab", type="table", series=[], latest=None,
                 columns=[{"key": "a", "label": "A", "format": "text"}, {"key": "n", "label": "N", "format": "pct"}],
                 rows=[{"label": "x", "values": {"a": "Sep 2026", "n": 1.5}, "flag": None},
                       {"label": "y", "values": {"a": None, "n": None}, "flag": None}])
        check.check_bundle(t, "tab.json", rep)
        self.assertEqual(rep.errors, [])                      # text columns hold strings
        bad = dict(t, rows=[{"label": "x", "values": {"a": 1, "n": "1.5"}, "flag": None}])
        check.check_bundle(bad, "tab.json", rep)
        self.assertTrue(any("text value a=1" in e for e in rep.errors))
        self.assertTrue(any("value n='1.5' is not a number" in e for e in rep.errors))


if __name__ == "__main__":
    unittest.main()
