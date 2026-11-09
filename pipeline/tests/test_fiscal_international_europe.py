"""Fiscal, international and Europe sections: derived series, build hooks and the categorical-bar
workaround (no network)."""
import unittest

import _util  # noqa: F401

from eet import bundles, check, registry
from eet.context import BuildContext
from eet.registry import europe, fiscal, international


def ctx_with(data, today="2026-11-09"):
    """A BuildContext over the real registry whose store is the dict ``data`` (id -> obs)."""
    reg = registry.load()

    def children(parent):
        return sorted(k for k in data if k.startswith(parent + "__"))

    return BuildContext(reg, lambda sid: data.get(sid, []), children, lambda sid: "2026-10-21T11:00:00+0200",
                        today, "2026-11-09T06:00:00Z")


def annual(values, first=2020):
    return [(str(first + i), v, "") for i, v in enumerate(values)]


class HelperTests(unittest.TestCase):
    def test_pick_period_skips_early_publisher(self):
        data = {"A": annual([1, 2, 3]), "B": annual([1, 2]), "C": annual([1, 2])}
        self.assertEqual(fiscal.pick_period(data), "2021")       # only 1 of 3 has 2022
        self.assertEqual(fiscal.pick_period(data, min_share=0.3), "2022")
        half = {"A": [("2026-S1", 1.0, "")], "B": [("2025-S2", 1.0, ""), ("2026-S1", 2.0, "")]}
        self.assertEqual(fiscal.pick_period(half), "2026-S1")

    def test_period_text(self):
        self.assertEqual(fiscal.period_text("2026-S1"), "first half of 2026")
        self.assertEqual(fiscal.period_text("2026-Q2"), "Q2 2026")
        self.assertEqual(fiscal.period_text("2025"), "2025")

    def test_primary_balance_and_r_minus_g(self):
        pb = fiscal.primary_balance(annual([-3.0, -4.0, None]), annual([1.5, 2.0, 2.0]))
        self.assertEqual(pb, [("2020", -1.5, ""), ("2021", -2.0, "")])
        rg = fiscal.r_minus_g(annual([3.0, 3.5]), annual([100.0, 104.0]))
        self.assertEqual(len(rg), 1)
        self.assertAlmostEqual(rg[0][1], 3.5 - 4.0)

    def test_sum12_needs_twelve_calendar_months(self):
        obs = [(f"2025-{m:02d}", 1000.0, "") for m in range(1, 13)] + [("2026-02", 1000.0, "")]
        out = international.sum12(obs)
        self.assertEqual(out, [("2025-12", 12.0, "")])            # 2026-02 lacks 2026-01

    def test_usd_index_inverts_and_rebases(self):
        obs = [("2019-01", 0.8, ""), ("2019-02", 1.0, ""), ("2020-01", 0.5, "")]
        out = international.usd_index(obs)
        base = (1 / 0.8 + 1.0) / 2
        self.assertAlmostEqual(out[2][1], 2.0 / base * 100)
        self.assertEqual(international.clean_flags([("2020-01", 1.0, "A"), ("2020-02", 1.0, "p")]),
                         [("2020-01", 1.0, ""), ("2020-02", 1.0, "p")])


class CategoricalBarTests(unittest.TestCase):
    def test_country_bars_bundle_passes_contract_check(self):
        data = {
            "fis_debt_a__EA21": annual([85.0, 87.3]),
            "fis_debt_a__IT": annual([135.0, 136.7]),
            "fis_debt_a__FR": annual([113.0, 115.7]),
            "fis_debt_a__DE": annual([63.0, 62.5]),
            "fis_debt_a__EE": annual([24.0]),                     # late: 2021 not yet published
        }
        ctx = ctx_with(data)
        chart = ctx.reg.charts["gov-debt-countries"]
        b, used, dropped = bundles.build_chart(ctx, chart)
        self.assertEqual(b["type"], "bar")
        pts = b["series"][0]["points"]
        self.assertEqual(pts[0], ["Italy", 136.7])                # sorted descending
        self.assertEqual([p[0] for p in pts], ["Italy", "France", "Euro area", "Germany"])
        self.assertEqual(b["highlight"], "Italy")
        self.assertEqual(b["latest"], {"period": "2021", "values": {"debt": 87.3}, "flag": None})
        self.assertEqual(b["previous"]["values"], {"debt": 85.0})
        self.assertIn("Estonia", b["notes"])
        self.assertTrue(b["subtitle"].endswith(", 2021"))
        rep = check.Report()
        check.check_bundle(b, "gov-debt-countries.json", rep)
        self.assertEqual(rep.errors, [])

    def test_half_year_bars(self):
        data = {"eu_elec_price__EA": [("2025-S2", 28.0, ""), ("2026-S1", 28.5, "")],
                "eu_elec_price__IT": [("2025-S2", 30.0, ""), ("2026-S1", 31.2, "")]}
        ctx = ctx_with(data)
        b, _, _ = bundles.build_chart(ctx, ctx.reg.charts["electricity-prices"])
        self.assertEqual(b["latest"]["period"], "2026-S1")
        self.assertEqual(b["highlight"], "Italy")
        rep = check.Report()
        check.check_bundle(b, "electricity-prices.json", rep)
        self.assertEqual(rep.errors, [])


