"""Inflation page: euro area HICP, its components and contributions, the ECB's underlying measures,
countries, and inflation expectations.

Source choice (one source per series, CONTRACT section 2): published rates come from Eurostat
``prc_hicp_minr`` (ECOICOP v2); seasonally adjusted indices and the ECB's underlying measures come
from the ECB ``HICP`` flow (DSD ECB_ICP3; provider 4F0 = ECB-computed).
"""
from .. import builders
from .. import periods as P
from .. import geo
from ..spec import Chart, Derived, Ref, Section, Series

PAGE = "inflation"
TARGET = [{"axis": "y", "value": 2, "label": "ECB target"}]

HICP_URL = "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table"


def _minr(sid, coicop, label, start="1997-01"):
    return Series(sid, "eurostat", dataset="prc_hicp_minr",
                  filters={"geo": "EA21", "unit": "RCH_A", "coicop18": coicop}, freq="M", unit="%",
                  label=label, start=start)


def _ecb_hicp(sid, key, label, unit="%", decimals=1, start="1997-01"):
    return Series(sid, "ecb", dataset="HICP", key=key, freq="M", unit=unit, label=label, decimals=decimals,
                  start=start)


COMPONENT_LABELS = {"NRG": "Energy", "FOOD": "Food, alcohol and tobacco",
                    "IGD_NNRG": "Non-energy industrial goods", "SERV": "Services"}
COUNTRY_CODES = ["EA21"] + geo.EURO_AREA + ["PL"]

SERIES = [
    _minr("hicp_headline", "TOTAL", "Headline"),
    _minr("hicp_core", "TOT_X_NRG_FOOD", "Core (ex energy, food, alcohol, tobacco)"),
    Series("hicp_components", "eurostat", dataset="prc_hicp_minr",
           filters={"geo": "EA21", "unit": "RCH_A", "coicop18": list(COMPONENT_LABELS)}, split="coicop18",
           labels=COMPONENT_LABELS, freq="M", start="1997-01", label="HICP components, % y/y"),
    Series("hicp_country", "eurostat", dataset="prc_hicp_minr",
           filters={"unit": "RCH_A", "coicop18": "TOTAL", "geo": COUNTRY_CODES}, split="geo",
           freq="M", start="2015-01", label="HICP by country, % y/y"),
    Series("hicp_contrib", "eurostat", dataset="prc_hicp_ctr",
           filters={"geo": "EA", "unit": "PC_PNT", "coicop18": list(COMPONENT_LABELS)}, split="coicop18",
           labels=COMPONENT_LABELS, freq="M", unit="pp", start="2015-01",
           label="Contributions to euro area annual inflation"),
    Series("hicp_release", "eurostat", dataset="prc_hicp_fpd",
           filters={"geo": "EA21", "unit": "RCH_A", "coicop18": "TOTAL", "release": ["FLS", "FIN"]},
           split="release", labels={"FLS": "Flash", "FIN": "Final"}, freq="M", start="2024-01",
           label="HICP headline, first release"),
    Series("hicp_ct", "eurostat", dataset="prc_hicp_ct",
           filters={"geo": "EA21", "unit": "RCH_A", "coicop18": "TOTAL"}, freq="M", start="2003-01",
           label="HICP at constant tax rates"),
    Series("ec_price_expectations", "eurostat", dataset="ei_bsco_m",
           filters={"geo": "EA21", "indic": "BS-PT-NY", "s_adj": "SA", "unit": "BAL"}, freq="M",
           unit="balance", label="Consumers' expected price trends, next 12 months", start="1990-01"),
    # ECB HICP flow: seasonally adjusted indices (for 1-, 3- and 6-month annualised rates)
    _ecb_hicp("hicp_sa_headline", "M.U2.Y.000000.4F0.INX", "Headline, SA index", unit="index", decimals=2),
    _ecb_hicp("hicp_sa_core", "M.U2.Y.XEF000.4F0.INX", "Core, SA index", unit="index", decimals=2),
    _ecb_hicp("hicp_sa_services", "M.U2.Y.SERV00.4F0.INX", "Services, SA index", unit="index", decimals=2),
    # ECB underlying inflation measures
    _ecb_hicp("hicp_supercore", "M.U2.N.SPRXEF.4F0.ANR", "Supercore"),
    _ecb_hicp("hicp_pcci", "M.U2.N.PCCI00.4F0.3MM", "PCCI (persistent and common component)", decimals=1),
    _ecb_hicp("hicp_pcci_xe", "M.U2.N.PCCIXE.4F0.3MM", "PCCI excluding energy", decimals=1),
    _ecb_hicp("hicp_trim10", "M.U2.N.TRIM10.4F0.ANR", "Trimmed mean (10%)"),
    _ecb_hicp("hicp_trim30", "M.U2.N.TRIM30.4F0.ANR", "Trimmed mean (30%)"),
    _ecb_hicp("hicp_wmedian", "M.U2.N.WGTMED.4F0.ANR", "Weighted median"),
    _ecb_hicp("hicp_domestic_index", "M.U2.N.DOM000.4F0.INX", "Domestic inflation, index", unit="index",
              decimals=2),
    # Expectations
    Series("spf_hicp_1y", "ecb", dataset="SPF", key="M.U2.HICP.POINT.P12M.Q.AVG", freq="M",
           label="SPF, one year ahead (by target month)"),
    Series("spf_hicp_2y", "ecb", dataset="SPF", key="M.U2.HICP.POINT.P24M.Q.AVG", freq="M",
           label="SPF, two years ahead (by target month)"),
    Series("spf_hicp_5y", "ecb", dataset="SPF", key="Q.U2.HICP.POINT.LT.Q.AVG", freq="Q",
           label="Five years ahead"),
    Series("ces_infl_12m", "ecb", dataset="CES", key="M.Z18.ALL.T.C1120.NUM_VAR.WM", freq="M",
           label="12 months ahead"),
    Series("ces_infl_3y", "ecb", dataset="CES", key="M.Z18.ALL.T.C1220.NUM_VAR.WM", freq="M",
           label="3 years ahead"),
    Series("ces_infl_5y", "ecb", dataset="CES", key="M.Z18.ALL.T.E2020.NUM_VAR.WM", freq="M",
           label="5 years ahead"),
]


