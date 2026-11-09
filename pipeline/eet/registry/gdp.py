"""GDP page: quarterly growth and its expenditure components, the level of output against 2019,
growth across all euro area members, and the monthly activity indicators.

Sources (one per series, CONTRACT section 2): Eurostat ``namq_10_gdp`` (national accounts, the
preliminary flash at t+30 and the full release with components at t+65) and the short-term
statistics datasets ``sts_inpr_m`` (industry), ``sts_trtu_m`` (retail), ``sts_setu_m`` (services)
and ``sts_copr_m`` (construction). In the STS datasets m/m changes exist only seasonally and
calendar adjusted (SCA) and y/y changes only calendar adjusted (CA): other combinations are empty.
"""
from .. import geo
from .. import periods as P
from .. import builders
from ..context import Missing
from ..spec import Chart, Derived, Ref, Section, Series

PAGE = "gdp"
NAMQ = "https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table"

COMPONENTS = {"P31_S14_S15": "Household consumption", "P3_S13": "Government consumption",
              "P51G": "Investment (gross fixed capital formation)", "P52_P53": "Inventories and valuables",
              "P6X7": "Net exports"}
TABLE_ITEMS = {"B1GQ": "GDP", "P31_S14_S15": "Household consumption", "P3_S13": "Government consumption",
               "P51G": "Investment (GFCF)", "P6": "Exports", "P7": "Imports"}
LEVEL_GEOS = ["EA21", "IE"] + geo.STRIP


def _sts(sid, dataset, nace, indic, s_adj, unit, label, start="2000-01"):
    return Series(sid, "eurostat", dataset=dataset,
                  filters={"geo": "EA21", "indic_bt": indic, "nace_r2": nace, "s_adj": s_adj, "unit": unit},
                  freq="M", unit="%", label=label, start=start)


SERIES = [
    Series("gdp_yoy", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "unit": "CLV_PCH_SM", "s_adj": "SCA", "na_item": "B1GQ"}, freq="Q",
           unit="% y/y", label="Real GDP, % change on a year earlier", start="1995-Q1"),
    Series("gdp_contrib", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "unit": "CON_PPCH_PRE", "s_adj": "SCA", "na_item": list(COMPONENTS)},
           split="na_item", labels=COMPONENTS, freq="Q", unit="pp", decimals=2, start="1995-Q1",
           label="Contributions to real GDP growth, q/q"),
    Series("gdp_comp_qoq", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "unit": "CLV_PCH_PRE", "s_adj": "SCA", "na_item": list(TABLE_ITEMS)},
           split="na_item", labels=TABLE_ITEMS, freq="Q", unit="% q/q", start="2015-Q1",
           label="GDP and components, % q/q"),
    Series("gdp_comp_yoy", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "unit": "CLV_PCH_SM", "s_adj": "SCA", "na_item": list(TABLE_ITEMS)},
           split="na_item", labels=TABLE_ITEMS, freq="Q", unit="% y/y", start="2015-Q1",
           label="GDP and components, % y/y"),
    Series("gdp_level", "eurostat", dataset="namq_10_gdp",
           filters={"unit": "CLV20_MEUR", "s_adj": "SCA", "na_item": "B1GQ", "geo": LEVEL_GEOS}, split="geo",
           freq="Q", unit="EUR mn, chain-linked 2020", decimals=0, start="1995-Q1",
           label="Real GDP, chain-linked volumes (2020), EUR million"),
    Series("gdp_qoq_country", "eurostat", dataset="namq_10_gdp",
           filters={"unit": "CLV_PCH_PRE", "s_adj": "SCA", "na_item": "B1GQ", "geo": ["EA21"] + geo.EURO_AREA},
           split="geo", freq="Q", unit="% q/q", start="2015-Q1", label="Real GDP by country, % q/q"),
    _sts("ip_mom", "sts_inpr_m", "B-D", "PRD", "SCA", "PCH_PRE", "Industrial production, % m/m (SCA)", "1991-01"),
    _sts("ip_yoy", "sts_inpr_m", "B-D", "PRD", "CA", "PCH_SM", "Industrial production, % y/y (CA)", "1991-01"),
    _sts("retail_mom", "sts_trtu_m", "G47", "VOL_SLS", "SCA", "PCH_PRE", "Retail trade volume, % m/m (SCA)"),
    _sts("retail_yoy", "sts_trtu_m", "G47", "VOL_SLS", "CA", "PCH_SM", "Retail trade volume, % y/y (CA)"),
    _sts("services_mom", "sts_setu_m", "H-N_X_K", "NETTUR", "SCA", "PCH_PRE", "Services turnover, % m/m (SCA)"),
    _sts("services_yoy", "sts_setu_m", "H-N_X_K", "NETTUR", "CA", "PCH_SM", "Services turnover, % y/y (CA)"),
    _sts("construction_mom", "sts_copr_m", "F", "PRD", "SCA", "PCH_PRE", "Construction output, % m/m (SCA)"),
    _sts("construction_yoy", "sts_copr_m", "F", "PRD", "CA", "PCH_SM", "Construction output, % y/y (CA)"),
]


