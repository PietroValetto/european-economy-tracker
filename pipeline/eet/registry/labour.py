"""Labour page: unemployment, employment, slack, vacancies, job postings and worker flows.

The euro area has no monthly payrolls, no JOLTS and no weekly claims (research/02 section C), so
the page is built around: monthly unemployment (Eurostat ``une_rt_m``), quarterly employment from
the national accounts (``namq_10_pe``) and the LFS (``lfsi_emp_q``), slack (``lfsi_sla_q``), the
job vacancy rate (``jvs_q_r21``, NACE Rev. 2.1, total B-T), daily Indeed postings, LFS flows
(``lfsi_long_q``) and the European Commission's Employment Expectations Indicator. National
monthly counts are in ``national_labour.py`` (same page, section "national").
"""
from .. import geo
from .. import periods as P
from .. import builders
from ..context import Missing
from ..spec import Chart, Derived, Ref, Section, Series

PAGE = "labour"
INDEED_URL = "https://github.com/hiring-lab/job_postings_tracker"
INDEED_COUNTRIES = ["DE", "FR", "IT", "ES", "NL"]


def _lfs(sid, dataset, filters, label, unit="%", start="2000-Q1", **kw):
    f = {"geo": "EA21"}
    f.update(filters)
    return Series(sid, "eurostat", dataset=dataset, filters=f, freq="Q", unit=unit, label=label, start=start, **kw)


SERIES = [
    Series("unemployment_youth", "eurostat", dataset="une_rt_m",
           filters={"geo": "EA21", "s_adj": "SA", "sex": "T", "age": "Y_LT25", "unit": "PC_ACT"}, freq="M",
           label="Under 25", start="2000-01"),
    Series("unemployment_country", "eurostat", dataset="une_rt_m",
           filters={"s_adj": "SA", "sex": "T", "age": "TOTAL", "unit": "PC_ACT", "geo": geo.STRIP}, split="geo",
           freq="M", start="2000-01", label="Unemployment rate by country"),
    _lfs("employment_qoq", "namq_10_pe", {"s_adj": "SCA", "na_item": "EMP_DC", "unit": "PCH_PRE_PER"},
         "Employment, % q/q", unit="% q/q", start="1995-Q1"),
    _lfs("employment_yoy", "namq_10_pe", {"s_adj": "SCA", "na_item": "EMP_DC", "unit": "PCH_SM_PER"},
         "Employment, % y/y", unit="% y/y", start="1995-Q1"),
    _lfs("employment_level", "namq_10_pe", {"s_adj": "SCA", "na_item": "EMP_DC", "unit": "THS_PER"},
         "Employment, million persons", unit="million", start="1995-Q1", scale=0.001),
    _lfs("employment_rate_2064", "lfsi_emp_q",
         {"s_adj": "SA", "sex": "T", "age": "Y20-64", "unit": "PC_POP", "indic_em": "EMP_LFS"},
         "Employment rate, 20 to 64"),
    _lfs("employment_rate_2554", "lfsi_emp_q",
         {"s_adj": "SA", "sex": "T", "age": "Y25-54", "unit": "PC_POP", "indic_em": "EMP_LFS"},
         "Employment rate, 25 to 54"),
    Series("labour_slack", "eurostat", dataset="lfsi_sla_q",
           filters={"geo": "EA21", "s_adj": "SA", "sex": "T", "age": "Y15-74", "unit": "PC_ELF",
                    "wstatus": ["UNE", "UEMP_PT", "SEEK_NAVL", "NSEEK_AVL", "SLACK"]}, split="wstatus",
           labels={"UNE": "Unemployed", "UEMP_PT": "Underemployed part-time workers",
                   "SEEK_NAVL": "Seeking work but not available", "NSEEK_AVL": "Available but not seeking",
                   "SLACK": "Labour market slack"},
           freq="Q", unit="% of extended labour force", start="2009-Q1", label="Labour market slack"),
    _lfs("ltu_share", "une_ltu_q", {"indic_em": "LTU", "age": "Y15-74", "unit": "PC_UNE", "s_adj": "SA", "sex": "T"},
         "Long-term unemployed, % of unemployed", start="2009-Q1"),
    _lfs("ltu_rate", "une_ltu_q", {"indic_em": "LTU", "age": "Y15-74", "unit": "PC_ACT", "s_adj": "SA", "sex": "T"},
         "Long-term unemployment rate, % of labour force", start="2009-Q1"),
    _lfs("temporary_share", "lfsi_pt_q",
         {"s_adj": "SA", "sex": "T", "age": "Y15-64", "wstatus": "EMP_TEMP", "unit": "PC_SAL"},
         "Temporary contracts, % of employees (15 to 64)", start="2009-Q1"),
    _lfs("underemployed_pt_share", "lfsi_pt_q",
         {"s_adj": "SA", "sex": "T", "age": "Y15-74", "wstatus": "UEMP_PT", "unit": "PC_EMP"},
         "Underemployed part-time workers, % of employment (15 to 74)", start="2009-Q1"),
    _lfs("flow_e_to_u", "lfsi_long_q", {"s_adj": "SA", "sex": "T", "wstatus": "EMP_UNE", "unit": "PC_EMP"},
         "Employed to unemployed, % of employed", start="2010-Q1"),
    _lfs("flow_u_to_e", "lfsi_long_q", {"s_adj": "SA", "sex": "T", "wstatus": "UNE_EMP", "unit": "PC_UNE"},
         "Unemployed to employed, % of unemployed", start="2010-Q1"),
    Series("employment_expectations", "eurostat", dataset="ei_bsee_m_r2",
           filters={"geo": "EA21", "indic": "BS-EEI-I", "s_adj": "SA", "unit": "INX"}, freq="M",
           unit="index, long-run average = 100", label="Employment Expectations Indicator", start="1985-01"),
] + [
    Series(f"indeed_postings_{c.lower()}", "indeed", dataset=c, filters={"variable": "total postings"}, freq="D",
           unit="index", decimals=1, label=f"Indeed job postings, {geo.name(c)} (1 Feb 2020 = 100, SA)",
           source_name="Indeed Hiring Lab")
    for c in INDEED_COUNTRIES
]


