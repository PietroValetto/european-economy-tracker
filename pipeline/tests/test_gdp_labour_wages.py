"""Section-local computations of the GDP, labour, national labour and wages modules."""
import unittest

import _util  # noqa: F401

from eet import periods as P
from eet import registry
from eet.context import BuildContext, Missing
from eet.registry import gdp, labour, national_labour, wages


def monthly(values, start="2020-01"):
    out, p = [], start
    for v in values:
        out.append((p, v, ""))
        p = P.shift(p, 1)
    return out


def ctx_for(data, today="2026-11-09"):
    reg = registry.load()
    return BuildContext(reg, lambda sid: data.get(sid, []),
                        lambda parent: sorted(k for k in data if k.startswith(parent + "__")),
                        lambda sid: None, today, "2026-11-09T06:00:00Z")


class SahmTests(unittest.TestCase):
    def test_flat_rate_is_zero(self):
        out = labour.sahm(monthly([6.5] * 20))
        self.assertEqual(out[0][0], "2021-03")  # needs 15 months
        self.assertTrue(all(abs(v) < 1e-9 for _, v, _ in out))

    def test_rise_triggers(self):
        out = dict((p, v) for p, v, _ in labour.sahm(monthly([6.0] * 15 + [6.5, 7.0, 7.5])))
        self.assertAlmostEqual(out["2021-06"], 1.0)  # mean(6.5, 7, 7.5) - 6.0

    def test_gap_breaks_window(self):
        obs = monthly([6.0] * 20)
        obs[10] = (obs[10][0], None, "")
        out = labour.sahm(obs)
        self.assertNotIn("2021-03", [p for p, _, _ in out])


class GdpTests(unittest.TestCase):
    def test_ex_ireland(self):
        ea = [("2026-Q1", 1000.0, ""), ("2026-Q2", 1010.0, ""), ("2026-Q3", 1020.0, "")]
        ie = [("2026-Q1", 100.0, ""), ("2026-Q2", 110.0, ""), ("2026-Q3", 110.0, "e")]
        out = gdp.ex_ireland_qoq(ea, ie)
        self.assertEqual([p for p, _, _ in out], ["2026-Q2", "2026-Q3"])
        self.assertAlmostEqual(out[0][1], 0.0)            # 900 -> 900
        self.assertAlmostEqual(out[1][1], 10 / 900 * 100)  # 900 -> 910
        self.assertEqual(gdp.ex_ireland_level(ea, ie)[0], ("2026-Q1", 900.0, ""))

    def test_gdp_table_and_heatmap(self):
        q = ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]
        data = {"gdp_comp_qoq__B1GQ": [(p, v, "") for p, v in zip(q, [0.2, 0.0, 0.6, 0.4])],
                "gdp_comp_qoq__P6": [(p, v, "") for p, v in zip(q[:3], [0.4, -0.5, 3.5])],
                "gdp_comp_yoy__B1GQ": [("2026-Q3", 1.3, "")],
                "gdp_comp_yoy__P6": [("2026-Q2", 4.1, "")],
                "gdp_qoq_country__EA21": [(p, 0.3, "") for p in q],
                "gdp_qoq_country__DE": [(p, 0.1, "") for p in q],
                "gdp_qoq_country__IE": [(p, 5.0, "") for p in q]}
        ctx = ctx_for(data)
        t = gdp.gdp_table(ctx, None)
        self.assertEqual([c["label"] for c in t["columns"]][2:], ["Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"])
        self.assertEqual(t["rows"][0]["values"]["qoq"], 0.4)
        self.assertEqual(t["rows"][1]["label"], "Exports (Q2 2026)")
        self.assertIsNone(t["rows"][1]["values"]["q3"])
        h = gdp.growth_heatmap(ctx, None)
        self.assertEqual(h["row_keys"][0], "EA21")
        self.assertEqual(h["row_keys"][1:], ["IE", "DE"])  # no level data: no ex-Ireland row; sorted
        self.assertEqual(h["columns"], q)