def ex_ireland_qoq(ea, ie):
    """Euro area GDP excluding Ireland, % q/q, from chain-linked levels (EA21 minus IE).

    Chain-linked volumes are not strictly additive, so the difference is an approximation; it is
    close because both are in 2020 reference-year euros. Periods where either level is missing
    are skipped.
    """
    iv = {p: v for p, v, _ in ie}
    lv = [(p, v - iv[p], f) for p, v, f in ea if v is not None and iv.get(p) is not None]
    d = {p: v for p, v, _ in lv}
    out = []
    for p, v, f in lv:
        b = d.get(P.shift(p, -1))
        if b:
            out.append((p, (v / b - 1.0) * 100.0, f))
    return out


def ex_ireland_level(ea, ie):
    iv = {p: v for p, v, _ in ie}
    return [(p, v - iv[p], f) for p, v, f in ea if v is not None and iv.get(p) is not None]


DERIVED = [
    Derived("gdp_qoq_ea_ex_ie", ["gdp_level__EA21", "gdp_level__IE"], ex_ireland_qoq, freq="Q", unit="% q/q",
            label="Euro area excluding Ireland (approximation)"),
    Derived("gdp_level_ea_ex_ie", ["gdp_level__EA21", "gdp_level__IE"], ex_ireland_level, freq="Q",
            unit="EUR mn", decimals=0, label="Euro area excluding Ireland (approximation)"),
]

SECTIONS = [
    Section(PAGE, "growth", "Growth and its components",
            "Quarterly real GDP and how much consumption, investment, government, inventories and trade "
            "added to it.", 10),
    Section(PAGE, "levels", "Output since the pandemic",
            "The level of real GDP against the last quarter before the pandemic.", 20),
    Section(PAGE, "countries", "Across the euro area",
            "Quarterly growth in every member state. Ireland's multinational accounting can move the euro "
            "area figure on its own.", 30),
    Section(PAGE, "monthly", "Monthly activity",
            "Industry, retail, services and construction: the monthly data that come before GDP.", 40),
]


