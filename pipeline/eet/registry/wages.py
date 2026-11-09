"""Wages page: negotiated wages, the ECB wage tracker, labour costs, compensation per employee,
unit labour costs and productivity, posted wages on Indeed, and real wage growth.

The euro area has no monthly earnings series (research/02 section B4). Sources, one per series:
ECB ``INW`` (negotiated wages, the new flow; the old ``STS`` key stopped in 2025-Q3) and ``EWT``
(the ECB wage tracker, which already runs into the coming quarters because it is built from
agreements signed so far); Eurostat ``lc_lci_r2_q`` (labour cost index), ``namq_10_lp_ulc`` (unit
labour costs and productivity), ``namq_10_gdp`` and ``namq_10_pe`` (compensation of employees and
employees, for compensation per employee) and ``prc_hicp_minr`` (HICP index, for real wages);
the Indeed Hiring Lab wage tracker (posted wages, GitHub, CC BY 4.0).
"""
from .. import builders
from .. import geo
from .. import periods as P
from .. import sources as S
from .. import transforms
from ..context import Missing
from ..spec import Chart, Derived, Ref, Section, Series
from .labour import reads

PAGE = "wages"
EWT_URL = "https://data.ecb.europa.eu/data/datasets/EWT"
INDEED_WAGE_URL = "https://github.com/hiring-lab/indeed-wage-tracker"
INDEED_WAGE_COUNTRIES = ["EA", "DE", "FR", "IT", "ES", "NL", "IE"]
ULC_ITEMS = {"NULC_PER": "Unit labour costs (per person)", "NULC_HW": "Unit labour costs (per hour)",
             "RLPR_PER": "Productivity per person", "RLPR_HW": "Productivity per hour"}


def _keep_indeed(code):
    return code in INDEED_WAGE_COUNTRIES


SERIES = [
    Series("ewt_smoothed", "ecb", dataset="EWT", key="M.U2.N.WT.INWS._T.4F0.GY", freq="M", unit="% y/y",
           label="ECB wage tracker, one-off payments smoothed"),
    Series("ewt_unsmoothed", "ecb", dataset="EWT", key="M.U2.N.WT.INWR._T.4F0.GY", freq="M", unit="% y/y",
           label="ECB wage tracker, with one-off payments"),
    Series("lci_wages", "eurostat", dataset="lc_lci_r2_q",
           filters={"geo": "EA21", "s_adj": "SCA", "unit": "PCH_SM", "nace_r2": "B-S", "lcstruct": "D11"},
           freq="Q", unit="% y/y", label="Labour cost index, wages and salaries", start="2001-Q1"),
    Series("lci_total", "eurostat", dataset="lc_lci_r2_q",
           filters={"geo": "EA21", "s_adj": "SCA", "unit": "PCH_SM", "nace_r2": "B-S", "lcstruct": "D1_D4_MD5"},
           freq="Q", unit="% y/y", label="Labour cost index, total hourly labour costs", start="2001-Q1"),
    Series("ulc", "eurostat", dataset="namq_10_lp_ulc",
           filters={"geo": "EA21", "s_adj": "SCA", "unit": "PCH_SM", "na_item": list(ULC_ITEMS)}, split="na_item",
           labels=ULC_ITEMS, freq="Q", unit="% y/y", start="1996-Q1",
           label="Unit labour costs and productivity, % y/y"),
    Series("comp_employees", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "s_adj": "SCA", "unit": "CP_MEUR", "na_item": "D1"}, freq="Q", unit="EUR mn",
           decimals=0, start="1995-Q1", label="Compensation of employees, current prices"),
    Series("employees", "eurostat", dataset="namq_10_pe",
           filters={"geo": "EA21", "s_adj": "SCA", "unit": "THS_PER", "na_item": "SAL_DC"}, freq="Q",
           unit="thousand", decimals=0, start="1995-Q1", label="Employees (domestic concept)"),
    Series("hicp_index_ea", "eurostat", dataset="prc_hicp_minr",
           filters={"geo": "EA21", "unit": "I25", "coicop18": "TOTAL"}, freq="M", unit="index, 2025 = 100",
           decimals=2, start="1996-01", label="HICP, index 2025 = 100"),
    Series("indeed_wages", "csv", dataset=S.INDEED_WAGES + "main/posted-wage-growth-by-country.csv",
           split="jobcountry", keep=_keep_indeed, value_col="posted_wage_growth_yoy_3moavg", scale=100.0,
           freq="M", unit="% y/y", label="Indeed posted wage growth, 3-month average",
           labels={"EA": "Euro area"}, source_name="Indeed Hiring Lab wage tracker", source_url=INDEED_WAGE_URL),
]


