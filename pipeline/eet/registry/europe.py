"""Only in Europe: indicators with no US counterpart on the original site. The European
Commission's business and consumer surveys (ESI and its components, capacity utilisation),
TARGET balances, house prices, household saving and wealth, business registrations and
bankruptcies, household energy prices, administered prices, and a country table.

Sources: DG ECFIN surveys via Eurostat (``ei_bssi_m_r2``, ``ei_bsin_q_r2``); ECB ``TGB`` and
``DWA``; Eurostat ``prc_hpi_q``, ``prc_hpi_ooq``, ``nasq_10_ki``, ``sts_rb_q``, ``nrg_pc_204``,
``nrg_pc_202``, ``prc_hicp_minr`` (administered-price aggregates ``AP`` and ``TOT_X_AP``; the
dataset ``prc_hicp_admp`` is only the annual list of administered items), ``une_rt_m`` and
``irt_lt_mcby_m``. The country table also reads series declared in the inflation, fiscal and
international modules (``hicp_country``, ``fis_debt_q``, ``fis_balance_a``, ``glance_gdp_yoy``).
"""
from .. import geo
from .. import periods as P
from ..context import Missing
from ..spec import Chart, Ref, Section, Series
from .fiscal import (COUNTRIES, EA_MEMBERS, as_month, country_bars, country_name, period_text, pick_period,
                     value_at)

PAGE = "europe"

ESI_COMPONENTS = {"BS-ICI-BAL": "Industry", "BS-SCI-BAL": "Services", "BS-CSMCI-BAL": "Consumers",
                  "BS-RCI-BAL": "Retail trade", "BS-CCI-BAL": "Construction"}
TARGET_CODES = ["DE", "IT", "ES", "FR", "NL"]
HPI_CODES = ["EA21"] + [c for c in EA_MEMBERS if c != "EL"] + ["PL"]   # no Greek series in prc_hpi_q
ENERGY_CODES = ["EA"] + EA_MEMBERS + ["PL"]                            # "EA" = euro area in nrg_pc_*
GAS_CODES = [c for c in ENERGY_CODES if c not in ("CY", "FI", "MT")]   # no household gas series published
DWA_CODES = {"I10"} | {("GR" if c == "EL" else c) for c in EA_MEMBERS}  # ECB codes; I10 = euro area
Y10_CODES = ["EA"] + [c for c in EA_MEMBERS if c != "EE"] + ["PL"]    # Estonia has no benchmark bond
NRG_URL = "https://ec.europa.eu/eurostat/databrowser/view/{}/default/table"


def _survey(sid, dataset, indic, label, freq="M", start="1990-01", **kw):
    return Series(sid, "eurostat", dataset=dataset, filters={"geo": "EA21", "s_adj": "SA", "indic": indic},
                  freq=freq, label=label, start=start, **kw)