def spf_to_round(months):
    """SPF rolling-horizon series are indexed by target month (reference month + horizon).

    Map each point back to its survey round: reference month = target - horizon; the round is the
    quarter of the first survey month (January, April, July, October) after the reference month
    (Sep 2026 reference -> October survey -> 2026-Q4; Feb 2019 -> April -> 2019-Q2). If two
    points map to one quarter the later one wins.
    """
    def fn(obs):
        out = {}
        for p, v, f in obs:
            m = P.shift(P.shift(p, -months), 1)
            while int(m[5:7]) not in (1, 4, 7, 10):
                m = P.shift(m, 1)
            q = P.to_freq(m, "Q")
            out[q] = (q, v, f)
        return [out[k] for k in sorted(out)]
    fn.__name__ = f"spf_to_round_{months}"
    return fn


def yoy_of(obs):
    from ..transforms import yoy
    return yoy(obs)


DERIVED = [
    Derived("spf_hicp_1y_round", ["spf_hicp_1y"], spf_to_round(12), freq="Q", label="One year ahead"),
    Derived("spf_hicp_2y_round", ["spf_hicp_2y"], spf_to_round(24), freq="Q", label="Two years ahead"),
    Derived("hicp_domestic", ["hicp_domestic_index"], yoy_of, freq="M", label="Domestic inflation"),
]

SECTIONS = [
    Section(PAGE, "headline", "Headline and core",
            "Headline inflation is the ECB's target measure; core leaves out energy, food, alcohol and tobacco.", 10),
    Section(PAGE, "components", "What is driving it",
            "Energy, food, goods and services, and how much each adds to the headline rate.", 20),
    Section(PAGE, "underlying", "Underlying inflation",
            "The ECB's own gauges of the trend once one-off price swings are stripped out.", 30),
    Section(PAGE, "countries", "Across the euro area",
            "The common currency hides large gaps between member states.", 40),
    Section(PAGE, "expectations", "Inflation expectations",
            "What professional forecasters and households expect inflation to be.", 50),
]