def comp_per_employee_yoy(comp, emp):
    """Compensation per employee, % change on a year earlier: (D1 / employees) y/y."""
    e = {p: v for p, v, _ in emp}
    level = [(p, v / e[p], f) for p, v, f in comp if v is not None and e.get(p)]
    return transforms.yoy(level)


def hicp_quarterly_yoy(index):
    """HICP, % change of the quarterly average index on the same quarter a year earlier."""
    q = transforms.resample(index, "Q", "mean")
    counts = {}
    for p, v, _ in index:
        if v is not None:
            counts[P.to_freq(p, "Q")] = counts.get(P.to_freq(p, "Q"), 0) + 1
    q = [o for o in q if counts.get(o[0]) == 3]  # complete quarters only
    return transforms.yoy(q)


def deflate(nominal, prices):
    """Real growth: ((1 + nominal) / (1 + inflation) - 1) x 100 on the periods both have."""
    pv = {p: v for p, v, _ in prices}
    return [(p, ((1 + v / 100) / (1 + pv[p] / 100) - 1) * 100, f) for p, v, f in nominal
            if v is not None and pv.get(p) is not None]


DERIVED = [
    Derived("comp_per_employee_yoy", ["comp_employees", "employees"], comp_per_employee_yoy, freq="Q",
            unit="% y/y", label="Compensation per employee"),
    Derived("hicp_q_yoy", ["hicp_index_ea"], hicp_quarterly_yoy, freq="Q", unit="% y/y",
            label="HICP inflation, quarterly average"),
    Derived("real_negotiated_wages", ["negotiated_wages", "hicp_q_yoy"], deflate, freq="Q", unit="% y/y",
            label="Real negotiated wages"),
    Derived("real_comp_per_employee", ["comp_per_employee_yoy", "hicp_q_yoy"], deflate, freq="Q", unit="% y/y",
            label="Real compensation per employee"),
]

SECTIONS = [
    Section(PAGE, "pay", "Pay growth",
            "There is no monthly earnings survey for the euro area: these are the measures that exist, from "
            "collective agreements, labour costs and the national accounts.", 10),
    Section(PAGE, "tracker", "Where wages are heading",
            "The ECB's tracker is built from agreements already signed, so it runs ahead of the data. Indeed's "
            "posted wages are a second, independent read.", 20),
    Section(PAGE, "costs", "Labour costs and productivity",
            "Unit labour costs are pay per worker divided by output per worker: what wages mean for prices.", 30),
    Section(PAGE, "real", "Real wages", "Pay growth after inflation.", 40),
]


def ewt_chart(ctx, chart, start="2019-01"):
    """ECB wage tracker: smoothed series to the current month (story), beyond it (context, forward-looking),
    and the series with one-off payments (context). A marker shows where the forward-looking part starts."""
    sm = [o for o in ctx.obs("ewt_smoothed") if o[0] >= start and o[1] is not None]
    if not sm:
        raise Missing("no wage tracker data")
    now = P.from_date(ctx.today, "M")
    past = [[p, v] for p, v, _ in sm if p <= now]
    ahead = [[p, v] for p, v, _ in sm if p >= now]
    series = []
    if past:
        series.append({"key": "smoothed", "label": "One-off payments smoothed", "role": "story", "points": past,
                       "decimals": 1})
    if len(ahead) > 1:
        series.append({"key": "smoothed_forward", "label": "One-off payments smoothed, forward-looking",
                       "role": "context", "points": ahead, "decimals": 1})
    try:
        raw = [[p, v] for p, v, _ in ctx.obs("ewt_unsmoothed") if p >= start and v is not None]
        if raw:
            series.append({"key": "unsmoothed", "label": "Including one-off payments", "role": "context",
                           "points": raw, "decimals": 1})
    except Missing:
        pass
    out = {"series": series}
    if len(ahead) > 1:
        out["markers"] = [{"x": now, "label": "Forward-looking from here"}]
    return out


