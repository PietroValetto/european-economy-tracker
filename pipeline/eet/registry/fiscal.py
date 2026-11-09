"""Public finances page: euro area debt, deficit, primary balance, revenue and spending; the
same by country (latest year, Maastricht reference values); interest bills; the Commission's
latest forecast; r minus g; and a country table.

Sources (one per series): Eurostat quarterly government finance (``gov_10q_ggdebt``,
``gov_10q_ggnfa``, euro area EA21, seasonally adjusted where published) and the annual EDP
notification table (``gov_10dd_edpt1``, every member state); the Commission's latest forecast
vintage from DG ECFIN Redisstat (``FDMS_UBLGE``, ``FDMS_UDGG``); Eurostat annual 10-year
convergence yields (``irt_lt_mcby_a``) and nominal GDP (``nama_10_gdp``) for r minus g.

This module also holds the small helpers the international and Europe modules share
(:func:`pick_period`, :func:`country_bars`, :class:`Fields`).
"""
from .. import builders, geo
from .. import periods as P
from .. import transforms
from ..context import Missing
from ..spec import Chart, Derived, Ref, Section, Series

PAGE = "fiscal"

EA_MEMBERS = list(geo.EURO_AREA)
COUNTRIES = ["EA21"] + EA_MEMBERS + ["PL"]          # Eurostat codes
FDMS_GEO = ["EA"] + EA_MEMBERS + ["PL"]             # DG ECFIN forecast codes ("EA" = euro area)
RG_COUNTRIES = ["DE", "FR", "IT", "ES"]


# ---------------------------------------------------------------------------- shared helpers

class Fields(dict):
    """Bundle fields from a build hook that the core must merge verbatim.

    The core pops ``series`` from a hook's result to round the points and to compute
    ``latest``/``previous`` by period. Categorical bars (``[["Italy", 137.1], ...]``, CONTRACT
    section 3) have no periods, so that step would fail; this dict keeps ``series`` in place and
    the core's final ``bundle.update(...)`` copies it, with ``latest``, ``previous`` and any other
    field, as given. Values are rounded here. A chart using it still needs one ordinary ``Ref``
    (the core refuses a chart with no series); the hook's fields replace what the core built
    from it. See docs/notes/fiscal-international-europe.md (core change requested).
    """

    def pop(self, key, *default):
        if key == "series":
            return default[0] if default else []
        return super().pop(key, *default)


def _rnd(v, d):
    if v is None:
        return None
    x = round(float(v), d)
    return int(x) if d == 0 else (0.0 if x == 0 else x)


def value_at(obs, period):
    for p, v, f in obs:
        if p == period:
            return v, f
    return None, None


def pick_period(obs_by_code, min_share=0.6):
    """The most recent period for which at least ``min_share`` of the codes have a value.

    Used for cross-country snapshots so that one early publisher does not leave every other
    country blank (and one late publisher does not hold the snapshot back)."""
    lasts = {}
    for code, obs in obs_by_code.items():
        for p, v, _ in obs:
            if v is not None:
                lasts.setdefault(p, set()).add(code)
    if not lasts:
        return None
    n = len(obs_by_code)
    for p in sorted(lasts, key=_period_key, reverse=True):
        if len(lasts[p]) >= max(1, min_share * n):
            return p
    return max(lasts, key=_period_key)


def _period_key(p):
    if len(p) == 7 and p[4:6] == "-S":           # Eurostat half-years: 2026-S1, 2026-S2
        return (int(p[:4]), 1 if p[-1] == "1" else 7)
    d = P.start_date(p)
    return (d.year, d.month, d.day)


def period_text(p):
    """'2025', 'Q2 2026', 'Sep 2026', 'first half of 2026'."""
    if len(p) == 7 and p[4:6] == "-S":
        return f"{'first' if p[-1] == '1' else 'second'} half of {p[:4]}"
    return builders.period_label(p)


def country_name(code, labels=None):
    if labels and code in labels:
        return labels[code]
    if code in ("EA21", "EA", "EA20", "I10", "U2", "XM"):
        return "Euro area"
    return geo.name(code)