SERIES = [
    Series("eu_esi_components", "eurostat", dataset="ei_bssi_m_r2",
           filters={"geo": "EA21", "s_adj": "SA", "indic": list(ESI_COMPONENTS)}, split="indic",
           labels=ESI_COMPONENTS, freq="M", unit="balance", label="Confidence indicators", start="1990-01"),
    Series("eu_esi_country", "eurostat", dataset="ei_bssi_m_r2",
           filters={"s_adj": "SA", "indic": "BS-ESI-I", "geo": list(geo.STRIP)}, split="geo", freq="M",
           unit="index", label="Economic Sentiment Indicator", start="2000-01"),
    _survey("eu_capacity_util", "ei_bsin_q_r2", "BS-ICU-PC", "Capacity utilisation in industry", freq="Q",
            start="1990-Q1", unit="%"),
    Series("eu_target2", "ecb", dataset="TGB", key="M." + "+".join(TARGET_CODES) + ".N.A094T.U2.EUR.E", split=1,
           freq="M", unit="EUR bn", decimals=0, scale=0.001, start="2000-01",
           label="TARGET balance of the national central bank"),
    Series("eu_hpi", "eurostat", dataset="prc_hpi_q",
           filters={"purchase": "TOTAL", "unit": "RCH_A", "geo": HPI_CODES}, split="geo", freq="Q", unit="% y/y",
           label="House prices, % change on a year earlier", start="2006-Q1"),
    Series("eu_ooh_prices", "eurostat", dataset="prc_hpi_ooq",
           filters={"geo": "EA21", "expend": "TOTAL", "unit": "RCH_A"}, freq="Q", unit="% y/y",
           label="Owner-occupied housing price index, % change on a year earlier", start="2011-Q1"),
    Series("eu_saving_rate", "eurostat", dataset="nasq_10_ki",
           filters={"geo": "EA21", "sector": "S14_S15", "na_item": "SRG_S14_S15", "s_adj": "SCA", "unit": "PC"},
           freq="Q", unit="% of disposable income", label="Gross household saving rate", start="1999-Q1"),
    Series("eu_business_demography", "eurostat", dataset="sts_rb_q",
           filters={"geo": "EA21", "nace_r2": "B-S_X_O_S94", "s_adj": "SCA", "unit": "I21",
                    "indic_bt": ["REG", "BKRT"]}, split="indic_bt",
           labels={"REG": "Business registrations", "BKRT": "Bankruptcy declarations"}, freq="Q", unit="index",
           label="Business registrations and bankruptcies, index 2021 = 100", start="2015-Q1"),
    Series("eu_elec_price", "eurostat", dataset="nrg_pc_204",
           filters={"siec": "E7000", "nrg_cons": "KWH2500-4999", "unit": "KWH", "tax": "I_TAX", "currency": "EUR",
                    "geo": ENERGY_CODES}, split="geo", freq="A", unit="euro cents per kWh", scale=100.0,
           label="Household electricity price, all taxes included", start="2022-S1",
           source_url=NRG_URL.format("nrg_pc_204")),
    Series("eu_gas_price", "eurostat", dataset="nrg_pc_202",
           filters={"siec": "G3000", "nrg_cons": "GJ20-199", "unit": "KWH", "tax": "I_TAX", "currency": "EUR",
                    "geo": GAS_CODES}, split="geo", freq="A", unit="euro cents per kWh", scale=100.0,
           label="Household gas price, all taxes included", start="2022-S1",
           source_url=NRG_URL.format("nrg_pc_202")),
    Series("eu_hicp_admin", "eurostat", dataset="prc_hicp_minr",
           filters={"geo": "EA21", "unit": "RCH_A", "coicop18": ["AP", "TOT_X_AP"]}, split="coicop18",
           labels={"AP": "Administered prices", "TOT_X_AP": "Excluding administered prices"}, freq="M",
           label="HICP, administered prices, % y/y", start="2002-01"),
    Series("eu_dwa_top10", "ecb", dataset="DWA", key="Q..S14._Z._Z.NWA.T10.PT.S.N", split=1,
           keep=lambda c: c in DWA_CODES, labels={"I10": "Euro area"}, freq="Q", unit="% of net wealth",
           label="Share of net wealth held by the wealthiest 10% of households", start="2009-Q1"),
    Series("glance_unemp", "eurostat", dataset="une_rt_m",
           filters={"s_adj": "SA", "sex": "T", "age": "TOTAL", "unit": "PC_ACT", "geo": COUNTRIES}, split="geo",
           freq="M", unit="%", label="Unemployment rate", start="2015-01"),
    Series("y10_members", "eurostat", dataset="irt_lt_mcby_m",
           filters={"int_rt": "MCBY", "geo": Y10_CODES}, split="geo", freq="M", unit="%", decimals=2,
           label="10-year government bond yield (EMU convergence criterion)", start="2015-01"),
]

