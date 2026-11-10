"""Core behaviour the section modules used to work around (no network): categorical bars, text
table columns, half-yearly periods, BIS/OECD "normal value" flags, derived-series provenance,
failures kept across partial builds, and concurrent writes of the shared files."""
import json
import os
import tempfile
import threading
import unittest

import _util  # noqa: F401

from eet import build, bundles, check, paths, sources, store, transforms
from eet import periods as P
from eet.context import BuildContext
from eet.parsers import csvdata
from eet.registry import Registry, validate
from eet.spec import Chart, Derived, Ref, Section, Series


def _ctx(reg, data, stamps=None):
    stamps = stamps or {}

    def children(parent):
        return sorted(k for k in data if k.startswith(parent + "__"))

    return BuildContext(reg, lambda sid: data.get(sid, []), children, lambda sid: stamps.get(sid), "2026-11-09",
                        "2026-11-09T06:00:00Z")


class CategoricalTests(unittest.TestCase):
    def test_latest_previous_skips_category_points(self):
        cats = [{"key": "debt", "label": "Debt", "role": "base", "points": [["Italy", 137.1], ["France", 116.0]]}]
        self.assertEqual(bundles.latest_previous(cats, lambda k: 1, lambda s, p: None), (None, None))
        timed = cats + [{"key": "ea", "label": "EA", "role": "story", "points": [["2024", 1.0], ["2025", 2.0]]}]
        latest, prev = bundles.latest_previous(timed, lambda k: 1, lambda s, p: None)
        self.assertEqual(latest["period"], "2025")
        self.assertEqual(latest["values"], {"ea": 2.0})

    def test_hook_bars_without_any_ref(self):
        reg = Registry()
        reg.series["d"] = Series("d", "eurostat", dataset="gov_10dd_edpt1", split="geo", freq="A", module="t")
        reg.sections[("fiscal", "s")] = Section("fiscal", "s", "S", module="t")

        def bars(ctx, chart):
            panel = ctx.panel("d")
            pts = sorted(([k, o[-1][1]] for k, o in panel.items()), key=lambda x: -x[1])
            return {"series": [{"key": "debt", "label": "Debt", "role": "base", "points": pts}],
                    "latest": {"period": "2025", "values": {"debt": 87.33}, "flag": None}}

        reg.charts["bars"] = Chart("bars", "fiscal", "s", 1, "T", "S", type="bar", frequency="A", build=bars,
                                   highlight="IT", module="t")
        reg.charts["bare"] = Chart("bare", "fiscal", "s", 2, "T", "S", type="bar", frequency="A",
                                   build=lambda ctx, c: {"series": bars(ctx, c)["series"]}, module="t")
        validate(reg)
        ctx = _ctx(reg, {"d__IT": [("2025", 137.14, "")], "d__FR": [("2025", 115.96, "")]})
        b, used, _ = bundles.build_chart(ctx, reg.charts["bars"])
        self.assertEqual(b["series"][0]["points"], [["IT", 137.1], ["FR", 116.0]])
        self.assertEqual(b["latest"]["values"], {"debt": 87.33})
        self.assertIn("d__IT", used)
        self.assertEqual(b["source"], "Eurostat (gov_10dd_edpt1)")
        rep = check.Report()
        check.check_bundle(b, "bars.json", rep)
        self.assertEqual(rep.errors, [])
        b2, _, _ = bundles.build_chart(ctx, reg.charts["bare"])  # no latest from the hook
        self.assertEqual(b2["latest"], {"period": None, "values": {}, "flag": None})


class SeriesDecimalsTests(unittest.TestCase):
    def test_series_at_other_precision_carries_decimals(self):
        reg = Registry()
        reg.series["a"] = Series("a", "eurostat", dataset="d", decimals=2, module="t")
        reg.series["b"] = Series("b", "eurostat", dataset="d", decimals=2, module="t")
        reg.sections[("gdp", "s")] = Section("gdp", "s", "S", module="t")
        reg.charts["c"] = Chart("c", "gdp", "s", 1, "T", "S", decimals=2,
                                series=[Ref("a", "a"), Ref("b", "b", role="story", decimals=1)], module="t")
        validate(reg)
        ctx = _ctx(reg, {"a": [("2026-Q3", 0.123, "")], "b": [("2026-Q3", 0.444, "")]})
        b, _, _ = bundles.build_chart(ctx, reg.charts["c"])
        self.assertNotIn("decimals", b["series"][0])
        self.assertEqual(b["series"][1]["decimals"], 1)
        self.assertEqual(b["series"][1]["points"], [["2026-Q3", 0.4]])
        rep = check.Report()
        check.check_bundle(b, "c.json", rep)
        self.assertEqual(rep.errors, [])