def country_bars(panel, key, label, *, codes=None, highlight=None, sort="desc", ea_code="EA21",
                 labels=None, decimals=1, min_share=0.6, transform=None, subtitle_period=True):
    """Build hook for categorical bars: one bar per country at the latest common period.

    ``panel`` is a registry panel id. ``highlight`` is a geo code; the bundle's ``highlight`` is
    that country's display label (what the renderer matches). Countries without the chosen period
    are left out and named in the notes. ``latest`` holds the euro area value when there is one.
    """
    def build(ctx, chart):
        data = ctx.panel(panel)
        if codes is not None:
            data = {c: data[c] for c in codes if c in data}
        if transform is not None:
            data = {c: ctx.apply(o, transform) for c, o in data.items()}
        data = {c: o for c, o in data.items() if o}
        if not data:
            raise Missing(f"{panel}: no country data")
        period = pick_period(data, min_share)
        bars, missing = [], []
        for c in (codes or sorted(data)):
            if c not in data:
                if codes is not None:
                    missing.append(c)
                continue
            v, f = value_at(data[c], period)
            if v is None:
                missing.append(c)
                continue
            bars.append((country_name(c, labels), _rnd(v, decimals), c, f))
        if not bars:
            raise Missing(f"{panel}: no values for {period}")
        if sort == "desc":
            bars.sort(key=lambda b: -b[1])
        elif sort == "asc":
            bars.sort(key=lambda b: b[1])
        series = [{"key": key, "label": label, "role": "base", "points": [[b[0], b[1]] for b in bars]}]
        ea = data.get(ea_code)
        latest = {"period": period, "values": {}, "flag": None}
        previous = None
        if ea:
            v, f = value_at(ea, period)
            if v is not None:
                latest = {"period": period, "values": {key: _rnd(v, decimals)}, "flag": f or None}
            prev = [(p, w) for p, w, _ in ea if w is not None and _period_key(p) < _period_key(period)]
            if prev:
                previous = {"period": prev[-1][0], "values": {key: _rnd(prev[-1][1], decimals)}}
        out = Fields(series=series, latest=latest, previous=previous)
        if highlight:
            out["highlight"] = country_name(highlight, labels)
        notes = chart.notes or ""
        if missing:
            names = ", ".join(country_name(c, labels) for c in missing)
            notes = (notes + " " if notes else "") + f"Not yet published for {period_text(period)}: {names}."
        out["notes"] = notes
        if subtitle_period:
            out["subtitle"] = f"{chart.subtitle}, {period_text(period)}"
        return out
    return build


def as_month(obs):
    """Half-year periods (2026-S1) to the first month of the half (2026-01), so the core can
    order them. Used only on the placeholder Ref of a categorical bar chart."""
    out = []
    for p, v, f in obs:
        if len(p) == 7 and p[4:6] == "-S":
            p = f"{p[:4]}-{'01' if p[-1] == '1' else '07'}"
        out.append((p, v, f))
    return out


# ---------------------------------------------------------------------------- series

def _edpt1(sid, item, label):
    return Series(sid, "eurostat", dataset="gov_10dd_edpt1",
                  filters={"sector": "S13", "unit": "PC_GDP", "na_item": item, "geo": COUNTRIES},
                  split="geo", freq="A", unit="% of GDP", label=label, start="1995")


def _ggnfa(sid, item, label, s_adj="SCA"):
    return Series(sid, "eurostat", dataset="gov_10q_ggnfa",
                  filters={"geo": "EA21", "sector": "S13", "unit": "PC_GDP", "s_adj": s_adj, "na_item": item},
                  freq="Q", unit="% of GDP", label=label, start="1999-Q1")


def _fdms(sid, indicator, label):
    return Series(sid, "ecfin", dataset=f"FDMS_{indicator}", filters={"GEO": FDMS_GEO}, split="GEO",
                  freq="A", unit="% of GDP", label=label, start="2015",
                  source_url="https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/"
                             "economic-forecasts_en")


SERIES = [
    _ggnfa("fis_balance_q", "B9", "Net lending (+) / net borrowing (-)"),
    _ggnfa("fis_revenue_q", "TR", "Total revenue"),
    _ggnfa("fis_expenditure_q", "TE", "Total expenditure"),
    _ggnfa("fis_interest_q", "D41PAY", "Interest payable", s_adj="NSA"),
    _edpt1("fis_balance_a", "B9", "Government balance (net lending)"),
    _edpt1("fis_debt_a", "GD", "Government gross debt"),
    _edpt1("fis_interest_a", "D41PAY", "Interest expenditure"),
    Series("fis_debt_q", "eurostat", dataset="gov_10q_ggdebt",
           filters={"sector": "S13", "na_item": "GD", "unit": "PC_GDP", "geo": COUNTRIES}, split="geo",
           freq="Q", unit="% of GDP", label="Government gross debt (quarterly)", start="2015-Q1"),
    _fdms("ec_fc_balance", "UBLGE", "Government balance, Commission forecast"),
    _fdms("ec_fc_debt", "UDGG", "Government gross debt, Commission forecast"),
    Series("fis_y10_annual", "eurostat", dataset="irt_lt_mcby_a",
           filters={"int_rt": "MCBY", "geo": ["EA"] + RG_COUNTRIES}, split="geo", freq="A", unit="%",
           decimals=2, label="10-year government bond yield, annual average", start="1993"),
    Series("fis_ngdp_annual", "eurostat", dataset="nama_10_gdp",
           filters={"na_item": "B1GQ", "unit": "CP_MEUR", "geo": ["EA21"] + RG_COUNTRIES}, split="geo",
           freq="A", unit="EUR mn", label="GDP at current prices", start="1995"),
]


