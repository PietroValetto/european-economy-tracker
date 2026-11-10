"""International page: the euro area next to the United States, the United Kingdom, Japan and
China; the euro area's current account and goods trade; current accounts by member state.

Sources (one per series; a chart may combine sources, each line from one):

* euro area lines come from Eurostat (GDP ``namq_10_gdp``, HICP ``prc_hicp_minr``, unemployment
  ``une_rt_m``), because the OECD's euro area CPI stops at 2025-12;
* other economies: OECD (quarterly national accounts, harmonised unemployment, long-term yields)
  and BIS (central bank policy rates, consumer prices, exchange rates against the US dollar);
* the euro area current account is Eurostat ``ei_bpm6ca_m`` (extra-euro area, monthly, not
  seasonally adjusted, so it is shown as a 12-month sum; the ECB BOP flow was blocked in the
  research); current accounts by country are ``bop_gdp6_q`` (% of GDP, the same BoP data as
  ``bop_c6_q`` expressed as a share of GDP; ``bop_c6_q`` has no euro area aggregate and returns
  413 unfiltered); goods trade is the euro indicator ``ei_etea_m``.
"""
from .. import builders
from .. import periods as P
from .. import transforms
from ..context import Missing
from ..spec import Chart, Derived, Ref, Section, Series
from .fiscal import COUNTRIES, EA_MEMBERS, country_bars, period_text

PAGE = "international"

OECD_LABELS = {"USA": "United States", "GBR": "United Kingdom", "JPN": "Japan", "CHN": "China"}
CA_CODES = EA_MEMBERS + ["PL"]  # bop_gdp6_q has the euro area only against non-members (EXT_EA21)
BIS_LABELS = {"US": "United States", "GB": "United Kingdom", "JP": "Japan", "CN": "China", "XM": "Euro area"}