SECTIONS = [
    Section(PAGE, "glance", "Europe at a glance",
            "Growth, jobs, prices, public finances and borrowing costs in every euro area country.", 5),
    Section(PAGE, "surveys", "Business and consumer surveys",
            "The European Commission's monthly surveys: the earliest free read on the cycle.", 10),
    Section(PAGE, "fragmentation", "Fragmentation",
            "TARGET balances: where money moves inside the euro area's payment system.", 20),
    Section(PAGE, "housing", "Housing", "House prices across the euro area.", 30),
    Section(PAGE, "households", "Households", "How much households save, and how wealth is shared.", 40),
    Section(PAGE, "business", "Business dynamics", "New businesses and bankruptcies.", 50),
    Section(PAGE, "energy", "Energy and regulated prices",
            "What households pay for electricity and gas, and the prices set or steered by governments.", 60),
]


# ---------------------------------------------------------------------------- build hooks

def average_line(sid, start, end, label):
    """Reference line at the mean of ``sid`` over ``start``..``end`` (computed at build time)."""
    def build(ctx, chart):
        vals = [v for p, v, _ in ctx.obs(sid) if start <= p <= end and v is not None]
        if not vals:
            raise Missing(f"{sid}: no data between {start} and {end}")
        mean = round(sum(vals) / len(vals), 1)
        return {"reference_lines": list(chart.reference_lines) + [{"axis": "y", "value": mean, "label": label}]}
    return build


GLANCE = [
    # key, label, format, decimals, panel (children keyed by Eurostat geo code)
    ("gdp", "GDP, % y/y", "pct", 1, "glance_gdp_yoy"),
    ("unemp", "Unemployment, %", "pct", 1, "glance_unemp"),
    ("hicp", "Inflation, % y/y", "pct", 1, "hicp_country"),
    ("debt", "Debt, % of GDP", "pct", 1, "fis_debt_q"),
    ("balance", "Budget balance, % of GDP", "pct", 1, "fis_balance_a"),
]


def glance_table(ctx, chart):
    """Rows: euro area, its members, Poland. Each column is taken at its own latest common period
    (the most recent one at least 60% of countries have published); the period is in the header."""
    order = ["EA21"] + sorted(EA_MEMBERS, key=geo.name) + ["PL"]
    rows = {c: {"label": country_name(c) + (" (not in the euro area)" if c == "PL" else ""), "values": {},
                "flag": None} for c in order}
    cols, periods = [], []
    for key, label, fmt, dec, panel in GLANCE:
        try:
            data = ctx.panel(panel)
        except Missing:
            continue
        data = {c: o for c, o in data.items() if c in rows}
        period = pick_period({c: o for c, o in data.items() if c != "EA21"} or data)
        if period is None:
            continue
        cols.append({"key": key, "label": f"{label}, {period_text(period)}", "format": fmt, "decimals": dec})
        periods.append(period)
        for c in order:
            rows[c]["values"][key] = value_at(data.get(c, []), period)[0]
    # 10-year spread over Germany (monthly averages, Eurostat convergence yields)
    try:
        y10 = ctx.panel("y10_members")
    except Missing:
        y10 = {}
    if "DE" in y10:
        period = pick_period(y10)
        de = value_at(y10["DE"], period)[0]
        if de is not None:
            cols.append({"key": "spread", "label": f"10-year spread over Germany, pp, {period_text(period)}",
                         "format": "pp", "decimals": 2})
            periods.append(period)
            for c in order:
                y = value_at(y10.get("EA" if c == "EA21" else c, []), period)[0]
                rows[c]["values"]["spread"] = None if y is None else y - de
    if not cols:
        raise Missing("glance table has no data")
    keys = [c["key"] for c in cols]
    out = []
    for c in order:
        r = rows[c]
        r["values"] = {k: r["values"].get(k) for k in keys}
        if any(v is not None for v in r["values"].values()):
            out.append(r)
    newest = max(periods, key=P.compare_key)
    return {"columns": cols, "rows": out, "latest": {"period": newest, "values": {}, "flag": None}}