class HookTests(unittest.TestCase):
    def test_forecast_joins_at_last_outturn(self):
        data = {"fis_balance_a__EA21": annual([-3.4, -3.0, -3.0], 2023),
                "ec_fc_balance__EA": annual([-3.5, -3.1, -2.9, -3.3, -3.5], 2023)}
        ctx = ctx_with(data)
        b, _, _ = bundles.build_chart(ctx, ctx.reg.charts["gov-forecast-deficit"])
        fc = [s for s in b["series"] if s["key"] == "forecast"][0]
        self.assertEqual([p[0] for p in fc["points"]], ["2025", "2026", "2027"])

    def test_fiscal_table_columns_and_primary(self):
        data = {"fis_balance_a__EA21": annual([-3.0], 2025), "fis_interest_a__EA21": annual([1.9], 2025),
                "fis_debt_a__EA21": annual([87.3], 2025), "fis_balance_a__IT": annual([-3.1], 2025),
                "fis_interest_a__IT": annual([3.8], 2025), "fis_debt_a__IT": annual([136.7], 2025),
                "ec_fc_balance__IT": annual([-2.8], 2026)}
        ctx = ctx_with(data)
        b, _, _ = bundles.build_chart(ctx, ctx.reg.charts["fiscal-table"])
        self.assertEqual(b["rows"][0]["label"], "Euro area")
        it = [r for r in b["rows"] if r["label"] == "Italy"][0]
        self.assertAlmostEqual(it["values"]["primary"], 0.7)
        self.assertEqual(it["values"]["fc_balance"], -2.8)
        self.assertIn("Balance 2026, EC forecast", [c["label"] for c in b["columns"]])
        rep = check.Report()
        check.check_bundle(b, "fiscal-table.json", rep)
        self.assertEqual(rep.errors, [])

    def test_glance_spread_and_periods(self):
        data = {"y10_members__DE": [("2026-09", 2.80, "")], "y10_members__IT": [("2026-09", 3.69, "")],
                "y10_members__EA": [("2026-09", 3.26, "")],
                "glance_unemp__EA21": [("2026-09", 6.5, "")], "glance_unemp__IT": [("2026-09", 6.3, "")],
                "glance_unemp__DE": [("2026-09", 4.1, ""), ("2026-10", 4.1, "")]}
        ctx = ctx_with(data)
        b, _, _ = bundles.build_chart(ctx, ctx.reg.charts["europe-at-a-glance"])
        cols = {c["key"]: c["label"] for c in b["columns"]}
        self.assertEqual(cols["unemp"], "Unemployment, %, Sep 2026")
        rows = {r["label"]: r["values"] for r in b["rows"]}
        self.assertAlmostEqual(rows["Italy"]["spread"], 0.89)
        self.assertAlmostEqual(rows["Euro area"]["spread"], 0.46)
        self.assertEqual(rows["Germany"]["spread"], 0.0)

    def test_overview_notes_older_periods(self):
        data = {"glance_gdp_yoy__EA21": [("2026-Q3", 1.3, "")], "oecd_gdp_yoy__GBR": [("2026-Q2", 1.4, "A")],
                "hicp_headline": [("2026-10", 4.0, "e")], "bis_cpi__US": [("2026-09", 3.7, "A")]}
        ctx = ctx_with(data)
        b, _, _ = bundles.build_chart(ctx, ctx.reg.charts["intl-overview"])
        self.assertIn("United Kingdom gdp Q2 2026", b["notes"])
        self.assertEqual(b["columns"][0]["label"], "GDP, % y/y (Q3 2026)")
        self.assertEqual(b["latest"]["period"], "2026-10")


class RegistryShapeTests(unittest.TestCase):
    def test_reserved_ids_and_pages(self):
        reg = registry.load()
        self.assertEqual(reg.charts["gov-debt"].page, "fiscal")
        self.assertEqual(reg.charts["economic-sentiment"].page, "europe")
        for c in reg.charts.values():
            if c.module in ("fiscal", "international", "europe"):
                self.assertTrue(c.what, c.id)                      # every chart has a methods text
                self.assertEqual(c.page, c.module, c.id)


if __name__ == "__main__":
    unittest.main()