def r_minus_g(y10, ngdp):
    """10-year yield (annual average, %) minus nominal GDP growth (% on a year earlier)."""
    return transforms.spread(y10, transforms.yoy(ngdp))


def primary_balance(balance, interest):
    """Primary balance = net lending + interest payable (both % of GDP)."""
    iv = {p: v for p, v, _ in interest}
    return [(p, v + iv[p], f) for p, v, f in balance if v is not None and iv.get(p) is not None]


DERIVED = [
    Derived("fis_primary_a_ea", ["fis_balance_a__EA21", "fis_interest_a__EA21"], primary_balance, freq="A",
            unit="% of GDP", label="Primary balance"),
    Derived("fis_rg_ea", ["fis_y10_annual__EA", "fis_ngdp_annual__EA21"], r_minus_g, freq="A", unit="pp",
            decimals=1, label="Euro area"),
] + [
    Derived(f"fis_rg_{c.lower()}", [f"fis_y10_annual__{c}", f"fis_ngdp_annual__{c}"], r_minus_g, freq="A",
            unit="pp", decimals=1, label=geo.name(c))
    for c in RG_COUNTRIES
]

SECTIONS = [
    Section(PAGE, "debt", "Government debt",
            "Gross debt under the Maastricht definition; the EU's reference value is 60% of GDP.", 10),
    Section(PAGE, "deficit", "Deficits",
            "Net borrowing of all levels of government; the reference value is a deficit of 3% of GDP.", 20),
    Section(PAGE, "interest", "The cost of debt",
            "What governments pay in interest, and whether growth outruns the interest rate.", 30),
    Section(PAGE, "forecasts", "The Commission's forecast",
            "The European Commission's latest published forecast for deficits and debt.", 40),
    Section(PAGE, "countries", "Country by country", "The latest annual figures for every member state.", 50),
]

EDP_URL = "https://ec.europa.eu/eurostat/databrowser/view/gov_10dd_edpt1/default/table"
REF_60 = [{"axis": "y", "value": 60, "label": "60% reference value"}]
REF_3 = [{"axis": "y", "value": -3, "label": "3% deficit reference value"}]


# ---------------------------------------------------------------------------- build hooks

def forecast_vs_outturn(outturn_id, forecast_id, fc_code="EA", start="2010"):
    """Outturn (Eurostat) and the Commission's forecast years, joined at the last outturn year."""
    def build(ctx, chart):
        out = [o for o in ctx.obs(outturn_id) if o[0] >= start and o[1] is not None]
        fc = ctx.panel(forecast_id).get(fc_code)
        if not out or not fc:
            raise Missing("forecast or outturn missing")
        last = out[-1][0]
        fpts = [[p, v] for p, v, _ in fc if p >= last and v is not None]
        if len(fpts) < 2:
            raise Missing("no forecast years beyond the latest outturn")
        stamp = ctx.updated(forecast_id) or ""
        series = [builders.series_entry("outturn", "Eurostat outturn", "base", out),
                  {"key": "forecast", "label": "Commission forecast", "role": "story", "points": fpts}]
        res = {"series": series}
        if stamp:
            res["notes"] = (chart.notes + " " if chart.notes else "") + \
                f"Forecast vintage published {stamp[:10]}."
        return res
    return build