CHARTS = [
    Chart("europe-at-a-glance", PAGE, "glance", 10,
          "Europe at a glance", "Latest readings by country",
          kicker="Country by country", type="table", units="", decimals=1, build=glance_table,
          source="Eurostat (namq_10_gdp, une_rt_m, prc_hicp_minr, gov_10q_ggdebt, gov_10dd_edpt1, irt_lt_mcby_m)",
          source_url="https://ec.europa.eu/eurostat/web/euro-indicators",
          notes="Each column is shown for the latest period that at least 60% of countries have published; a dash "
                "means the country has not published that period yet. GDP: real, seasonally adjusted. Debt: latest "
                "quarter. Budget balance: latest year (negative = deficit). Spread: 10-year government yield minus "
                "Germany's, monthly average; the euro area row uses the euro area average yield. Estonia has no "
                "benchmark 10-year bond.",
          what="Real GDP growth, unemployment, HICP inflation, government debt, the budget balance and the 10-year "
               "spread over the Bund for the euro area, every member state and Poland.",
          transform_text="As published. Spread = country 10-year yield minus the German 10-year yield in the same "
                         "month.",
          caveats="Columns refer to different periods (quarterly, monthly, annual); read across a row with care."),
    Chart("economic-sentiment", PAGE, "surveys", 10,
          "Economic sentiment", "Economic Sentiment Indicator, euro area, long-run average = 100",
          kicker="Surveys", units="index", format="index", decimals=1,
          series=[Ref("esi", "esi", "Economic Sentiment Indicator", "story", start="2000-01")],
          reference_lines=[{"axis": "y", "value": 100, "label": "Long-run average"}], default_window="10y",
          what="The European Commission's Economic Sentiment Indicator: a weighted composite of confidence in "
               "industry (40%), services (30%), consumers (20%), construction and retail trade (5% each), scaled "
               "to a long-run average of 100 and a standard deviation of 10.",
          caveats="A survey of expectations and assessments, not a measure of output; it leads GDP turning points "
                  "but can miss levels."),
    Chart("sentiment-components", PAGE, "surveys", 20,
          "Confidence by sector", "European Commission confidence indicators, euro area, balance of answers, "
                                  "seasonally adjusted",
          kicker="Surveys", units="balance", format="level", decimals=1,
          series=[Ref("eu_esi_components__BS-ICI-BAL", "industry", "Industry", "base"),
                  Ref("eu_esi_components__BS-SCI-BAL", "services", "Services", "story"),
                  Ref("eu_esi_components__BS-CSMCI-BAL", "consumers", "Consumers", "context"),
                  Ref("eu_esi_components__BS-RCI-BAL", "retail", "Retail trade", "context"),
                  Ref("eu_esi_components__BS-CCI-BAL", "construction", "Construction", "context")],
          start="2000-01", reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="10y",
          what="The five sector confidence indicators behind the ESI: balances of positive minus negative answers "
               "to the survey questions for each sector.",
          caveats="Balances are not comparable in level across sectors; compare each with its own history."),
    Chart("esi-countries", PAGE, "surveys", 30,
          "Sentiment in the largest economies", "Economic Sentiment Indicator, long-run average = 100",
          kicker="Surveys", type="country-strip", units="index", format="index", decimals=1,
          series=[Ref(f"eu_esi_country__{c}", c, geo.name(c), "base") for c in geo.STRIP]
                 + [Ref("esi", "EA21", "Euro area", "context")],
          start="2015-01", reference_lines=[{"axis": "y", "value": 100, "label": "Long-run average"}],
          default_window="5y",
          notes="Poland is not in the euro area; its ESI is shown for comparison.",
          what="The Economic Sentiment Indicator for Germany, France, Italy, Spain, the Netherlands and Poland, with "
               "the euro area."),
    Chart("capacity-utilisation", PAGE, "surveys", 40,
          "How hard factories are running", "Capacity utilisation in manufacturing, euro area, %",
          kicker="Surveys", units="%", decimals=1,
          series=[Ref("eu_capacity_util", "cu", "Capacity utilisation", "story")],
          build=average_line("eu_capacity_util", "1990-Q1", "2019-Q4", "1990-2019 average"),
          default_window="max",
          what="Firms' answers to the quarterly industry survey question on their current level of capacity "
               "utilisation, as a percentage of full capacity, seasonally adjusted.",
          transform_text="As published; the reference line is the 1990-2019 mean, computed by the tracker.",
          caveats="Survey-based and quarterly (January, April, July, October)."),
    Chart("target2-balances", PAGE, "fragmentation", 10,
          "TARGET balances", "Claims (+) or liabilities (-) of national central banks within the Eurosystem, "
                             "end of month, EUR billion",
          kicker="Fragmentation", units="EUR bn", format="eur_bn", decimals=0,
          series=[Ref("eu_target2__DE", "DE", "Bundesbank", "base"),
                  Ref("eu_target2__IT", "IT", "Banca d'Italia", "story"),
                  Ref("eu_target2__ES", "ES", "Banco de España", "context"),
                  Ref("eu_target2__FR", "FR", "Banque de France", "context"),
                  Ref("eu_target2__NL", "NL", "De Nederlandsche Bank", "context")],
          reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="max",
          what="Each national central bank's net claim on (or liability to) the Eurosystem arising from cross-border "
               "payments in TARGET, the euro area's payment system.",
          transform_text="EUR millions divided by 1,000.",
          caveats="Balances also grow with central bank asset purchases settled across borders, so a widening is "
                  "not by itself capital flight."),
    Chart("house-prices", PAGE, "housing", 10,
          "House prices", "Euro area, % change on a year earlier",
          kicker="Housing", decimals=1,
          series=[Ref("eu_hpi__EA21", "hpi", "House price index", "story"),
                  Ref("eu_ooh_prices", "ooh", "Owner-occupied housing price index", "context")],
          reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="max",
          what="Annual change in the prices of all dwellings bought by households (new and existing), and in the "
               "owner-occupied housing price index, which also covers the costs of owning a home.",
          caveats="Quarterly, published about three months after the quarter. Owner-occupied housing is not in the "
                  "HICP."),
    Chart("house-prices-countries", PAGE, "housing", 20,
          "House prices in the largest economies", "House price index, % change on a year earlier",
          kicker="Housing", type="country-strip", decimals=1,
          series=[Ref(f"eu_hpi__{c}", c, geo.name(c), "base") for c in geo.STRIP]
                 + [Ref("eu_hpi__EA21", "EA21", "Euro area", "context")],
          start="2015-Q1", reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="10y",
          notes="Poland is not in the euro area; shown for comparison.",
          what="Annual house price inflation in Germany, France, Italy, Spain, the Netherlands and Poland, with the "
               "euro area."),
    Chart("household-saving-rate", PAGE, "households", 10,
          "How much households save", "Gross household saving rate, euro area, % of gross disposable income, "
                                      "seasonally adjusted",
          kicker="Households", units="%", decimals=1,
          series=[Ref("eu_saving_rate", "saving", "Saving rate", "story")],
          build=average_line("eu_saving_rate", "2015-Q1", "2019-Q4", "2015-2019 average"), default_window="max",
          what="Gross saving of households and non-profit institutions serving households as a share of their gross "
               "disposable income (adjusted for the change in pension entitlements).",
          transform_text="As published; the reference line is the 2015-2019 mean, computed by the tracker.",
          caveats="Gross saving includes the money households put into housing investment and pensions."),
    Chart("wealth-top10", PAGE, "households", 20,
          "How concentrated wealth is", "Share of household net wealth held by the wealthiest 10%, %",
          kicker="Households", type="bar", units="%", decimals=1, frequency="Q", geo="multi",
          series=[Ref("eu_dwa_top10__I10", "placeholder", "", "base")],
          build=country_bars("eu_dwa_top10", "top10", "Top 10% share", ea_code="I10", sort="desc"),
          default_window="max", source_url="https://data.ecb.europa.eu/data/datasets/DWA",
          notes="The euro area aggregate is the ECB's (area code I10).",
          what="The ECB's Distributional Wealth Accounts: the share of total household net wealth owned by the "
               "top decile of households, by country.",
          caveats="Experimental statistics: survey data (HFCS) aligned to national accounts totals, with modelled "
                  "top tails. Cross-country levels are less reliable than changes over time."),
    Chart("business-demography", PAGE, "business", 10,
          "New businesses and bankruptcies", "Euro area, industry, construction and market services, index 2021 = "
                                             "100, seasonally adjusted",
          kicker="Business dynamics", units="index", format="index", decimals=1,
          series=[Ref("eu_business_demography__BKRT", "bankruptcies", "Bankruptcy declarations", "story"),
                  Ref("eu_business_demography__REG", "registrations", "Business registrations", "base")],
          reference_lines=[{"axis": "y", "value": 100, "label": "2021"}], default_window="max",
          what="Quarterly indices of new business registrations and of bankruptcy declarations, euro area.",
          caveats="Bankruptcy procedures differ by country; the index shows the trend, not a bankruptcy rate."),
    Chart("electricity-prices", PAGE, "energy", 10,
          "What households pay for electricity",
          "Household electricity price, 2,500-5,000 kWh a year, all taxes included, euro cents per kWh",
          kicker="Energy", type="bar", units="c/kWh", format="level", decimals=1, frequency="A", geo="multi",
          series=[Ref("eu_elec_price__EA", "placeholder", "", "base", transform=as_month)],
          build=country_bars("eu_elec_price", "price", "Electricity price", codes=ENERGY_CODES, highlight="IT",
                             ea_code="EA", sort="desc"),
          default_window="max", source_url=NRG_URL.format("nrg_pc_204"),
          notes="Half-yearly data for the medium consumption band (DC). Poland is not in the euro area.",
          what="The average price households pay for electricity in the medium consumption band, including network "
               "charges, levies and VAT.",
          caveats="Prices are averages over the half-year and include taxes and support measures, which differ by "
                  "country."),
    Chart("gas-prices", PAGE, "energy", 20,
          "What households pay for gas",
          "Household gas price, 20-200 GJ a year, all taxes included, euro cents per kWh",
          kicker="Energy", type="bar", units="c/kWh", format="level", decimals=1, frequency="A", geo="multi",
          series=[Ref("eu_gas_price__EA", "placeholder", "", "base", transform=as_month)],
          build=country_bars("eu_gas_price", "price", "Gas price", codes=GAS_CODES, highlight="IT", ea_code="EA",
                             sort="desc"),
          default_window="max", source_url=NRG_URL.format("nrg_pc_202"),
          notes="Half-yearly data for the medium consumption band (D2). Cyprus, Finland and Malta publish no "
                "household gas price. Poland is not in the euro area.",
          what="The average price households pay for natural gas in the medium consumption band, including network "
               "charges, levies and VAT.",
          caveats="Prices include taxes and support measures, which differ by country."),
    Chart("hicp-administered", PAGE, "energy", 30,
          "Prices set by governments", "Euro area HICP, % change on a year earlier",
          kicker="Regulated prices", decimals=1,
          series=[Ref("hicp_headline", "headline", "All items", "base", start="2015-01"),
                  Ref("eu_hicp_admin__AP", "administered", "Administered prices", "story", start="2015-01"),
                  Ref("eu_hicp_admin__TOT_X_AP", "market", "Excluding administered prices", "context",
                      start="2015-01")],
          reference_lines=[{"axis": "y", "value": 2, "label": "ECB target"}], default_window="10y",
          what="Inflation in the HICP items whose prices are fully or mainly set or steered by governments or "
               "regulators (for example some energy tariffs, public transport, health and education fees), and "
               "in the rest of the basket.",
          caveats="Which items count as administered differs by country and changes over time (prc_hicp_admp)."),
]