SERIES = [
    # euro area (Eurostat): GDP y/y for every member state, so the Europe page can reuse it
    Series("glance_gdp_yoy", "eurostat", dataset="namq_10_gdp",
           filters={"na_item": "B1GQ", "unit": "CLV_PCH_SM", "s_adj": "SCA", "geo": COUNTRIES}, split="geo",
           freq="Q", unit="% y/y", label="Real GDP, % change on a year earlier", start="1996-Q1"),
    Series("intl_ea_gdp_level", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "na_item": "B1GQ", "unit": "CLV20_MEUR", "s_adj": "SCA"}, freq="Q",
           unit="EUR mn, 2020 prices", label="Real GDP, euro area", start="2015-Q1"),
    # OECD
    Series("oecd_gdp_yoy", "oecd", dataset="OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,",
           key="Q.Y.USA+GBR+JPN+CHN.S1.S1.B1GQ._Z._Z._Z.PC.L.GY.T0102", split="REF_AREA", labels=OECD_LABELS,
           freq="Q", unit="% y/y", label="Real GDP, % change on a year earlier", start="2000-Q1",
           source_name="OECD (quarterly national accounts)"),
    Series("oecd_gdp_level", "oecd", dataset="OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,",
           key="Q.Y.USA+GBR+JPN.S1.S1.B1GQ._Z._Z._Z.XDC.LR.LA.T0102", split="REF_AREA", labels=OECD_LABELS,
           freq="Q", unit="national currency, constant prices", label="Real GDP", start="2015-Q1",
           source_name="OECD (quarterly national accounts)"),
    Series("oecd_unemployment", "oecd", dataset="OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,",
           key="USA+GBR+JPN.UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M", split="REF_AREA", labels=OECD_LABELS,
           freq="M", unit="%", label="Harmonised unemployment rate", start="2000-01",
           source_name="OECD (harmonised unemployment rates)"),
    Series("oecd_y10", "oecd", dataset="OECD.SDD.STES,DSD_STES@DF_FINMARK,",
           key="USA+GBR+JPN+CHN.M.IRLT.PA._Z._Z._Z._Z.N", split="REF_AREA", labels=OECD_LABELS,
           freq="M", unit="%", decimals=2, label="Long-term government bond yield (10 years)", start="2000-01",
           source_name="OECD (financial indicators)"),
    # the euro area 10-year yield from the OECD (its euro area code is EA20): one month fresher than
    # Eurostat's EMU convergence series (irt_lt_mcby_m, used on the Europe page), and the same source as
    # the other economies' yields on this page
    Series("oecd_y10_ea", "oecd", dataset="OECD.SDD.STES,DSD_STES@DF_FINMARK,",
           key="EA20.M.IRLT.PA._Z._Z._Z._Z.N", freq="M", unit="%", decimals=2,
           label="Euro area long-term government bond yield (10 years)", start="2000-01",
           source_name="OECD (financial indicators)"),
    # BIS
    Series("bis_policy_rate", "bis", dataset="WS_CBPOL", key="M.US+XM+GB+JP+CN", split="REF_AREA",
           labels=BIS_LABELS, freq="M", unit="%", decimals=2, label="Central bank policy rate, end of month",
           start="2000-01"),
    Series("bis_cpi", "bis", dataset="WS_LONG_CPI", key="M.US+GB+JP+CN.771", split="REF_AREA", labels=BIS_LABELS,
           freq="M", unit="% y/y", label="Consumer prices, % change on a year earlier", start="2000-01"),
    Series("bis_usd", "bis", dataset="WS_XRU", key="M.XM+GB+JP+CN..A", split="REF_AREA", labels=BIS_LABELS,
           freq="M", unit="national currency per US dollar", decimals=4,
           label="Exchange rate against the US dollar, monthly average", start="2015-01"),
    # Eurostat external accounts
    Series("intl_ea_ca", "eurostat", dataset="ei_bpm6ca_m",
           filters={"geo": "EA21", "currency": "MIO_EUR", "sector10": "S1", "sectpart": "S1", "stk_flow": "BAL",
                    "partner": "EXT_EA21", "s_adj": "NSA", "bop_item": ["CA", "G", "S", "IN1", "IN2"]},
           split="bop_item", labels={"CA": "Current account", "G": "Goods", "S": "Services",
                                     "IN1": "Primary income", "IN2": "Secondary income"},
           freq="M", unit="EUR mn", label="Euro area current account (extra-euro area), monthly", start="1999-01"),
    Series("intl_ca_gdp", "eurostat", dataset="bop_gdp6_q",
           filters={"freq": "Q", "unit": "PC_GDP", "s_adj": "NSA", "bop_item": "CA", "stk_flow": "BAL",
                    "partner": "WRL_REST", "geo": CA_CODES}, split="geo",
           freq="Q", unit="% of GDP", label="Current account balance, % of GDP", start="2010-Q1"),
    Series("intl_ea_trade", "eurostat", dataset="ei_etea_m",
           filters={"geo": "EA21", "partner": "EXT_EA21", "indic": "ET-T", "unit": "MIO-EUR-SA",
                    "stk_flow": ["BAL_RT", "EXP", "IMP"]}, split="stk_flow",
           labels={"BAL_RT": "Trade balance", "EXP": "Exports", "IMP": "Imports"}, freq="M", unit="EUR bn",
           scale=0.001, label="Euro area trade in goods with the rest of the world, seasonally adjusted",
           start="2002-01"),
]


def sum12(obs):
    """Rolling 12-month sum, EUR millions to EUR billions. A month gets a value only when all 12
    calendar months up to it are present."""
    vals = {p: v for p, v, _ in obs}
    out = []
    for p, v, f in obs:
        win = [vals.get(P.shift(p, -k)) for k in range(12)]
        if all(w is not None for w in win):
            out.append((p, sum(win) / 1000.0, f))
    return out


def usd_index(obs):
    """National currency per US dollar -> US dollars per unit of national currency, 2019 = 100.

    A rise means the currency strengthened against the dollar."""
    inv = [(p, (1.0 / v) if v else None, f) for p, v, f in obs]
    return transforms.rebase(inv, "2019")


REAL_RATE = [("EA", "bis_policy_rate__XM", "hicp_headline", "ECB"),
             ("US", "bis_policy_rate__US", "bis_cpi__US", "Federal Reserve"),
             ("UK", "bis_policy_rate__GB", "bis_cpi__GB", "Bank of England"),
             ("JP", "bis_policy_rate__JP", "bis_cpi__JP", "Bank of Japan")]

DERIVED = [
    Derived(f"intl_real_rate_{key.lower()}", [rate, cpi], transforms.spread, freq="M", unit="%", decimals=1,
            label=name)
    for key, rate, cpi, name in REAL_RATE
] + [
    Derived(f"intl_ca12_{c.lower()}", [f"intl_ea_ca__{c}"], sum12, freq="M", unit="EUR bn", decimals=0,
            label=lab)
    for c, lab in (("CA", "Current account"), ("G", "Goods"), ("S", "Services"), ("IN1", "Primary income"),
                   ("IN2", "Secondary income"))
]