def sahm(obs):
    """Sahm-rule indicator: 3-month average of the unemployment rate minus the lowest 3-month
    average of the previous 12 months, in percentage points. Needs 15 consecutive months."""
    vals = {p: v for p, v, _ in obs if v is not None}
    out = []
    for p, _, f in obs:
        window = [vals.get(P.shift(p, -k)) for k in range(3)]
        if any(w is None for w in window):
            continue
        ma = sum(window) / 3
        prior = []
        for k in range(1, 13):
            q = P.shift(p, -k)
            w = [vals.get(P.shift(q, -j)) for j in range(3)]
            if any(x is None for x in w):
                prior = None
                break
            prior.append(sum(w) / 3)
        if prior:
            out.append((p, ma - min(prior), f))
    return out


DERIVED = [
    Derived("sahm_ea", ["unemployment_rate"], sahm, freq="M", unit="pp", decimals=2,
            label="Sahm-rule indicator, euro area"),
]

SECTIONS = [
    Section(PAGE, "unemployment", "Unemployment",
            "The ILO unemployment rate is the one monthly, harmonised labour market number for the euro area.", 10),
    Section(PAGE, "employment", "Employment",
            "Employment is counted quarterly, from the national accounts and the Labour Force Survey.", 20),
    Section(PAGE, "slack", "Slack and job quality",
            "Unemployment misses people who want more hours or would work but are not searching.", 30),
    Section(PAGE, "vacancies", "Vacancies and job postings",
            "Official vacancies are quarterly and late; Indeed's postings move daily.", 40),
]