class SourceLineTests(unittest.TestCase):
    def test_join_sources_groups_by_publisher(self):
        self.assertEqual(bundles.join_sources(["Eurostat (a)", "ECB (X)", "Eurostat (b)", "Eurostat (a)", "OECD"]),
                         "Eurostat (a, b); ECB (X); OECD")


class HalfYearTests(unittest.TestCase):
    def test_periods(self):
        self.assertEqual(P.freq_of("2026-S1"), "S")
        self.assertEqual(P.shift("2026-S1", -1), "2025-S2")
        self.assertEqual(P.shift("2025-S2", 3), "2027-S1")
        self.assertEqual(P.start_date("2026-S2").isoformat(), "2026-07-01")
        self.assertEqual(P.end_date("2026-S1").isoformat(), "2026-06-30")
        self.assertEqual(P.to_freq("2026-08", "S"), "2026-S2")
        self.assertEqual(P.normalize("2026S2"), "2026-S2")
        self.assertEqual(P.normalize("2026-H1"), "2026-S1")
        self.assertLess(P.compare_key("2026-S1"), P.compare_key("2026-S2"))
        obs = [("2025-S1", 100.0, ""), ("2025-S2", 102.0, ""), ("2026-S1", 105.0, "")]
        self.assertAlmostEqual(transforms.yoy(obs)[-1][1], 5.0)

    def test_half_year_bundle_passes_check(self):
        b = {"id": "e", "page": "europe", "section": "s", "order": 1, "title": "t", "kicker": "", "subtitle": "",
             "type": "line", "units": "%", "frequency": "S", "geo": "EA21", "reference_lines": [], "markers": [],
             "default_window": "max", "source": "", "source_url": "", "notes": "", "methods_id": "e",
             "original": False, "built_at": "2026-11-09T06:00:00Z", "y_domain": None, "data_updated": None,
             "series": [{"key": "p", "label": "P", "role": "story", "points": [["2025-S2", 1.0], ["2026-S1", 2.0]]}],
             "latest": {"period": "2026-S1", "values": {"p": 2.0}, "flag": None}, "previous": None}
        rep = check.Report()
        check.check_bundle(b, "e.json", rep)
        self.assertEqual(rep.errors, [])


class NormalFlagTests(unittest.TestCase):
    BODY = ("KEY,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
            "WS_CBPOL.M.US,2026-09,4.125,A\nWS_CBPOL.M.US,2026-10,3.875,P\n")

    def test_bis_and_oecd_drop_A(self):
        for src in ("bis", "oecd"):
            s = Series("x", src, dataset="WS_CBPOL", key="M.US")
            groups, _ = sources.parse_body(s, self.BODY)
            self.assertEqual(groups["x"], [("2026-09", 4.125, ""), ("2026-10", 3.875, "P")], src)

    def test_other_sources_keep_flags(self):
        s = Series("x", "ecb", dataset="FM", key="M.U2")
        groups, _ = sources.parse_body(s, self.BODY)
        self.assertEqual(groups["x"][0][2], "A")
        self.assertEqual(csvdata.parse(self.BODY)[0][2], "A")


class DerivedProvenanceTests(unittest.TestCase):
    def test_cached_derived_credits_its_inputs(self):
        reg = Registry()
        reg.series["a"] = Series("a", "eurostat", dataset="ds_a", module="t")
        reg.series["b"] = Series("b", "ecb", dataset="INW", key="Q.U2", module="t")
        reg.derived["gap"] = Derived("gap", ["a", "b"], transforms.spread, module="t")
        reg.sections[("inflation", "s")] = Section("inflation", "s", "S", module="t")
        for cid in ("first", "second"):
            reg.charts[cid] = Chart(cid, "inflation", "s", 1, "T", "S", series=[Ref("gap", "gap", "Gap", "story")],
                                    module="t")
        validate(reg)
        data = {"a": [("2026-01", 3.0, ""), ("2026-02", 3.5, "")], "b": [("2026-01", 1.0, ""), ("2026-02", 1.0, "")]}
        ctx = _ctx(reg, data, {"a": "2026-10-01T11:00:00+0200", "b": "2026-11-05T15:00:00+0100"})
        bundles.build_chart(ctx, reg.charts["first"])             # computes and caches "gap"
        b, used, _ = bundles.build_chart(ctx, reg.charts["second"])  # reads "gap" from the cache
        self.assertTrue({"a", "b", "gap"} <= set(used))
        self.assertEqual(b["source"], "Eurostat (ds_a); ECB (INW)")
        self.assertEqual(b["data_updated"], "2026-11-05T15:00:00+0100")
        names = [x["name"] for x in bundles.methods_entry(ctx, reg.charts["second"], used, b)["sources"]]
        self.assertEqual(names, ["Eurostat (ds_a)", "ECB (INW)"])


class SharedFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (paths.SITE_DATA, paths.CHARTS, paths.LOCK)
        paths.SITE_DATA = self.tmp.name
        paths.CHARTS = os.path.join(self.tmp.name, "charts")
        paths.LOCK = os.path.join(self.tmp.name, "build.lock")

    def tearDown(self):
        paths.SITE_DATA, paths.CHARTS, paths.LOCK = self.saved
        self.tmp.cleanup()

    def _reg(self):
        reg = Registry()
        for sid in ("a", "b"):
            reg.series[sid] = Series(sid, "eurostat", dataset="d_" + sid, module="m_" + sid)
        reg.series["p"] = Series("p", "eurostat", dataset="d_p", split="geo", module="m_b")
        reg.sections[("inflation", "s")] = Section("inflation", "s", "S", module="m_a")
        reg.charts["ca"] = Chart("ca", "inflation", "s", 1, "A", "S", series=[Ref("a", "a", role="story")],
                                 module="m_a")
        reg.charts["cb"] = Chart("cb", "inflation", "s", 2, "B", "S", series=[Ref("b", "b", role="story")],
                                 module="m_b")
        validate(reg)
        return reg

    def test_merge_failed(self):
        reg = self._reg()
        prev = [{"id": "b", "error": "old"}, {"id": "p__DE", "error": "old"}, {"id": "a", "error": "old"},
                {"id": "gone", "error": "series removed from the registry"}]
        # a partial live run that fetched only "a": b and p__DE stand, a is cleared, gone is dropped
        out = build.merge_failed(reg, [], prev, attempted={"a"})
        self.assertEqual([f["id"] for f in out], ["b", "p__DE"])
        # an offline run attempts nothing live: every earlier failure in the registry stands
        out = build.merge_failed(reg, [{"id": "a", "error": "new"}], prev, attempted=frozenset())
        self.assertEqual([(f["id"], f["error"]) for f in out], [("a", "new"), ("b", "old"), ("p__DE", "old")])

    def test_partial_build_keeps_other_modules_failures(self):
        reg = self._reg()
        data = {"a": [("2026-01", 1.0, "")], "b": [("2026-01", 2.0, "")]}
        with open(os.path.join(self.tmp.name, "index.json"), "w") as fh:
            json.dump({"failed": [{"id": "b", "error": "HTTP 504", "chart_ids": ["cb"]}]}, fh)
        # e.g. build --offline --only m_a
        _, _, _, failed = build.build_site(reg, _ctx(reg, data), ["ca"], [], full=False, log=lambda *a: None)
        self.assertEqual([(f["id"], f["chart_ids"]) for f in failed], [("b", ["cb"])])
        with open(os.path.join(self.tmp.name, "index.json")) as fh:
            self.assertEqual(json.load(fh)["failed"][0]["id"], "b")

    def test_concurrent_meta_writes_merge(self):
        root = os.path.join(self.tmp.name, "store")
        store.save_meta({"x": {"updated": "1"}}, root=root)

        def write(i):
            store.save_meta({f"s{i}": {"updated": str(i)}}, root=root)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        meta = store.load_meta(root)
        self.assertEqual(set(meta), {"x"} | {f"s{i}" for i in range(8)})
        self.assertEqual([f for f in os.listdir(root) if f.endswith(".tmp")], [])

    def test_atomic_write_leaves_no_temp(self):
        p = os.path.join(self.tmp.name, "x", "f.json")
        paths.atomic_write(p, "{}\n")
        paths.atomic_write(p, "[]\n")
        with open(p) as fh:
            self.assertEqual(fh.read(), "[]\n")
        self.assertEqual(os.listdir(os.path.dirname(p)), ["f.json"])


if __name__ == "__main__":
    unittest.main()