SECTIONS = [
    Section(PAGE, "overview", "At a glance", "The latest headline numbers for the largest economies.", 5),
    Section(PAGE, "growth", "Growth", "Real GDP in the euro area and the other large economies.", 10),
    Section(PAGE, "prices-jobs", "Inflation and jobs", "Consumer prices and unemployment, economy by economy.", 20),
    Section(PAGE, "rates-fx", "Interest rates and currencies",
            "Policy rates, long-term yields and exchange rates against the dollar.", 30),
    Section(PAGE, "external", "Trade with the world",
            "The euro area's current account and goods trade, and the current accounts of its members.", 40),
]

OVERVIEW = [
    # column key, label, format, decimals, {economy: series id}
    ("gdp", "GDP, % y/y", "pct", 1, {"EA": "glance_gdp_yoy__EA21", "US": "oecd_gdp_yoy__USA",
                                     "UK": "oecd_gdp_yoy__GBR", "JP": "oecd_gdp_yoy__JPN",
                                     "CN": "oecd_gdp_yoy__CHN"}),
    ("cpi", "Inflation, % y/y", "pct", 1, {"EA": "hicp_headline", "US": "bis_cpi__US", "UK": "bis_cpi__GB",
                                           "JP": "bis_cpi__JP", "CN": "bis_cpi__CN"}),
    ("unemp", "Unemployment, %", "pct", 1, {"EA": "unemployment_rate", "US": "oecd_unemployment__USA",
                                            "UK": "oecd_unemployment__GBR", "JP": "oecd_unemployment__JPN"}),
    ("policy", "Policy rate, %", "pct", 2, {"EA": "bis_policy_rate__XM", "US": "bis_policy_rate__US",
                                            "UK": "bis_policy_rate__GB", "JP": "bis_policy_rate__JP",
                                            "CN": "bis_policy_rate__CN"}),
    ("y10", "10-year yield, %", "pct", 2, {"EA": "oecd_y10_ea", "US": "oecd_y10__USA", "UK": "oecd_y10__GBR",
                                           "JP": "oecd_y10__JPN", "CN": "oecd_y10__CHN"}),
]
ECONOMIES = [("EA", "Euro area"), ("US", "United States"), ("UK", "United Kingdom"), ("JP", "Japan"),
             ("CN", "China")]
SHORT = {"EA": "euro area", "US": "US", "UK": "UK", "JP": "Japan", "CN": "China"}


def overview_table(ctx, chart):
    """One row per headline indicator, one column per economy, then two text columns: the period
    most economies are on (any economy on another period in brackets) and how old that period is
    at build time."""
    import datetime
    today = datetime.date.fromisoformat(ctx.today)
    cols = [{"key": code, "label": name, "format": "pct"} for code, name in ECONOMIES]
    cols += [{"key": "period", "label": "Latest period", "format": "text"},
             {"key": "lag", "label": "Age at this update", "format": "text"}]
    rows, periods = [], []
    for key, label, fmt, dec, ids in OVERVIEW:
        latest = {}
        for econ, sid in ids.items():
            try:
                lp = builders.last_point(ctx.obs(sid))
            except Missing:
                lp = None
            if lp:
                latest[econ] = lp
        if not latest:
            continue
        # the period most economies are on (ties: the newest); the others are named in brackets
        counts = {}
        for lp in latest.values():
            counts[lp[0]] = counts.get(lp[0], 0) + 1
        ref = max(counts, key=lambda p: (counts[p], P.compare_key(p)))
        periods.append(max((lp[0] for lp in latest.values()), key=P.compare_key))
        older = [f"{SHORT[e]} {period_text(lp[0])}" for e, lp in latest.items() if lp[0] != ref]
        vals = {econ: (latest[econ][1] if econ in latest else None) for econ, _ in ECONOMIES}
        vals["period"] = period_text(ref) + (f" ({'; '.join(older)})" if older else "")
        vals["lag"] = f"{(today - P.end_date(ref)).days} days"
        rows.append({"label": label, "values": vals, "flag": None, "decimals": dec})
    if not rows:
        raise Missing("overview has no data")
    # drop an economy with no value in any row (no empty column)
    used = [c for c in cols if c["format"] == "text" or any(r["values"].get(c["key"]) is not None for r in rows)]
    keys = {c["key"] for c in used}
    for r in rows:
        r["values"] = {k: v for k, v in r["values"].items() if k in keys}
    return {"columns": used, "rows": rows,
            "latest": {"period": max(periods, key=P.compare_key), "values": {}, "flag": None}}