def wages_table(ctx, chart):
    """Latest, previous period and a year earlier for each pay measure (% y/y)."""
    rows_spec = [
        ("Negotiated wages", "negotiated_wages"),
        ("Compensation per employee", "comp_per_employee_yoy"),
        ("Labour cost index: wages and salaries", "lci_wages"),
        ("Labour cost index: total", "lci_total"),
        ("Unit labour costs (per person)", "ulc__NULC_PER"),
        ("Productivity per person", "ulc__RLPR_PER"),
        ("Productivity per hour", "ulc__RLPR_HW"),
        ("Indeed posted wages (3-month average)", "indeed_wages__EA"),
        ("Real negotiated wages", "real_negotiated_wages"),
        ("Real compensation per employee", "real_comp_per_employee"),
    ]
    rows = []
    for label, sid in rows_spec:
        try:
            obs = ctx.obs(sid)
        except Missing:
            continue
        lp = builders.last_point(obs)
        if not lp:
            continue
        p = lp[0]
        per_year = P.PER_YEAR.get(P.freq_of(p), 4)
        rows.append({"label": f"{label} ({builders.period_label(p)})",
                     "values": {"latest": lp[1], "previous": builders.value_at(obs, P.shift(p, -1)),
                                "year_ago": builders.value_at(obs, P.shift(p, -per_year))},
                     "flag": lp[2] or None, "period": p})
    # the wage tracker: its value for the current month (it already runs ahead)
    try:
        now = P.from_date(ctx.today, "M")
        ewt = ctx.obs("ewt_smoothed")
        v = builders.value_at(ewt, now)
        if v is not None:
            rows.insert(1, {"label": f"ECB wage tracker, smoothed ({builders.period_label(now)})",
                            "values": {"latest": v, "previous": builders.value_at(ewt, P.shift(now, -1)),
                                       "year_ago": builders.value_at(ewt, P.shift(now, -12))},
                            "flag": None, "period": now})
    except Missing:
        pass
    if not rows:
        raise Missing("no rows")
    return {"columns": [{"key": "latest", "label": "Latest", "format": "pct"},
                        {"key": "previous", "label": "Previous period", "format": "pct"},
                        {"key": "year_ago", "label": "A year earlier", "format": "pct"}],
            "rows": rows, "latest": {"period": max((r["period"] for r in rows), key=P.compare_key),
                                     "values": {}, "flag": None}}