def gdp_table(ctx, chart):
    """Latest q/q and y/y, then the last four quarters q/q, by expenditure component."""
    qq, yy = ctx.panel("gdp_comp_qoq"), ctx.panel("gdp_comp_yoy")
    if "B1GQ" not in qq:
        raise Missing("GDP q/q missing")
    gdp_last = builders.last_point(qq["B1GQ"])[0]
    quarters = [P.shift(gdp_last, -k) for k in (3, 2, 1, 0)]
    cols = [{"key": "qoq", "label": "q/q, latest", "format": "pct"},
            {"key": "yoy", "label": "y/y, latest", "format": "pct"}]
    cols += [{"key": f"q{i}", "label": builders.period_label(q), "format": "pct"} for i, q in enumerate(quarters)]
    rows = []
    for code, label in TABLE_ITEMS.items():
        if code not in qq:
            continue
        lp = builders.last_point(qq[code])
        if not lp:
            continue
        vals = {"qoq": lp[1], "yoy": builders.value_at(yy.get(code, []), lp[0])}
        for i, q in enumerate(quarters):
            vals[f"q{i}"] = builders.value_at(qq[code], q)
        lab = label if lp[0] == gdp_last else f"{label} ({builders.period_label(lp[0])})"
        rows.append({"label": lab, "values": vals, "flag": lp[2] or None, "period": lp[0]})
    return {"columns": cols, "rows": rows, "latest": {"period": gdp_last, "values": {}, "flag": None}}


def growth_heatmap(ctx, chart, last_n=12):
    """Rows: euro area, euro area ex Ireland, then members by latest growth. Columns: 12 quarters."""
    panel = ctx.panel("gdp_qoq_country")
    if "EA21" not in panel:
        raise Missing("EA21 GDP missing")
    cols = [p for p, v, _ in panel["EA21"] if v is not None][-last_n:]
    items = [("EA21", "Euro area", panel["EA21"])]
    try:
        items.append(("EA21_X_IE", "Euro area excluding Ireland", ctx.obs("gdp_qoq_ea_ex_ie")))
    except Missing:
        pass
    members = []
    for code in geo.EURO_AREA:
        if code in panel:
            d = {p: v for p, v, _ in panel[code]}
            last = next((d[c] for c in reversed(cols) if d.get(c) is not None), float("-inf"))
            members.append((last, code))
    members.sort(key=lambda x: -x[0])
    items += [(code, geo.name(code), panel[code]) for _, code in members]
    rows, cells, keys = [], [], []
    for ri, (code, label, obs) in enumerate(items):
        rows.append(label)
        keys.append(code)
        d = {p: v for p, v, _ in obs}
        for ci, c in enumerate(cols):
            if d.get(c) is not None:
                cells.append([ri, ci, d[c]])
    return {"rows": rows, "columns": cols, "cells": cells, "scale": "diverging", "midpoint": 0, "row_keys": keys}


def _monthly(cid, order, title, subtitle, mom, yoy, what, caveats, kicker="Monthly activity"):
    return Chart(cid, PAGE, "monthly", order, title, subtitle, kicker=kicker, type="bar-line",
                 series=[Ref(mom, "mom", "% change on previous month (seasonally adjusted)", "base", mark="bar"),
                         Ref(yoy, "yoy", "% change on a year earlier (calendar adjusted)", "story", mark="line")],
                 start="2015-01", default_window="5y",
                 notes="Eurostat publishes month-on-month changes only seasonally and calendar adjusted, and "
                       "year-on-year changes only calendar adjusted, so the bars and the line come from two "
                       "different adjustments of the same index.",
                 what=what,
                 transform_text="As published: m/m from the seasonally and calendar adjusted index (SCA, PCH_PRE); "
                                "y/y from the calendar adjusted index (CA, PCH_SM).",
                 caveats=caveats)