def _econ(sids, story="EA"):
    """Refs for EA / US / UK / JP / CN lines: the euro area is the story, the US the base."""
    refs = []
    for key, sid in sids:
        role = "story" if key == story else ("base" if key == "US" else "context")
        refs.append(Ref(sid, key, dict(ECONOMIES)[key], role))
    return refs


CHARTS = [
    Chart("intl-overview", PAGE, "overview", 10,
          "The large economies at a glance", "Latest readings",
          kicker="International", type="table", units="", decimals=1, build=overview_table,
          source="Eurostat; OECD; BIS", source_url="https://data-explorer.oecd.org/",
          notes="Euro area: Eurostat GDP, HICP and unemployment; OECD 10-year yield; BIS policy rate (ECB deposit "
                "facility rate). Other economies: OECD GDP, unemployment and yields; BIS consumer prices and "
                "policy rates. China has no harmonised unemployment rate.",
          what="Real GDP growth on a year earlier, consumer price inflation, the unemployment rate, the central bank "
               "policy rate and the 10-year government bond yield in the euro area, the US, the UK, Japan and "
               "China.",
          transform_text="Latest published value of each series. 'Latest period' is the period most economies have "
                         "published for that indicator, with any economy on another period in brackets; 'Age at this "
                         "update' counts the days from the end of that period to this build.",
          caveats="National definitions differ: inflation is the HICP for the euro area and national CPIs "
                  "elsewhere; China's GDP and CPI are official figures with a different methodology."),
    Chart("intl-gdp-growth", PAGE, "growth", 10,
          "Growth in the large economies", "Real GDP, % change on a year earlier",
          kicker="Growth", decimals=1, frequency="Q",
          series=_econ([("EA", "glance_gdp_yoy__EA21"), ("US", "oecd_gdp_yoy__USA"), ("UK", "oecd_gdp_yoy__GBR"),
                        ("JP", "oecd_gdp_yoy__JPN"), ("CN", "oecd_gdp_yoy__CHN")]),
          start="2015-Q1", reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="5y",
          what="Year-on-year growth of real GDP, seasonally adjusted, euro area (Eurostat, EA21) and the US, UK, "
               "Japan and China (OECD).",
          caveats="The euro area flash for the latest quarter can be revised; China's GDP is the official "
                  "figure."),
    Chart("intl-gdp-level", PAGE, "growth", 20,
          "The transatlantic gap", "Real GDP, index, fourth quarter of 2019 = 100",
          kicker="Growth", units="index", format="index", decimals=1, frequency="Q",
          series=[Ref("intl_ea_gdp_level", "EA", "Euro area", "story", transform="rebase:2019-Q4", start="2018-Q1"),
                  Ref("oecd_gdp_level__USA", "US", "United States", "base", transform="rebase:2019-Q4",
                      start="2018-Q1"),
                  Ref("oecd_gdp_level__GBR", "UK", "United Kingdom", "context", transform="rebase:2019-Q4",
                      start="2018-Q1"),
                  Ref("oecd_gdp_level__JPN", "JP", "Japan", "context", transform="rebase:2019-Q4",
                      start="2018-Q1")],
          reference_lines=[{"axis": "y", "value": 100, "label": "Q4 2019"}], default_window="max", original=True,
          what="Real GDP of the euro area and the US (and the UK and Japan), each indexed to its own level in the "
               "last quarter before the pandemic.",
          transform_text="Chain-linked volumes (Eurostat CLV20_MEUR for the euro area; OECD national-currency "
                         "constant-price levels for the others) divided by their 2019-Q4 value, times 100.",
          caveats="Measures growth since 2019, not living standards: population grew faster in the US, so the gap "
                  "per person is smaller than this chart suggests."),
    Chart("intl-inflation", PAGE, "prices-jobs", 10,
          "Inflation in the large economies", "Consumer prices, % change on a year earlier",
          kicker="Prices", decimals=1, frequency="M",
          series=_econ([("EA", "hicp_headline"), ("US", "bis_cpi__US"), ("UK", "bis_cpi__GB"),
                        ("JP", "bis_cpi__JP"), ("CN", "bis_cpi__CN")]),
          start="2015-01", reference_lines=[{"axis": "y", "value": 2, "label": "2%"}], default_window="5y",
          notes="Euro area: HICP (Eurostat), including the flash estimate. Others: national CPIs as compiled by the "
                "BIS.",
          what="Annual consumer price inflation: the euro area HICP and national consumer price indices for the US, "
               "UK, Japan and China.",
          caveats="The OECD's euro area CPI stops at December 2025 (the ECOICOP 2 switch), so the euro area line is "
                  "Eurostat's HICP. The UK series is the CPI, the US the CPI-U."),
    Chart("intl-unemployment", PAGE, "prices-jobs", 20,
          "Unemployment in the large economies", "Unemployment rate, % of the labour force, seasonally adjusted",
          kicker="Jobs", decimals=1, frequency="M",
          series=_econ([("EA", "unemployment_rate"), ("US", "oecd_unemployment__USA"),
                        ("UK", "oecd_unemployment__GBR"), ("JP", "oecd_unemployment__JPN")]),
          start="2015-01", default_window="10y",
          what="ILO-based unemployment rates: the euro area from Eurostat, the US, UK and Japan from the OECD's "
               "harmonised series.",
          caveats="The UK figure is a three-month average and arrives later. China publishes no comparable "
                  "rate."),
    Chart("intl-policy-rates", PAGE, "rates-fx", 10,
          "Central bank policy rates", "Policy rate at the end of the month, %",
          kicker="Interest rates", decimals=2, frequency="M",
          series=[Ref(f"bis_policy_rate__{code}", key, name, role, curve="step-after")
                  for code, key, name, role in (("XM", "EA", "ECB", "story"), ("US", "US", "Federal Reserve", "base"),
                                                ("GB", "UK", "Bank of England", "context"),
                                                ("JP", "JP", "Bank of Japan", "context"),
                                                ("CN", "CN", "People's Bank of China", "context"))],
          start="2015-01", default_window="5y",
          notes="ECB: the deposit facility rate since 18 September 2024, the main refinancing rate before (the BIS "
                "series follows the ECB's steering rate). Federal Reserve: midpoint of the target range. China: the "
                "one-year loan prime rate. The Bank of Japan had no policy rate from April 2013 to September 2016.",
          what="The policy rate of each central bank at the end of every month, as compiled by the BIS.",
          caveats="Policy rates are not comparable across countries as levels of stance; compare them with each "
                  "economy's inflation."),
    Chart("intl-real-policy-rates", PAGE, "rates-fx", 15,
          "Real policy rates", "Policy rate at the end of the month minus consumer price inflation, %",
          kicker="Interest rates", decimals=1, frequency="M",
          series=[Ref(f"intl_real_rate_{key.lower()}", key, name, "story" if key == "EA" else
                      ("base" if key == "US" else "context")) for key, _, _, name in REAL_RATE],
          start="2015-01", reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="5y",
          original=True,
          notes="Above zero, the policy rate is higher than current inflation. Euro area: ECB steering rate minus "
                "HICP inflation (including the flash estimate); others: BIS policy rates minus national CPIs.",
          what="Each central bank's policy rate minus the latest annual consumer price inflation: a simple, "
               "backward-looking measure of how tight policy is.",
          transform_text="Policy rate (BIS WS_CBPOL, end of month) minus inflation (Eurostat HICP for the euro area, "
                         "BIS WS_LONG_CPI for the others), month by month.",
          caveats="Uses current inflation, not expected inflation, so it overstates tightness when inflation is "
                  "falling and understates it when inflation is rising."),
    Chart("intl-10y-yields", PAGE, "rates-fx", 20,
          "Ten-year government bond yields", "Long-term government bond yield, monthly average, %",
          kicker="Interest rates", decimals=2, frequency="M",
          series=_econ([("EA", "oecd_y10_ea"), ("US", "oecd_y10__USA"), ("UK", "oecd_y10__GBR"),
                        ("JP", "oecd_y10__JPN"), ("CN", "oecd_y10__CHN")]),
          start="2015-01", default_window="5y",
          what="Ten-year benchmark government bond yields, monthly averages, all from the OECD's financial "
               "indicators (the euro area aggregate is the OECD's EA20).",
          caveats="The euro area yield is a weighted average of member states' yields, not a single bond, and differs "
                  "slightly from Eurostat's EMU convergence yield (used on the Europe page), which comes out about a "
                  "month later. The financial conditions page has the AAA curve and country spreads."),
    Chart("intl-fx-usd", PAGE, "rates-fx", 30,
          "Currencies against the dollar", "US dollars per unit of currency, monthly average, index 2019 = 100",
          kicker="Currencies", units="index", format="index", decimals=1, frequency="M",
          series=[Ref("bis_usd__XM", "EA", "Euro", "story", transform=usd_index),
                  Ref("bis_usd__GB", "UK", "Pound sterling", "base", transform=usd_index),
                  Ref("bis_usd__JP", "JP", "Yen", "context", transform=usd_index),
                  Ref("bis_usd__CN", "CN", "Renminbi", "context", transform=usd_index)],
          reference_lines=[{"axis": "y", "value": 100, "label": "2019 average"}], default_window="max",
          original=True,
          notes="Above 100, the currency buys more dollars than on average in 2019.",
          what="The value of the euro, pound, yen and renminbi in US dollars, indexed to the 2019 average.",
          transform_text="BIS monthly averages of national currency per US dollar, inverted (dollars per unit) and "
                         "divided by their 2019 mean, times 100.",
          caveats="Bilateral rates against one currency; the euro's trade-weighted rate is on the financial "
                  "conditions page."),
    Chart("ea-current-account", PAGE, "external", 10,
          "The euro area current account", "Balance with the rest of the world, 12-month sum, EUR billion",
          kicker="Trade with the world", type="stacked-bar", units="EUR bn", format="eur_bn", decimals=0,
          series=[Ref("intl_ca12_g", "goods", "Goods", "base"), Ref("intl_ca12_s", "services", "Services", "base"),
                  Ref("intl_ca12_in1", "primary", "Primary income", "base"),
                  Ref("intl_ca12_in2", "secondary", "Secondary income", "base"),
                  Ref("intl_ca12_ca", "total", "Current account", "story")],
          total_key="total", start="2012-01", default_window="5y", original=True,
          what="The euro area's current account with countries outside it, and its four components, summed over the "
               "latest 12 months.",
          transform_text="Sum of the latest 12 monthly balances (Eurostat ei_bpm6ca_m, not seasonally adjusted), "
                         "EUR millions divided by 1,000.",
          caveats="Monthly balance of payments data are revised substantially; the 12-month sum removes "
                  "seasonality but not revisions."),
    Chart("ea-trade-balance", PAGE, "external", 20,
          "Euro area trade in goods", "Trade balance with the rest of the world, EUR billion, seasonally adjusted",
          kicker="Trade with the world", type="bar", units="EUR bn", format="eur_bn", decimals=1, frequency="M",
          series=[Ref("intl_ea_trade__BAL_RT", "balance", "Goods trade balance", "story")],
          reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="5y",
          what="Monthly balance of the euro area's trade in goods with non-member countries (exports minus imports), "
               "seasonally adjusted, from the euro indicators release.",
          caveats="Customs-based trade statistics (international trade in goods), not the balance of payments "
                  "goods balance, which differs by merchanting and goods sent for processing."),
    Chart("ea-exports-imports", PAGE, "external", 30,
          "Euro area exports and imports of goods", "Trade with the rest of the world, EUR billion a month, "
                                                     "seasonally adjusted",
          kicker="Trade with the world", units="EUR bn", format="eur_bn", decimals=1, frequency="M",
          series=[Ref("intl_ea_trade__EXP", "exports", "Exports", "story"),
                  Ref("intl_ea_trade__IMP", "imports", "Imports", "base")],
          default_window="5y",
          what="Monthly value of extra-euro area exports and imports of goods, seasonally adjusted.",
          caveats="Values, not volumes: energy prices move imports a lot."),
    Chart("current-account-countries", PAGE, "external", 40,
          "Current accounts across the euro area", "Current account balance, % of GDP, average of four quarters",
          kicker="Trade with the world", type="bar", units="% of GDP", decimals=1, frequency="Q", geo="multi",
          series=[],
          build=country_bars("intl_ca_gdp", "ca", "Current account", codes=CA_CODES, highlight="DE",
                             sort="desc", transform="roll:4"),
          reference_lines=[{"axis": "x", "value": 0, "label": ""}], default_window="max",
          notes="Poland is not in the euro area; shown for comparison. The euro area as a whole is in the chart "
                "above (its balance with non-members).",
          what="Each member state's current account balance with the rest of the world as a share of GDP, averaged "
               "over the latest four quarters.",
          transform_text="Four-quarter moving average of the unadjusted quarterly ratio (Eurostat bop_gdp6_q).",
          caveats="Country balances include trade with other euro area members; the euro area aggregate does not. "
                  "Ireland and Luxembourg are distorted by multinational accounting."),
]