class LabourTests(unittest.TestCase):
    def test_beveridge_segments(self):
        u = monthly([7.0] * 12 * 17, start="2010-01")
        v = [(f"{y}-Q{k}", 2.0, "") for y in range(2010, 2027) for k in range(1, 5)]
        ctx = ctx_for({"unemployment_rate": u, "job_vacancy_rate": v})
        out = labour.beveridge(ctx, None)
        keys = [s["key"] for s in out["series"]]
        self.assertEqual(keys, ["pre", "pandemic", "recent"])
        self.assertEqual(out["series"][0]["points"][0], ["2010-Q1", 7.0, 2.0])
        self.assertEqual([s["role"] for s in out["series"]].count("story"), 1)

    def test_rates_table_quarterly_lags(self):
        v = [(f"{y}-Q{k}", 2.0 + k / 10, "") for y in (2025, 2026) for k in range(1, 5)][:-2]
        ctx = ctx_for({"job_vacancy_rate": v, "unemployment_rate": monthly([6.0] * 13, "2025-09")})
        t = labour.labour_rates_table(ctx, None)
        row = [r for r in t["rows"] if r["label"].startswith("Job vacancy")][0]
        self.assertEqual(row["values"]["latest"], 2.2)   # 2026-Q2
        self.assertEqual(row["values"]["m3"], 2.1)       # 2026-Q1
        self.assertEqual(row["values"]["m12"], 2.2)      # 2025-Q2

    def test_weekly_keeps_latest(self):
        obs = [(f"2026-10-{d:02d}", float(d), "") for d in range(1, 31)]
        w = labour.weekly(obs)
        self.assertEqual(w[-1][0], "2026-10-30")
        self.assertEqual(w[-2][0], "2026-10-23")


class WagesTests(unittest.TestCase):
    def test_deflate(self):
        out = wages.deflate([("2026-Q2", 3.0, "")], [("2026-Q2", 1.0, ""), ("2026-Q3", 2.0, "")])
        self.assertAlmostEqual(out[0][1], (1.03 / 1.01 - 1) * 100)
        self.assertEqual(len(out), 1)

    def test_comp_per_employee(self):
        comp = [("2025-Q2", 100.0, ""), ("2026-Q2", 110.0, "")]
        emp = [("2025-Q2", 10.0, ""), ("2026-Q2", 10.5, "")]
        out = wages.comp_per_employee_yoy(comp, emp)
        self.assertAlmostEqual(out[-1][1], (110 / 10.5) / 10 * 100 - 100)

    def test_hicp_quarterly_needs_complete_quarters(self):
        idx = monthly([100.0] * 12 + [102.0] * 13, "2025-01")  # ends 2027-01: 2027-Q1 incomplete
        out = dict((p, v) for p, v, _ in wages.hicp_quarterly_yoy(idx))
        self.assertAlmostEqual(out["2026-Q1"], 2.0)
        self.assertNotIn("2027-Q1", out)

    def test_wage_tracker_split_at_current_month(self):
        ewt = monthly([2.0] * 30, "2025-01")  # to 2027-06
        ctx = ctx_for({"ewt_smoothed": ewt, "ewt_unsmoothed": ewt})
        out = wages.ewt_chart(ctx, None)
        past, ahead = out["series"][0], out["series"][1]
        self.assertEqual(past["points"][-1][0], "2026-11")
        self.assertEqual(ahead["points"][0][0], "2026-11")
        self.assertEqual(out["markers"][0]["x"], "2026-11")
        with self.assertRaises(Missing):
            wages.ewt_chart(ctx_for({}), None)

    def test_gus_index_to_percent(self):
        self.assertEqual(national_labour.minus_100([("2026-09", 105.9, "")]), [("2026-09", 105.9 - 100, "")])


class RegistryShapeTests(unittest.TestCase):
    def test_reserved_ids_and_methods_text(self):
        reg = registry.load()
        for cid, page in [("gdp-growth", "gdp"), ("unemployment-rate", "labour"), ("job-vacancy-rate", "labour"),
                          ("indeed-postings", "labour"), ("wage-growth", "wages")]:
            self.assertEqual(reg.charts[cid].page, page)
        for c in reg.charts.values():
            if c.module in ("gdp", "labour", "national_labour", "wages"):
                self.assertTrue(c.what and c.caveats is not None and (c.transform_text or c.series), c.id)
        for s in reg.series.values():
            if s.module == "national_labour":
                self.assertTrue(s.source_name and s.source_url, s.id)


if __name__ == "__main__":
    unittest.main()