def beveridge(ctx, chart, start="2010-Q1"):
    """Scatter of the vacancy rate (y) on the unemployment rate (x), quarterly, as connected paths."""
    u = ctx.apply(ctx.obs("unemployment_rate"), "resample:Q:mean")
    v = {p: x for p, x, _ in ctx.obs("job_vacancy_rate") if x is not None}
    pts = [[p, x, v[p]] for p, x, _ in u if p >= start and p in v and x is not None]
    if not pts:
        raise Missing("no overlapping quarters")
    parts = [("pre", "2010 to 2019", "context", None, "2019-Q4"),
             ("pandemic", "2020 and 2021", "base", "2020-Q1", "2021-Q4"),
             ("recent", "2022 onwards", "story", "2022-Q1", None)]
    series = []
    for key, label, role, a, b in parts:
        seg = [pt for pt in pts if (a is None or pt[0] >= a) and (b is None or pt[0] <= b)]
        if seg:
            series.append({"key": key, "label": label, "role": role, "points": seg, "decimals": 1})
    return {"series": series}


def labour_rates_table(ctx, chart):
    """Latest value, 3 months (one quarter) ago and 12 months ago, and the 12-month change."""
    rows_spec = [
        ("Unemployment rate", "unemployment_rate"),
        ("Youth unemployment rate (under 25)", "unemployment_youth"),
        ("Sahm-rule indicator (pp)", "sahm_ea"),
        ("Job vacancy rate", "job_vacancy_rate"),
        ("Employment rate, 20 to 64", "employment_rate_2064"),
        ("Employment rate, 25 to 54", "employment_rate_2554"),
        ("Labour market slack (% of extended labour force)", "labour_slack__SLACK"),
        ("Long-term unemployed (% of unemployed)", "ltu_share"),
        ("Employment Expectations Indicator (index)", "employment_expectations"),
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
        f = P.freq_of(p)
        back3, back12 = (P.shift(p, -1), P.shift(p, -4)) if f == "Q" else (P.shift(p, -3), P.shift(p, -12))
        v3, v12 = builders.value_at(obs, back3), builders.value_at(obs, back12)
        rows.append({"label": f"{label} ({builders.period_label(p)})",
                     "values": {"latest": lp[1], "m3": v3, "m12": v12,
                                "chg": None if v12 is None else lp[1] - v12},
                     "flag": lp[2] or None, "period": p,
                     "decimals": 2 if sid == "sahm_ea" else 1})
    if not rows:
        raise Missing("no rows")
    return {"columns": [{"key": "latest", "label": "Latest", "format": "level"},
                        {"key": "m3", "label": "3 months earlier", "format": "level"},
                        {"key": "m12", "label": "12 months earlier", "format": "level"},
                        {"key": "chg", "label": "12-month change", "format": "change"}],
            "rows": rows, "latest": {"period": max((r["period"] for r in rows), key=P.compare_key),
                                     "values": {}, "flag": None}}


def reads(*sids):
    """A build hook that only reads the inputs of derived series, so the chart's source line, update
    stamp and methods entry list them (the context caches derived results)."""
    def build(ctx, chart):
        for sid in sids:
            try:
                ctx.obs(sid)
            except Missing:
                pass
        return {}
    return build


def weekly(obs):
    """Every seventh daily point, counted back from the latest (keeps country lines light)."""
    return list(reversed(list(reversed(obs))[::7]))


CHARTS = [
    Chart("unemployment-rate", PAGE, "unemployment", 10,
          "Euro area unemployment", "% of the labour force, seasonally adjusted",
          kicker="Labour market",
          series=[Ref("unemployment_rate", "total", "All ages (15 to 74)", "story"),
                  Ref("unemployment_youth", "youth", "Under 25", "context")],
          start="2000-01", default_window="10y",
          notes="Monthly figures for Germany, the Netherlands, Austria and some other countries are partly "
                "modelled from registers and the quarterly Labour Force Survey, and are revised.",
          what="ILO unemployment rate of the euro area (EA21) for all ages and for people under 25.",
          transform_text="As published (une_rt_m, SA, PC_ACT).",
          caveats="Youth unemployment rates are high partly because many young people are students and not in "
                  "the labour force: the denominator is small."),
    Chart("unemployment-countries", PAGE, "unemployment", 20,
          "Unemployment in the largest economies", "% of the labour force, seasonally adjusted",
          kicker="Labour market", type="country-strip",
          series=[Ref(f"unemployment_country__{c}", c, geo.name(c), "base") for c in geo.STRIP]
                 + [Ref("unemployment_rate", "EA21", "Euro area", "context")],
          start="2015-01", default_window="10y",
          notes="Poland is not in the euro area.",
          what="ILO unemployment rate in Germany, France, Italy, Spain, the Netherlands and Poland.",
          transform_text="As published (une_rt_m).",
          caveats="Spain's rate is structurally higher; compare changes rather than levels across countries."),
    Chart("sahm-rule", PAGE, "unemployment", 30,
          "A recession signal from unemployment", "Sahm-rule indicator for the euro area, percentage points",
          kicker="Labour market", units="pp", format="pp", decimals=2,
          series=[Ref("sahm_ea", "sahm", "Sahm-rule indicator", "story")],
          reference_lines=[{"axis": "y", "value": 0.5, "label": "US trigger (0.5)"}],
          start="2001-01", default_window="max", original=True, build=reads("unemployment_rate"),
          source="Eurostat (une_rt_m)",
          source_url="https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table",
          notes="Computed by the tracker. In the United States a reading of 0.5 or more has marked the start of "
                "every recession since 1970. In Europe short-time work schemes (Kurzarbeit, cassa integrazione, "
                "ERTE) keep workers employed in downturns, so unemployment rises later and less, and the "
                "threshold has a weaker track record.",
          what="Three-month average of the euro area unemployment rate minus its lowest three-month average over "
               "the previous twelve months.",
          transform_text="SR_t = mean(u_t, u_t-1, u_t-2) - min over k = 1..12 of mean(u_t-k, u_t-k-1, u_t-k-2), on "
                         "the seasonally adjusted monthly rate (une_rt_m).",
          caveats="A house application of Claudia Sahm's US rule, not an official indicator. Monthly unemployment "
                  "is revised, which can move the indicator after the fact."),
    Chart("long-term-unemployment", PAGE, "unemployment", 40,
          "Long-term unemployment", "Euro area, people unemployed for 12 months or more, seasonally adjusted",
          kicker="Labour market",
          series=[Ref("ltu_share", "share", "% of the unemployed", "story"),
                  Ref("ltu_rate", "rate", "% of the labour force", "base")],
          default_window="max",
          what="Share of the unemployed who have been looking for work for a year or more, and the long-term "
               "unemployment rate.",
          transform_text="As published (une_ltu_q, LTU, SA).",
          caveats="The European threshold is 12 months, against 27 weeks in the US statistics."),
    Chart("labour-rates-table", PAGE, "unemployment", 90,
          "Labour market rates", "Euro area, %, seasonally adjusted, unless stated",
          kicker="Labour market", type="table", build=labour_rates_table, decimals=1,
          source="Eurostat (une_rt_m, jvs_q_r21, lfsi_emp_q, lfsi_sla_q, une_ltu_q); European Commission "
                 "(ei_bsee_m_r2)",
          source_url="https://ec.europa.eu/eurostat/web/labour-market",
          notes="For quarterly rows, '3 months earlier' is the previous quarter and '12 months earlier' the same "
                "quarter a year before.",
          what="The latest value of the main labour market rates, a quarter earlier and a year earlier.",
          transform_text="As published; the Sahm-rule row is computed by the tracker.",
          caveats="Rows end in different months or quarters; each label states its period."),
    Chart("employment-growth", PAGE, "employment", 10,
          "Employment growth", "Euro area employment (national accounts, persons), % change, seasonally adjusted",
          kicker="Employment", type="bar-line",
          series=[Ref("employment_qoq", "qoq", "% change on previous quarter", "base", mark="bar"),
                  Ref("employment_yoy", "yoy", "% change on a year earlier", "story", mark="line")],
          start="2010-Q1", default_window="10y",
          notes="Eurostat's employment flash comes about 45 days after the quarter, with the second GDP estimate.",
          what="Growth of total employment in the euro area, domestic concept, from the quarterly national accounts.",
          transform_text="As published (namq_10_pe, EMP_DC, PCH_PRE_PER and PCH_SM_PER).",
          caveats="Counts persons, not jobs or hours; hours per worker have fallen since 2019."),
    Chart("employment-level", PAGE, "employment", 20,
          "People in work", "Euro area employment, national accounts, million persons, seasonally adjusted",
          kicker="Employment", units="million", format="level", decimals=1,
          series=[Ref("employment_level", "level", "Employment", "story")],
          start="2000-Q1", default_window="max",
          what="Total employment in the euro area (domestic concept).",
          transform_text="Thousand persons divided by 1,000.",
          caveats="The EA21 aggregate is backcast for the whole period with today's 21 members."),
    Chart("employment-rates", PAGE, "employment", 30,
          "Share of people in work", "Euro area, employed as % of the population of each age group, seasonally "
          "adjusted",
          kicker="Employment",
          series=[Ref("employment_rate_2064", "y2064", "Ages 20 to 64", "story"),
                  Ref("employment_rate_2554", "y2554", "Ages 25 to 54 (prime age)", "base")],
          default_window="max",
          reference_lines=[{"axis": "y", "value": 78, "label": "EU 2030 target (20 to 64)"}],
          what="Employment rate of people aged 20 to 64 (the EU 2030 target measure) and of prime-age adults.",
          transform_text="As published (lfsi_emp_q, EMP_LFS, PC_POP, SA).",
          caveats="The EU target of 78% applies to the EU27, shown here against the euro area rate."),
    Chart("employment-expectations", PAGE, "employment", 40,
          "What employers plan", "European Commission Employment Expectations Indicator, euro area, long-run "
          "average = 100",
          kicker="Employment", units="index", format="index",
          series=[Ref("employment_expectations", "eei", "Employment Expectations Indicator", "story")],
          reference_lines=[{"axis": "y", "value": 100, "label": "Long-run average"}],
          start="2000-01", default_window="10y",
          what="Managers' employment plans for the next three months in industry, services, retail and "
               "construction, combined into one index.",
          transform_text="As published (ei_bsee_m_r2, BS-EEI-I).",
          caveats="A survey of intentions, published before the month ends; it leads employment by a few months "
                  "but not one for one."),
    Chart("labour-slack", PAGE, "slack", 10,
          "Labour market slack", "Euro area, % of the extended labour force, ages 15 to 74, seasonally adjusted",
          kicker="Slack", type="stacked-bar", total_key="total",
          series=[Ref("labour_slack__UNE", "une", "Unemployed", "base"),
                  Ref("labour_slack__UEMP_PT", "uemp_pt", "Underemployed part-time workers", "base"),
                  Ref("labour_slack__NSEEK_AVL", "nseek_avl", "Available but not seeking", "base"),
                  Ref("labour_slack__SEEK_NAVL", "seek_navl", "Seeking but not available", "base"),
                  Ref("labour_slack__SLACK", "total", "Total slack", "story")],
          default_window="max",
          what="Eurostat's labour market slack: the unemployed plus three groups with unmet demand for work, as a "
               "share of the extended labour force. The closest European analogue of the US U-6 rate.",
          transform_text="As published (lfsi_sla_q, PC_ELF).",
          caveats="The denominator is the labour force plus the two inactive groups, so the unemployed share here "
                  "is lower than the headline unemployment rate."),
    Chart("job-quality", PAGE, "slack", 20,
          "Temporary contracts and involuntary part-time", "Euro area, seasonally adjusted",
          kicker="Slack",
          series=[Ref("temporary_share", "temporary", "Temporary contracts, % of employees (15 to 64)", "story"),
                  Ref("underemployed_pt_share", "uemp_pt", "Part-timers wanting more hours, % of employment",
                      "base")],
          default_window="max",
          what="Share of employees on temporary contracts and of workers in part-time jobs who want to work more.",
          transform_text="As published (lfsi_pt_q).",
          caveats="Temporary-contract shares depend heavily on national labour law (Spain's 2022 reform cut its "
                  "share sharply)."),
    Chart("labour-flows", PAGE, "slack", 30,
          "Moving in and out of work", "Euro area, quarterly transitions, seasonally adjusted",
          kicker="Slack",
          series=[Ref("flow_u_to_e", "u_to_e", "Unemployed finding a job, % of the unemployed", "story"),
                  Ref("flow_e_to_u", "e_to_u", "Employed losing a job, % of the employed", "base")],
          default_window="max",
          notes="Eurostat publishes seasonally adjusted flows for the euro area only from 2021; the two lines use "
                "different denominators.",
          what="Labour Force Survey flows: the share of last quarter's unemployed who are now employed and of last "
               "quarter's employed who are now unemployed.",
          transform_text="As published (lfsi_long_q, SA).",
          caveats="Worker flows from a survey, not employer-reported hires and separations as in JOLTS."),
    Chart("job-vacancy-rate", PAGE, "vacancies", 10,
          "Job vacancies", "Euro area job vacancy rate, industry, construction and services (B-T), %, "
          "seasonally adjusted",
          kicker="Vacancies",
          series=[Ref("job_vacancy_rate", "jvr", "Job vacancy rate", "story")],
          default_window="max",
          notes="Since 2026 Eurostat publishes vacancies on the NACE Rev. 2.1 classification (jvs_q_r21); the "
                "series is backcast to 2006.",
          what="Vacant posts as a share of occupied plus vacant posts.",
          transform_text="As published (jvs_q_r21, nace_r2_1 B-T, JVR, SA).",
          caveats="Published about 75 days after the quarter. Agriculture is excluded and some countries do not "
                  "cover the public sector or small firms."),
    Chart("beveridge-curve", PAGE, "vacancies", 20,
          "The Beveridge curve", "Euro area job vacancy rate against the unemployment rate, quarterly, %",
          kicker="Vacancies", type="scatter", build=beveridge, decimals=1,
          x_label="Unemployment rate, %", y_label="Job vacancy rate, %",
          original=True,
          notes="Each point is a quarter; the lines connect consecutive quarters. Moving up and left means a "
                "tighter labour market.",
          what="The relation between unemployment and vacancies since 2010.",
          transform_text="Unemployment: quarterly mean of the monthly seasonally adjusted rate (une_rt_m). "
                         "Vacancies: jvs_q_r21, B-T, SA.",
          caveats="The vacancy rate covers firms in industry, construction and services; the unemployment rate "
                  "covers the whole labour force."),
    Chart("indeed-postings", PAGE, "vacancies", 30,
          "Job postings on Indeed", "Indeed job postings index, 1 February 2020 = 100, seasonally adjusted, 7-day "
          "average",
          kicker="Job postings", units="index", format="index",
          series=[Ref("indeed_postings_ea", "EA", "Euro area", "story")]
                 + [Ref(f"indeed_postings_{c.lower()}", c, geo.name(c), "context", transform=weekly)
                    for c in INDEED_COUNTRIES],
          start="2020-02-01", default_window="5y",
          reference_lines=[{"axis": "y", "value": 100, "label": "Feb 2020"}],
          notes="Country lines are thinned to one point a week. Data run to about ten days before today.",
          what="Indeed Hiring Lab's index of the number of job postings on Indeed, euro area and five largest "
               "countries.",
          transform_text="As published (seven-day trailing average of the daily seasonally adjusted index); "
                         "country lines show every seventh day.",
          caveats="Postings on one website, not vacancies; Indeed's market share and posting practices differ by "
                  "country and change over time. CC BY 4.0, Indeed Hiring Lab."),
]