def fiscal_table(ctx, chart):
    bal, debt, intr = ctx.panel("fis_balance_a"), ctx.panel("fis_debt_a"), ctx.panel("fis_interest_a")
    year = pick_period({c: o for c, o in bal.items() if c != "EA21"})
    if year is None:
        raise Missing("no balance data")
    try:
        debt_q = ctx.panel("fis_debt_q")
    except Missing:
        debt_q = {}
    q = pick_period(debt_q) if debt_q else None
    fc_b, fc_d = {}, {}
    try:
        fc_b = ctx.panel("ec_fc_balance")
    except Missing:
        pass
    try:
        fc_d = ctx.panel("ec_fc_debt")
    except Missing:
        pass
    fyear = str(int(year) + 1)
    cols = [{"key": "balance", "label": f"Balance {year}", "format": "pct"},
            {"key": "primary", "label": f"Primary balance {year}", "format": "pct"},
            {"key": "interest", "label": f"Interest {year}", "format": "pct"},
            {"key": "debt", "label": f"Debt {year}", "format": "pct"}]
    if q:
        cols.append({"key": "debt_q", "label": f"Debt {period_text(q)}", "format": "pct"})
    if fc_b or fc_d:
        cols += [{"key": "fc_balance", "label": f"Balance {fyear}, EC forecast", "format": "pct"},
                 {"key": "fc_debt", "label": f"Debt {fyear}, EC forecast", "format": "pct"}]
    rows = []
    order = ["EA21"] + sorted(EA_MEMBERS, key=geo.name) + ["PL"]
    for c in order:
        b, f = value_at(bal.get(c, []), year)
        i, _ = value_at(intr.get(c, []), year)
        d, _ = value_at(debt.get(c, []), year)
        vals = {"balance": b, "primary": (b + i) if b is not None and i is not None else None,
                "interest": i, "debt": d}
        if q:
            vals["debt_q"] = value_at(debt_q.get(c, []), q)[0]
        if fc_b or fc_d:
            fc = "EA" if c == "EA21" else c
            vals["fc_balance"] = value_at(fc_b.get(fc, []), fyear)[0]
            vals["fc_debt"] = value_at(fc_d.get(fc, []), fyear)[0]
        if all(v is None for v in vals.values()):
            continue
        label = country_name(c) + (" (not in the euro area)" if c == "PL" else "")
        rows.append({"label": label, "values": vals, "flag": f or None, "period": year})
    return {"columns": cols, "rows": rows, "latest": {"period": year, "values": {}, "flag": None}}


# ---------------------------------------------------------------------------- charts

def _placeholder(sid, transform=None):
    """The one ordinary Ref a categorical chart needs (see :class:`Fields`)."""
    return [Ref(sid, "placeholder", "", "base", transform=transform)]