def flash_final(ctx, chart, months=6):
    flash = ctx.obs("hicp_release__FLS")
    final = {p: v for p, v, _ in ctx.obs("hicp_release__FIN")}
    rows = []
    for p, v, f in flash[-months:][::-1]:
        fin = final.get(p)
        rows.append({"label": P.start_date(p).strftime("%B %Y"),
                     "values": {"flash": v, "final": fin, "revision": None if fin is None else fin - v},
                     "flag": None if fin is not None else "flash only", "period": p})
    return {"columns": [{"key": "flash", "label": "Flash", "format": "pct"},
                        {"key": "final", "label": "Final", "format": "pct"},
                        {"key": "revision", "label": "Revision", "format": "change"}],
            "rows": rows, "latest": {"period": flash[-1][0], "values": {}, "flag": None}}


BANK_ROWS = [
    ("Headline", {"m1": ("hicp_sa_headline", "ann:1"), "m3": ("hicp_sa_headline", "ann3m"),
                  "m6": ("hicp_sa_headline", "ann6m"), "m12": ("hicp_headline", None)}),
    ("Core (HICPX)", {"m1": ("hicp_sa_core", "ann:1"), "m3": ("hicp_sa_core", "ann3m"),
                      "m6": ("hicp_sa_core", "ann6m"), "m12": ("hicp_core", None)}),
    ("Services", {"m1": ("hicp_sa_services", "ann:1"), "m3": ("hicp_sa_services", "ann3m"),
                  "m6": ("hicp_sa_services", "ann6m"), "m12": ("hicp_components__SERV", None)}),
    ("Supercore", {"m12": ("hicp_supercore", None)}),
    ("PCCI", {"m12": ("hicp_pcci", None)}),
    ("PCCI excluding energy", {"m12": ("hicp_pcci_xe", None)}),
    ("Trimmed mean (10%)", {"m12": ("hicp_trim10", None)}),
    ("Trimmed mean (30%)", {"m12": ("hicp_trim30", None)}),
    ("Weighted median", {"m12": ("hicp_wmedian", None)}),
    ("Domestic inflation", {"m12": ("hicp_domestic", None)}),
]

ECB_HICP_URL = "https://data.ecb.europa.eu/data/datasets/HICP"