CHARTS = [
    Chart("gdp-growth", PAGE, "growth", 10,
          "Euro area GDP growth", "Real GDP, % change on the previous quarter (bars) and on a year earlier (line), "
          "seasonally and calendar adjusted",
          kicker="GDP", type="bar-line",
          series=[Ref("gdp_qoq", "qoq", "% change on previous quarter", "base", mark="bar"),
                  Ref("gdp_yoy", "yoy", "% change on a year earlier", "story", mark="line")],
          start="2010-Q1", default_window="10y",
          notes="The latest quarter is Eurostat's preliminary flash (about 30 days after the quarter) until the "
                "full release at about 65 days. 2020 swings run off the scale.",
          what="Quarterly growth of euro area real GDP (chain-linked volumes), fixed EA21 composition.",
          transform_text="As published by Eurostat (namq_10_gdp, units CLV_PCH_PRE and CLV_PCH_SM).",
          caveats="Ireland's GDP, driven by multinationals' accounting, can move the euro area figure by 0.1 to "
                  "0.2 points in a quarter; see the euro area excluding Ireland row in the country heatmap."),
    Chart("gdp-contributions", PAGE, "growth", 20,
          "What drove growth", "Contributions to euro area real GDP growth, percentage points, q/q",
          kicker="GDP", type="contrib", units="pp", format="pp", decimals=2, total_key="gdp",
          series=[Ref(f"gdp_contrib__{c}", c.lower(), lab, "base") for c, lab in COMPONENTS.items()]
                 + [Ref("gdp_qoq", "gdp", "GDP growth, % q/q", "story", decimals=1)],
          start="2019-Q1", default_window="5y",
          notes="Components are published with the full release (about 65 days after the quarter), so the latest "
                "flash quarter has GDP growth but no breakdown yet. Contributions can differ from GDP growth "
                "by rounding and the statistical discrepancy.",
          what="Eurostat's contributions of household and government consumption, investment, inventories and net "
               "exports to quarterly real GDP growth.",
          transform_text="As published (namq_10_gdp, unit CON_PPCH_PRE).",
          caveats="Inventories include the statistical discrepancy in several countries. Irish intellectual "
                  "property investment and its imports move investment and net exports in opposite directions."),
    Chart("gdp-table", PAGE, "growth", 30,
          "GDP by expenditure component", "Euro area, real, % change, seasonally and calendar adjusted",
          kicker="GDP", type="table", build=gdp_table, decimals=1, source="Eurostat (namq_10_gdp)",
          source_url=NAMQ,
          notes="A component whose latest quarter is earlier than GDP's shows that quarter in its label.",
          what="Latest quarter-on-quarter and year-on-year growth and the last four quarters, for GDP and its main "
               "expenditure components.",
          transform_text="As published (CLV_PCH_PRE and CLV_PCH_SM).",
          caveats="Exports and imports include trade between euro area members."),
    Chart("gdp-level", PAGE, "levels", 10,
          "Output against its pre-pandemic level", "Euro area real GDP, index 2019-Q4 = 100",
          kicker="GDP", units="index", format="index", decimals=1,
          series=[Ref("gdp_level__EA21", "EA21", "Euro area", "story", transform="rebase:2019-Q4"),
                  Ref("gdp_level_ea_ex_ie", "ex_ie", "Euro area excluding Ireland", "base", transform="rebase:2019-Q4")],
          start="2015-Q1", default_window="10y", reference_lines=[{"axis": "y", "value": 100, "label": "2019-Q4"}],
          original=True, source="Eurostat (namq_10_gdp)", source_url=NAMQ,
          build=lambda ctx, chart: (ctx.obs("gdp_level__IE"), {})[1],
          what="The level of euro area real GDP relative to the fourth quarter of 2019, with and without Ireland.",
          transform_text="Chain-linked volumes (2020 euros) rebased to 2019-Q4 = 100. Excluding Ireland: euro area "
                         "level minus the Irish level, then rebased.",
          caveats="Chain-linked levels are not strictly additive, so the excluding-Ireland line is an approximation."),
    Chart("gdp-level-countries", PAGE, "levels", 20,
          "Output in the largest economies", "Real GDP, index 2019-Q4 = 100",
          kicker="GDP", type="country-strip", units="index", format="index", decimals=1,
          series=[Ref(f"gdp_level__{c}", c, geo.name(c), "base", transform="rebase:2019-Q4") for c in geo.STRIP]
                 + [Ref("gdp_level__EA21", "EA21", "Euro area", "context", transform="rebase:2019-Q4")],
          start="2015-Q1", default_window="10y", reference_lines=[{"axis": "y", "value": 100, "label": "2019-Q4"}],
          notes="Poland is not in the euro area; its volumes are in 2020 euros at Eurostat's conversion.",
          what="Real GDP in Germany, France, Italy, Spain, the Netherlands and Poland relative to 2019-Q4.",
          transform_text="Chain-linked volumes rebased to 2019-Q4 = 100.",
          caveats="The latest quarter is a flash estimate for the countries that publish one; others end a "
                  "quarter earlier."),
    Chart("gdp-country-heatmap", PAGE, "countries", 10,
          "Growth across all euro area members", "Real GDP, % change on the previous quarter, last 12 quarters",
          kicker="GDP", type="heatmap", decimals=1, build=growth_heatmap, original=True,
          source="Eurostat (namq_10_gdp)", source_url=NAMQ,
          notes="The second row removes Ireland, whose GDP swings by several points a quarter on multinationals' "
                "accounting and can move the euro area aggregate on its own. Countries are sorted by the latest "
                "quarter; blank cells are not yet published.",
          what="Quarter-on-quarter real GDP growth in each of the 21 euro area members, the euro area and the euro "
               "area excluding Ireland.",
          transform_text="As published for countries and the euro area (CLV_PCH_PRE). Excluding Ireland: % change of "
                         "(EA21 level minus IE level), chain-linked 2020 euros.",
          caveats="The excluding-Ireland row is an approximation computed by the tracker (chain-linked levels are "
                  "not strictly additive)."),
    _monthly("industrial-production", 10, "Industrial production",
             "Euro area, industry excluding construction (B-D), volume",
             "ip_mom", "ip_yoy",
             "Monthly change in the volume of output of mining, manufacturing and energy supply.",
             "Irish pharmaceutical and contract manufacturing swing the euro area index from month to month."),
    _monthly("retail-sales", 20, "Retail sales volumes", "Euro area, retail trade except motor vehicles, volume",
             "retail_mom", "retail_yoy",
             "Monthly change in the deflated turnover of retail trade (NACE G47).",
             "Retail covers about a third of household consumption; it excludes cars, fuel stations are included."),
    _monthly("services-turnover", 30, "Services turnover",
             "Euro area, services except trade and finance (H-N excluding K), nominal turnover",
             "services_mom", "services_yoy",
             "Monthly change in the turnover of transport, accommodation, information, real estate, professional "
             "and support services.",
             "Turnover is in current prices: part of the growth is inflation. Eurostat publishes no euro area volume "
             "index for services. The latest month is often flagged i (see Eurostat metadata)."),
    _monthly("construction-output", 40, "Construction output", "Euro area, construction (F), volume",
             "construction_mom", "construction_yoy",
             "Monthly change in the volume of output of buildings and civil engineering.",
             "Construction is volatile and weather-dependent; the first estimate is often revised."),
    Chart("monthly-activity-table", PAGE, "monthly", 50,
          "Monthly activity at a glance", "Euro area, latest month, %",
          kicker="Monthly activity", type="table",
          build=builders.transform_table(
              columns=[("mom", "m/m (SCA)", "pct"), ("yoy", "y/y (CA)", "pct")],
              rows=[("Industrial production", {"mom": ("ip_mom", None), "yoy": ("ip_yoy", None)}),
                    ("Retail sales volume", {"mom": ("retail_mom", None), "yoy": ("retail_yoy", None)}),
                    ("Services turnover (nominal)", {"mom": ("services_mom", None), "yoy": ("services_yoy", None)}),
                    ("Construction output", {"mom": ("construction_mom", None), "yoy": ("construction_yoy", None)})],
              period_from="mom"),
          decimals=1, source="Eurostat (sts_inpr_m, sts_trtu_m, sts_setu_m, sts_copr_m)",
          source_url="https://ec.europa.eu/eurostat/web/short-term-business-statistics",
          what="Latest month-on-month and year-on-year change in the four monthly activity indicators.",
          transform_text="As published.",
          caveats="The four indicators are released on different days, so their latest months can differ."),
]