CHARTS = [
    Chart("wage-growth", PAGE, "pay", 10,
          "Wage growth in the euro area", "% change on a year earlier",
          kicker="Wages",
          series=[Ref("negotiated_wages", "negotiated", "Negotiated wages", "story"),
                  Ref("comp_per_employee_yoy", "cpe", "Compensation per employee", "base"),
                  Ref("lci_wages", "lci", "Labour cost index, wages and salaries (hourly)", "context")],
          start="2000-Q1", default_window="10y",
          build=reads("comp_employees", "employees"),
          source="ECB (INW); Eurostat (namq_10_gdp, namq_10_pe, lc_lci_r2_q)",
          source_url="https://data.ecb.europa.eu/data/datasets/INW",
          notes="Negotiated wages come from collective agreements (ECB INW flow), about 50 days after the quarter. "
                "Compensation per employee and the labour cost index follow at about 65 and 75 days.",
          what="Three measures of pay growth: wages agreed in collective agreements, compensation per employee from "
               "the national accounts, and hourly wages and salaries from the labour cost index.",
          transform_text="Negotiated wages: as published by the ECB (INW, y/y). Compensation per employee: "
                         "compensation of employees (namq_10_gdp, D1, current prices) divided by employees "
                         "(namq_10_pe, SAL_DC), % change on a year earlier. LCI: as published (lc_lci_r2_q, D11, "
                         "PCH_SM).",
          caveats="Negotiated wages include one-off payments, which made 2024 jump. The labour cost index is "
                  "per hour, so changes in hours worked move it."),
    Chart("ecb-wage-tracker", PAGE, "tracker", 10,
          "The ECB wage tracker", "Negotiated wage growth implied by signed collective agreements, % y/y",
          kicker="Wages", build=ewt_chart, decimals=1, frequency="M",
          source="ECB (EWT)", source_url=EWT_URL,
          notes="The ECB updates the tracker about every six to eight weeks. Beyond the current month it shows only agreements already signed: it understates future "
                "pay growth as new agreements are added, so read the thin line as a floor, not a forecast.",
          what="The ECB's wage tracker: annual growth of negotiated wages implied by collective agreements in "
               "force or already signed, with and without one-off payments.",
          transform_text="As published (EWT.M.U2.N.WT.INWS._T.4F0.GY, one-off payments smoothed, and "
                         "EWT.M.U2.N.WT.INWR._T.4F0.GY). The smoothed line is split at the current month by the "
                         "tracker.",
          caveats="Built from collective agreements in a sample of large euro area countries, not from pay "
                  "actually received; wage drift and workers outside agreements are not covered."),
    Chart("indeed-wage-tracker", PAGE, "tracker", 20,
          "Wages in job ads", "Indeed posted wage growth, % y/y, 3-month average, not seasonally adjusted",
          kicker="Wages",
          series=[Ref("indeed_wages__EA", "EA", "Euro area", "story")]
                 + [Ref(f"indeed_wages__{c}", c, geo.name(c), "context") for c in INDEED_WAGE_COUNTRIES[1:]],
          start="2019-03", default_window="5y",
          notes="Published after the 15th of each month for the previous month. Ireland, the Netherlands and Spain "
                "have smaller samples.",
          what="Indeed Hiring Lab's tracker of wages advertised in job postings: the median year-on-year change in "
               "posted pay for the same job title, region and salary type.",
          transform_text="As published (posted_wage_growth_yoy_3moavg), multiplied by 100.",
          caveats="Pay offered to new hires in online ads, not pay of all workers; it tends to lead negotiated "
                  "wages. CC BY 4.0, Indeed Hiring Lab."),
    Chart("labour-cost-index", PAGE, "costs", 10,
          "Hourly labour costs", "Euro area labour cost index, industry, construction and services (B-S), "
          "% change on a year earlier, seasonally and calendar adjusted",
          kicker="Labour costs",
          series=[Ref("lci_wages", "wages", "Wages and salaries", "story"),
                  Ref("lci_total", "total", "Total labour costs", "base")],
          default_window="10y",
          what="Growth of hourly labour costs: wages and salaries and the total including employers' social "
               "contributions.",
          transform_text="As published (lc_lci_r2_q, PCH_SM, SCA).",
          caveats="Not composition-fixed like the US Employment Cost Index; shifts in the mix of jobs and in hours "
                  "move it."),
    Chart("unit-labour-costs", PAGE, "costs", 20,
          "Unit labour costs", "Euro area, labour cost per unit of output, % change on a year earlier",
          kicker="Labour costs",
          series=[Ref("ulc__NULC_PER", "per_person", "Per person employed", "story"),
                  Ref("ulc__NULC_HW", "per_hour", "Per hour worked", "base")],
          start="2000-Q1", default_window="10y",
          what="Nominal unit labour costs: compensation per employee relative to real output per person (or per "
               "hour).",
          transform_text="As published (namq_10_lp_ulc, NULC_PER and NULC_HW, PCH_SM).",
          caveats="A rise means labour costs grow faster than productivity; firms either pass it on into prices "
                  "or absorb it in margins."),
    Chart("productivity", PAGE, "costs", 30,
          "Labour productivity", "Euro area real output per person and per hour worked, % change on a year earlier",
          kicker="Labour costs",
          series=[Ref("ulc__RLPR_HW", "per_hour", "Per hour worked", "story"),
                  Ref("ulc__RLPR_PER", "per_person", "Per person employed", "base")],
          start="2000-Q1", default_window="10y",
          what="Growth of real GDP per person employed and per hour worked.",
          transform_text="As published (namq_10_lp_ulc, RLPR_PER and RLPR_HW, PCH_SM).",
          caveats="Whole-economy productivity, including the public sector, where output is measured mostly by "
                  "inputs. Short-time work in 2020 made per-person and per-hour productivity diverge."),
    Chart("real-wages", PAGE, "real", 10,
          "Real wage growth", "Euro area, pay growth deflated by HICP inflation, % change on a year earlier",
          kicker="Wages",
          series=[Ref("real_negotiated_wages", "negotiated", "Real negotiated wages", "story"),
                  Ref("real_comp_per_employee", "cpe", "Real compensation per employee", "base")],
          start="2001-Q1", default_window="10y", original=True,
          build=reads("negotiated_wages", "comp_employees", "employees", "hicp_index_ea"),
          source="ECB (INW); Eurostat (namq_10_gdp, namq_10_pe, prc_hicp_minr)",
          source_url="https://data.ecb.europa.eu/data/datasets/INW",
          reference_lines=[{"axis": "y", "value": 0, "label": "No real growth"}],
          what="Negotiated wages and compensation per employee after inflation.",
          transform_text="((1 + nominal growth) / (1 + HICP inflation) - 1) x 100, where HICP inflation is the "
                         "% change of the quarterly average HICP index (prc_hicp_minr, EA21) on a year earlier.",
          caveats="HICP is a consumer price index; deflating by the GDP deflator instead gives the real cost to "
                  "employers, which moved differently in the 2022 energy shock."),
    Chart("wages-table", PAGE, "pay", 90,
          "Pay measures at a glance", "Euro area, % change on a year earlier",
          kicker="Wages", type="table", build=wages_table, decimals=1,
          source="ECB (INW, EWT); Eurostat (lc_lci_r2_q, namq_10_lp_ulc, namq_10_gdp, namq_10_pe, prc_hicp_minr); "
                 "Indeed Hiring Lab",
          source_url="https://data.ecb.europa.eu/data/datasets/INW",
          notes="Each row states its own latest period. 'Previous period' is the previous quarter or month.",
          what="The latest reading of each pay, labour cost and productivity measure.",
          transform_text="As in the charts above; real rows are computed by the tracker.",
          caveats="The wage tracker row shows the current month of a forward-looking series."),
]