CHARTS = [
    Chart("hicp-headline-core", PAGE, "headline", 10,
          "Headline and core inflation", "Euro area HICP, % change on a year earlier",
          kicker="Consumer prices",
          series=[Ref("hicp_headline", "headline", "Headline", "base"),
                  Ref("hicp_core", "core", "Core (ex energy, food, alcohol, tobacco)", "story")],
          reference_lines=TARGET, default_window="5y",
          notes="The latest month is Eurostat's flash estimate (flag e) until the final release.",
          what="Annual rate of change of the euro area HICP and of the HICP excluding energy, food, alcohol "
               "and tobacco, as published by Eurostat.",
          caveats="HICP excludes owner-occupied housing costs. Since January 2026 the index follows ECOICOP "
                  "version 2 (prc_hicp_minr); the euro area series is the fixed EA21 composition."),
    Chart("hicp-3m-annualised", PAGE, "headline", 20,
          "Recent momentum in prices", "Euro area HICP, 3-month change at an annual rate, seasonally adjusted, %",
          kicker="Consumer prices",
          decimals=1,
          series=[Ref("hicp_sa_headline", "headline", "Headline", "base", transform="ann3m", start="2010-01"),
                  Ref("hicp_sa_core", "core", "Core", "story", transform="ann3m", start="2010-01"),
                  Ref("hicp_sa_services", "services", "Services", "context", transform="ann3m", start="2010-01")],
          reference_lines=TARGET, default_window="5y", original=True,
          what="Change over the latest three months in the ECB's seasonally adjusted HICP indices, compounded to "
               "an annual rate.",
          transform_text="((index_t / index_{t-3}) ^ 4 - 1) x 100 on the seasonally adjusted index (ECB HICP "
                         "flow, adjustment Y, provider 4F0).",
          caveats="Seasonal adjustment is the ECB's; short-horizon rates are volatile and are revised when the "
                  "seasonal factors are re-estimated."),
    Chart("hicp-bank", PAGE, "headline", 30,
          "Inflation at different horizons", "Euro area, % change at an annual rate (12m: on a year earlier)",
          kicker="Consumer prices", type="table",
          build=builders.transform_table(
              columns=[("m1", "1m ann.", "pct"), ("m3", "3m ann.", "pct"),
                       ("m6", "6m ann.", "pct"), ("m12", "12m", "pct")],
              rows=BANK_ROWS, period_from="m12"),
          source="Eurostat (prc_hicp_minr); ECB (HICP)", source_url=ECB_HICP_URL, original=True,
          notes="1-, 3- and 6-month rates use the ECB's seasonally adjusted indices; the 12-month rate is the "
                "published rate. The ECB's underlying measures are only published as 12-month rates and "
                "usually a month after the flash.",
          what="Headline, core and services inflation over 1, 3, 6 and 12 months, and the ECB's underlying "
               "inflation measures.",
          transform_text="n-month annualised: ((SA index_t / SA index_{t-n}) ^ (12 / n) - 1) x 100. Domestic "
                         "inflation: 12-month change of the ECB's domestic inflation index."),
    Chart("hicp-flash-final", PAGE, "headline", 40,
          "Flash estimate and final release", "Euro area HICP, % change on a year earlier",
          kicker="Consumer prices", type="table", build=flash_final, decimals=1,
          what="Eurostat's flash estimate of headline inflation next to the final figure published about two "
               "weeks later.",
          caveats="The flash estimate is published on the last working day of the month or the first of the "
                  "next; the final release follows mid-month."),
    Chart("hicp-components", PAGE, "components", 10,
          "Inflation by main component", "Euro area HICP, % change on a year earlier",
          kicker="Consumer prices",
          series=[Ref("hicp_components__SERV", "services", "Services", "story"),
                  Ref("hicp_components__IGD_NNRG", "goods", "Non-energy industrial goods", "base"),
                  Ref("hicp_components__FOOD", "food", "Food, alcohol and tobacco", "context"),
                  Ref("hicp_components__NRG", "energy", "Energy", "context")],
          reference_lines=TARGET, default_window="5y",
          what="Annual inflation in the four main HICP aggregates."),
    Chart("hicp-contributions", PAGE, "components", 20,
          "What adds up to headline inflation",
          "Contributions to euro area annual HICP inflation, percentage points",
          kicker="Consumer prices", type="contrib", units="pp", format="pp", total_key="headline",
          series=[Ref("hicp_contrib__NRG", "energy", "Energy", "base"),
                  Ref("hicp_contrib__FOOD", "food", "Food, alcohol and tobacco", "base"),
                  Ref("hicp_contrib__IGD_NNRG", "goods", "Non-energy industrial goods", "base"),
                  Ref("hicp_contrib__SERV", "services", "Services", "base"),
                  Ref("hicp_headline", "headline", "Headline inflation, %", "story")],
          start="2019-01", default_window="5y",
          notes="Contributions are Eurostat's (euro area, changing composition); they can differ from the "
                "headline rate by rounding.",
          what="Eurostat's contributions of energy, food, non-energy industrial goods and services to annual "
               "euro area inflation, with the headline rate.",
          caveats="Published with the final HICP, so the latest flash month has no contributions yet."),
    Chart("hicp-constant-tax", PAGE, "components", 30,
          "Inflation with and without tax changes",
          "Euro area HICP and HICP at constant tax rates, % change on a year earlier",
          kicker="Consumer prices",
          series=[Ref("hicp_headline", "headline", "HICP", "base", start="2003-01"),
                  Ref("hicp_ct", "constant_tax", "HICP at constant tax rates", "story")],
          reference_lines=TARGET, default_window="5y",
          what="The HICP recomputed with tax rates held constant, which shows how much VAT and excise changes "
               "move the headline rate.",
          caveats="Constant-tax data are published with the final HICP only."),
    Chart("ecb-underlying", PAGE, "underlying", 10,
          "The ECB's measures of underlying inflation", "Euro area, % change on a year earlier",
          kicker="Underlying inflation",
          series=[Ref("hicp_core", "core", "Core (HICPX)", "base"),
                  Ref("hicp_supercore", "supercore", "Supercore", "story"),
                  Ref("hicp_pcci", "pcci", "PCCI", "context"),
                  Ref("hicp_trim10", "trim10", "Trimmed mean (10%)", "context"),
                  Ref("hicp_wmedian", "median", "Weighted median", "context"),
                  Ref("hicp_domestic", "domestic", "Domestic inflation", "context")],
          start="2015-01", reference_lines=TARGET, default_window="5y",
          notes="Supercore keeps the HICPX items most sensitive to economic slack. PCCI is the persistent and "
                "common component (three-month average of the annual rate). Domestic inflation covers items "
                "with a low import content.",
          what="The underlying inflation measures the ECB computes from the HICP.",
          transform_text="As published by the ECB, except domestic inflation: 12-month change of the ECB index.",
          caveats="These measures are published about two weeks after the flash HICP and only for the euro area."),
    Chart("hicp-countries", PAGE, "countries", 10,
          "Inflation in the largest economies", "HICP, % change on a year earlier",
          kicker="Consumer prices", type="country-strip",
          series=[Ref(f"hicp_country__{c}", c, geo.name(c), "base") for c in geo.STRIP]
                 + [Ref("hicp_country__EA21", "EA21", "Euro area", "context")],
          start="2019-01", reference_lines=TARGET, default_window="5y",
          notes="Poland is not in the euro area; its HICP is shown for comparison.",
          what="Annual HICP inflation in Germany, France, Italy, Spain, the Netherlands and Poland, with the euro "
               "area."),
    Chart("hicp-country-heatmap", PAGE, "countries", 20,
          "Inflation across all euro area members", "HICP, % change on a year earlier, last 24 months",
          kicker="Consumer prices", type="heatmap", decimals=1,
          build=builders.heatmap(["hicp_country__EA21"] + [f"hicp_country__{c}" for c in geo.EURO_AREA],
                                 last_n=24, scale="diverging", midpoint=2, pin_first="EA21"),
          notes="Rows are sorted by the latest month, euro area first. The colour scale is centred on 2%.",
          what="Annual HICP inflation in each of the 21 euro area member states, month by month."),
    Chart("inflation-expectations-spf", PAGE, "expectations", 10,
          "What professional forecasters expect",
          "ECB Survey of Professional Forecasters, mean expected HICP inflation, %",
          kicker="Inflation expectations", frequency="Q",
          series=[Ref("spf_hicp_1y_round", "1y", "One year ahead", "base"),
                  Ref("spf_hicp_2y_round", "2y", "Two years ahead", "context"),
                  Ref("spf_hicp_5y", "5y", "Five years ahead", "story")],
          reference_lines=TARGET, default_window="10y",
          notes="Plotted at the survey round. One and two years ahead are rolling horizons measured from the "
                "latest HICP month known at the time of the survey.",
          what="Mean point forecasts of euro area HICP inflation in the ECB's quarterly Survey of Professional "
               "Forecasters.",
          transform_text="Rolling-horizon series are re-indexed from target month to survey round: target "
                         "month minus the horizon gives the reference month; the round is the next January, "
                         "April, July or October survey.",
          original=False),
    Chart("inflation-expectations-consumers", PAGE, "expectations", 20,
          "What households expect", "ECB Consumer Expectations Survey, median expected inflation, %",
          kicker="Inflation expectations",
          series=[Ref("ces_infl_12m", "12m", "12 months ahead", "story"),
                  Ref("ces_infl_3y", "3y", "3 years ahead", "base"),
                  Ref("ces_infl_5y", "5y", "5 years ahead", "context")],
          reference_lines=TARGET, default_window="max",
          what="Median of households' quantitative inflation expectations in the ECB Consumer Expectations "
               "Survey, euro area aggregate of the 11 survey countries.",
          caveats="Households' expectations sit well above measured inflation on average; watch the direction "
                  "rather than the level."),
    Chart("consumer-price-expectations", PAGE, "expectations", 30,
          "Consumers' view of prices over the next year",
          "European Commission consumer survey, expected price trends over the next 12 months, balance",
          kicker="Inflation expectations", units="balance", format="level",
          series=[Ref("ec_price_expectations", "balance", "Price expectations", "story", start="2000-01")],
          default_window="10y",
          what="Balance of consumers expecting prices to rise faster minus those expecting them to rise slower "
               "or fall, seasonally adjusted.",
          caveats="A qualitative balance, not a rate of inflation."),
]