CHARTS = [
    Chart("gov-debt", PAGE, "debt", 10,
          "Euro area government debt", "General government gross debt, euro area, % of GDP",
          kicker="Public debt", units="% of GDP", decimals=1,
          series=[Ref("gov_debt", "debt", "Gross debt", "story")],
          reference_lines=REF_60, default_window="max",
          notes="Quarterly Maastricht debt; the latest quarters are provisional (flag p).",
          what="Consolidated gross debt of general government (central, state, local government and social "
               "security funds) at nominal value, as a share of GDP over the latest four quarters.",
          caveats="Gross debt: government financial assets are not netted out. The euro area series is the fixed "
                  "EA21 composition back to 2000."),
    Chart("gov-debt-countries", PAGE, "debt", 20,
          "Government debt by country", "General government gross debt, % of GDP",
          kicker="Country by country", type="bar", units="% of GDP", decimals=1, frequency="A", geo="multi",
          series=_placeholder("fis_debt_a__EA21"),
          build=country_bars("fis_debt_a", "debt", "Gross debt", codes=COUNTRIES, highlight="IT", sort="desc"),
          reference_lines=[{"axis": "x", "value": 60, "label": "60%"}], default_window="max",
          source_url=EDP_URL,
          notes="Poland is not in the euro area; shown for comparison.",
          what="Maastricht gross debt of each member state's general government in the latest year of the EDP "
               "notification, with the euro area.",
          transform_text="As published (annual EDP notification); latest year that at least 60% of countries "
                         "report.",
          caveats="Annual data from the April and October notifications; quarterly figures are on the euro area "
                  "chart above."),
    Chart("gov-debt-heatmap", PAGE, "debt", 30,
          "Debt across the euro area over ten years", "General government gross debt, % of GDP",
          kicker="Country by country", type="heatmap", units="% of GDP", decimals=0, frequency="A",
          build=builders.heatmap(["fis_debt_a__EA21"] + [f"fis_debt_a__{c}" for c in EA_MEMBERS], last_n=10,
                                 scale="diverging", midpoint=60, pin_first="EA21"),
          source_url=EDP_URL, default_window="max",
          notes="Rows are sorted by the latest year, euro area first. The colour scale is centred on the 60% "
                "reference value.",
          what="Maastricht gross debt in each of the 21 euro area members, year by year, for the last ten years."),
    Chart("gov-balance", PAGE, "deficit", 10,
          "Euro area government balance", "Net lending (+) or net borrowing (-) of general government, euro area, "
                                          "% of GDP, seasonally adjusted",
          kicker="The budget", type="bar", units="% of GDP", decimals=1,
          series=[Ref("fis_balance_q", "balance", "Government balance", "story")],
          reference_lines=REF_3, default_window="10y",
          what="Quarterly net lending or borrowing of general government in the euro area, seasonally and calendar "
               "adjusted, as a share of quarterly GDP.",
          caveats="Quarterly balances are noisier than the annual EDP figures; one-off transactions (bank support, "
                  "EU fund timing) can move a single quarter."),
    Chart("gov-deficit-countries", PAGE, "deficit", 20,
          "Government balance by country", "Net lending (+) or net borrowing (-) of general government, % of GDP",
          kicker="Country by country", type="bar", units="% of GDP", decimals=1, frequency="A", geo="multi",
          series=_placeholder("fis_balance_a__EA21"),
          build=country_bars("fis_balance_a", "balance", "Government balance", codes=COUNTRIES, highlight="FR",
                             sort="asc"),
          reference_lines=[{"axis": "x", "value": -3, "label": "-3%"}], default_window="max", source_url=EDP_URL,
          notes="A negative number is a deficit. Poland is not in the euro area; shown for comparison.",
          what="Each member state's general government balance in the latest year of the EDP notification.",
          transform_text="As published (annual EDP notification); latest year that at least 60% of countries "
                         "report.",
          caveats="The 3% line is the Treaty reference value; under the 2024 rules the excessive deficit procedure "
                  "also depends on net expenditure paths, which are not shown."),
    Chart("gov-primary-balance", PAGE, "deficit", 30,
          "Balance before interest", "Euro area general government, % of GDP",
          kicker="The budget", type="bar-line", units="% of GDP", decimals=1, frequency="A",
          series=[Ref("fis_primary_a_ea", "primary", "Primary balance", "story", mark="bar"),
                  Ref("fis_balance_a__EA21", "balance", "Headline balance", "base", mark="line"),
                  Ref("fis_interest_a__EA21", "interest", "Interest expenditure", "context", mark="line")],
          reference_lines=[{"axis": "y", "value": 0, "label": ""}], default_window="max", original=True,
          what="The primary balance (the budget balance excluding interest payments) of the euro area "
               "governments, with the headline balance and the interest bill.",
          transform_text="Primary balance = net lending (B9) + interest payable (D41), both from the annual EDP "
                         "notification (gov_10dd_edpt1).",
          caveats="Interest is on an accrual basis (ESA 2010), so it moves slowly as old debt is refinanced."),
    Chart("gov-revenue-expenditure", PAGE, "deficit", 40,
          "Government revenue and spending", "Euro area general government, % of GDP, seasonally adjusted",
          kicker="The budget", units="% of GDP", decimals=1,
          series=[Ref("fis_expenditure_q", "expenditure", "Total expenditure", "story"),
                  Ref("fis_revenue_q", "revenue", "Total revenue", "base")],
          default_window="max",
          what="Total revenue and total expenditure of general government in the euro area, quarterly, as a share "
               "of GDP.",
          caveats="The gap between the two lines is the government balance."),
    Chart("gov-interest-countries", PAGE, "interest", 10,
          "Interest bills by country", "General government interest expenditure, % of GDP",
          kicker="The cost of debt", type="bar", units="% of GDP", decimals=1, frequency="A", geo="multi",
          series=_placeholder("fis_interest_a__EA21"),
          build=country_bars("fis_interest_a", "interest", "Interest expenditure", codes=COUNTRIES,
                             highlight="IT", sort="desc"),
          default_window="max", source_url=EDP_URL,
          notes="Poland is not in the euro area; shown for comparison.",
          what="Interest payable by each general government (ESA 2010 D.41), latest year of the EDP notification.",
          caveats="Accrual basis, before swaps; inflation-linked bonds add the indexation of principal to interest."),
    Chart("gov-interest-ea", PAGE, "interest", 20,
          "The euro area's interest bill", "General government interest expenditure, euro area, % of GDP, "
                                           "average of the latest four quarters",
          kicker="The cost of debt", units="% of GDP", decimals=1,
          series=[Ref("fis_interest_q", "interest", "Interest expenditure", "story", transform="roll:4")],
          default_window="max",
          what="Interest payable by euro area governments, quarterly, smoothed over four quarters.",
          transform_text="Four-quarter moving average of the unadjusted quarterly ratio to GDP (Eurostat publishes no "
                         "seasonally adjusted interest series).",
          caveats="The average of four quarterly ratios approximates, but is not identical to, the ratio of annual "
                  "sums."),
    Chart("gov-r-minus-g", PAGE, "interest", 30,
          "Interest rates against growth",
          "10-year government bond yield minus nominal GDP growth, percentage points",
          kicker="Debt dynamics", units="pp", format="pp", decimals=1, frequency="A",
          series=[Ref("fis_rg_ea", "EA", "Euro area", "base"), Ref("fis_rg_fr", "FR", "France", "story"),
                  Ref("fis_rg_it", "IT", "Italy", "context"), Ref("fis_rg_de", "DE", "Germany", "context"),
                  Ref("fis_rg_es", "ES", "Spain", "context")],
          start="2000", reference_lines=[{"axis": "y", "value": 0, "label": "r = g"}], default_window="max",
          original=True,
          notes="Below zero, nominal growth outpaces the market interest rate and debt ratios can fall even with a "
                "small primary deficit. The market yield is a marginal cost; the average rate governments pay on "
                "their stock of debt adjusts only as debt is refinanced.",
          what="The annual average 10-year government bond yield (EMU convergence series) minus the growth of "
               "nominal GDP in the same year: the snowball term of debt dynamics.",
          transform_text="r - g = 10-year yield (irt_lt_mcby_a, annual average) minus the % change of GDP at current "
                         "prices on a year earlier (nama_10_gdp, CP_MEUR). Euro area: the Eurostat 'EA' yield and "
                         "EA21 GDP.",
          caveats="An original indicator, not an official measure. The relevant rate for debt dynamics is the "
                  "effective (implicit) interest rate on the whole stock, which moves far more slowly than the "
                  "10-year yield; use this chart for direction, not to compute debt paths."),
    Chart("gov-forecast-deficit", PAGE, "forecasts", 10,
          "The Commission's deficit forecast", "Euro area general government balance, % of GDP",
          kicker="Forecast", units="% of GDP", decimals=1, frequency="A",
          series=[], build=forecast_vs_outturn("fis_balance_a__EA21", "ec_fc_balance"),
          reference_lines=REF_3, default_window="max",
          notes="The forecast line starts at the latest Eurostat outturn year.",
          what="Eurostat's annual euro area government balance and the European Commission's latest published "
               "forecast (spring or autumn economic forecast).",
          transform_text="Forecast years are those after the latest year of the Eurostat EDP series; the forecast's "
                         "own estimate for that year is shown to join the lines.",
          caveats="Forecasts assume unchanged policies (only measures adopted or credibly announced). The "
                  "Commission's euro area aggregate can differ slightly from Eurostat's EA21."),
    Chart("gov-forecast-debt", PAGE, "forecasts", 20,
          "The Commission's debt forecast", "Euro area general government gross debt, % of GDP",
          kicker="Forecast", units="% of GDP", decimals=1, frequency="A",
          series=[], build=forecast_vs_outturn("fis_debt_a__EA21", "ec_fc_debt"),
          reference_lines=REF_60, default_window="max",
          notes="The forecast line starts at the latest Eurostat outturn year.",
          what="Eurostat's annual euro area government debt ratio and the European Commission's latest published "
               "forecast.",
          transform_text="As for the deficit forecast.",
          caveats="Forecasts assume unchanged policies."),
    Chart("fiscal-table", PAGE, "countries", 10,
          "Public finances by country", "General government, % of GDP",
          kicker="Country by country", type="table", units="% of GDP", decimals=1, frequency="A",
          build=fiscal_table, source="Eurostat (gov_10dd_edpt1, gov_10q_ggdebt); European Commission (FDMS)",
          source_url=EDP_URL,
          notes="Balance: net lending (+) or borrowing (-). Primary balance excludes interest. EC forecast: the "
                "Commission's latest published economic forecast for the year after the latest outturn. Poland is "
                "not in the euro area.",
          what="Balance, primary balance, interest and gross debt for each euro area member in the latest EDP "
               "year, the latest quarterly debt ratio and the Commission's forecast for the next year.",
          transform_text="Primary balance = net lending + interest payable. Everything else as published.",
          caveats="Annual figures are from the latest EDP notification (April or October)."),
]
