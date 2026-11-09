"""ECB page: policy rates and €STR, where rates are heading (bond-curve forwards and the SPF
assumption), staff projections with vintages, the Eurosystem balance sheet, and the Bank Lending
Survey.

There is no free, documented source of €STR OIS forwards or futures settlements
(research/03 section 4), so the "path" chart uses instantaneous forwards on the ECB's AAA
government bond curve and says so in its subtitle and notes.
"""
from .. import periods as P
from ..context import Missing
from ..spec import Chart, Ref, Section, Series

PAGE = "ecb"


def _fm(sid, item, label):
    return Series(sid, "ecb", dataset="FM", key=f"B.U2.EUR.4F.KR.{item}.LEV", freq="D", unit="%", decimals=2,
                  start="1999-01-01", event=True, label=label)


def _yc(sid, item, label):
    return Series(sid, "ecb", dataset="YC", key=f"B.U2.EUR.4F.G_N_A.SV_C_YM.{item}", freq="D", unit="%",
                  decimals=2, start="2019-01-01", label=label)


def _bls(sid, key, label):
    return Series(sid, "ecb", dataset="BLS", key=key, freq="Q", unit="net %", decimals=0, start="2003-01",
                  label=label)


def _recent_round(code):
    """Keep MPD projection rounds from 2023 on (codes W/G/S/A + two-digit year; 99 = history)."""
    return len(code) == 3 and code[1:].isdigit() and 23 <= int(code[1:]) <= 90


ROUND_MONTH = {"W": (3, "March"), "G": (6, "June"), "S": (9, "September"), "A": (12, "December")}

SERIES = [
    _fm("dfr", "DFR", "Deposit facility rate"),
    _fm("mro", "MRR_FR", "Main refinancing operations rate"),
    _fm("mlf", "MLFR", "Marginal lending facility rate"),
    Series("estr", "ecb", dataset="EST", key="B.EU000A2X2A25.WT", freq="D", unit="%", decimals=3,
           start="2019-10-01", label="€STR"),
    _yc("fwd_6m", "IF_6M", "6 months ahead"),
    _yc("fwd_1y", "IF_1Y", "1 year ahead"),
    _yc("fwd_2y", "IF_2Y", "2 years ahead"),
    Series("spf_rate", "ecb", dataset="SPF", key="Q.U2.ASSU.IR.P3M+P6M+P9M+P12M.Q.AVG", split=4, freq="Q",
           unit="%", decimals=2, start="2020-Q1", label="SPF policy-rate assumption"),
    Series("mpd_hicp", "ecb", dataset="MPD", key="A.U2.HIC.A..0000", split=4, keep=_recent_round, freq="A",
           unit="%", decimals=1, label="Staff projection, HICP inflation"),
    Series("mpd_gdp", "ecb", dataset="MPD", key="A.U2.YER.A..0000", split=4, keep=_recent_round, freq="A",
           unit="%", decimals=1, label="Staff projection, real GDP growth"),
    Series("eurosystem_assets", "ecb", dataset="ILM", key="W.U2.C.T000000.Z5.Z01", freq="W", unit="EUR bn",
           decimals=0, scale=0.001, start="1999-01-01", label="Total assets"),
    _bls("bls_firms_standards", "Q.U2.ALL.O.E.Z.B3.ST.S.WFNET", "Credit standards (net tightening)"),
    _bls("bls_firms_demand", "Q.U2.ALL.O.E.Z.B3.ZZ.D.WFNET", "Loan demand (net increase)"),
    _bls("bls_house_standards", "Q.U2.ALL.Z.H.H.B3.ST.S.WFNET", "Credit standards (net tightening)"),
    _bls("bls_house_demand", "Q.U2.ALL.Z.H.H.B3.ZZ.D.WFNET", "Loan demand (net increase)"),
]

SECTIONS = [
    Section(PAGE, "rates", "Policy rates",
            "The deposit facility rate has been the ECB's policy rate since 2024; €STR is the overnight "
            "market rate it steers.", 10),
    Section(PAGE, "path", "Where rates are heading",
            "No free source publishes market pricing of future ECB decisions; these are the closest free "
            "proxies.", 20),
    Section(PAGE, "projections", "Staff projections",
            "The macroeconomic projections ECB and Eurosystem staff publish each quarter, round by round.", 30),
    Section(PAGE, "balance-sheet", "Balance sheet", "The size of the Eurosystem's consolidated balance sheet.", 40),
    Section(PAGE, "lending", "Bank lending survey",
            "What euro area banks report about their credit standards and the demand for loans.", 50),
]


def spf_rate_path(ctx, chart, rounds=4):
    """One series per SPF round: assumed policy rate 3, 6, 9 and 12 months after the survey."""
    panel = ctx.panel("spf_rate")
    horizons = [("P3M", 0), ("P6M", 1), ("P9M", 2), ("P12M", 3)]
    by_round = {}
    for code, offset in horizons:
        for p, v, _ in panel.get(code, []):
            rnd = P.shift(p, -offset)  # target quarter -> survey quarter
            by_round.setdefault(rnd, {})[p] = v
    complete = sorted(r for r, pts in by_round.items() if len(pts) == len(horizons))
    if not complete:
        raise Missing("no complete SPF round")
    chosen = complete[-rounds:]
    series = []
    first = P.shift(chosen[0], -4)
    dfr = ctx.apply(ctx.obs("dfr"), "resample:Q:last:ffill")
    series.append({"key": "dfr", "label": "Deposit facility rate (end of quarter)", "role": "base",
                   "points": [[p, v] for p, v, _ in dfr if p >= first]})
    for r in chosen:
        pts = by_round[r]
        y, q = r[:4], r[-1]
        series.append({"key": f"spf_{r.replace('-', '').lower()}", "label": f"Survey Q{q} {y}",
                       "role": "story" if r == chosen[-1] else "context",
                       "points": [[p, pts[p]] for p in sorted(pts)]})
    return {"series": series}


def _round_key(code):
    letter, yy = code[0], int(code[1:])
    return 2000 + yy, ROUND_MONTH[letter][0]


def projection_vintages(panel_id, rounds=4, from_year_offset=-2):
    """One series per projection round (latest = story), annual points from two years before."""
    def build(ctx, chart):
        panel = ctx.panel(panel_id)
        codes = sorted((c for c in panel if c[0] in ROUND_MONTH), key=_round_key)[-rounds:]
        if not codes:
            raise Missing("no projection rounds")
        series = []
        for c in codes:
            year, month = _round_key(c)
            start = str(year + from_year_offset)
            label = f"{ROUND_MONTH[c[0]][1]} {year}"
            pts = [[p, v] for p, v, _ in panel[c] if p >= start]
            series.append({"key": c.lower(), "label": label, "role": "story" if c == codes[-1] else "context",
                           "points": pts})
        return {"series": series}
    return build


TARGET = [{"axis": "y", "value": 2, "label": "ECB target"}]
ZERO = [{"axis": "y", "value": 0, "label": ""}]

CHARTS = [
    Chart("policy-rates", PAGE, "rates", 10,
          "ECB policy rates", "Key ECB interest rates and the euro short-term rate (€STR), %",
          kicker="Monetary policy", decimals=2,
          series=[Ref("dfr", "dfr", "Deposit facility", "story", transform="step"),
                  Ref("mro", "mro", "Main refinancing operations", "base", transform="step"),
                  Ref("mlf", "mlf", "Marginal lending facility", "context", transform="step"),
                  Ref("estr", "estr", "€STR", "context", decimals=3)],
          default_window="max",
          markers=[{"x": "2022-07-27", "label": "First hike of the 2022 cycle"},
                   {"x": "2024-06-12", "label": "First cut of the 2024 cycle"}],
          notes="Rates are drawn as steps: each value holds until the next Governing Council change. €STR "
                "starts in October 2019.",
          what="The three key ECB interest rates since 1999 and the overnight €STR.",
          transform_text="ECB change-date series expanded to steps (old value the day before each change, new "
                         "value on the day), extended to the build date.",
          caveats="Since March 2024 the MRO-DFR spread is 15 basis points; the DFR is the policy rate."),
    Chart("estr-vs-dfr", PAGE, "rates", 20,
          "Overnight rates follow the deposit rate", "€STR and the ECB deposit facility rate, %",
          kicker="Monetary policy", decimals=3,
          series=[Ref("estr", "estr", "€STR", "base", start="2022-01-01"),
                  Ref("dfr", "dfr", "Deposit facility rate", "story", transform="step", start="2022-01-01",
                      decimals=2)],
          default_window="max",
          what="The volume-weighted overnight unsecured rate banks pay (€STR) against the ECB deposit rate.",
          caveats="€STR trades a few basis points below the deposit rate because of excess liquidity."),
    Chart("rate-path-forwards", PAGE, "path", 10,
          "What the bond curve implies for short rates",
          "Instantaneous forward rates on the AAA euro area government curve, %. A bond-curve proxy, not "
          "market pricing of ECB decisions",
          kicker="Rate expectations", decimals=2,
          series=[Ref("fwd_6m", "f6m", "6 months ahead", "context", start="2022-01-01"),
                  Ref("fwd_1y", "f1y", "1 year ahead", "story", start="2022-01-01"),
                  Ref("fwd_2y", "f2y", "2 years ahead", "context", start="2022-01-01"),
                  Ref("dfr", "dfr", "Deposit facility rate", "base", transform="step", start="2022-01-01")],
          default_window="max",
          notes="These forwards come from government bonds, not from €STR swaps or futures: term premia, "
                "credit risk and bond supply push them above the expected policy rate. Read the direction, "
                "not the level.",
          what="Instantaneous forward rates 6 months, 1 year and 2 years ahead on the ECB's AAA government bond "
               "yield curve, against the deposit facility rate.",
          caveats="A rough proxy. Market-implied ECB paths (€STR OIS, Euribor and €STR futures) are licensed "
                  "data and are not used."),
    Chart("spf-rate-path", PAGE, "path", 20,
          "What forecasters assume for the policy rate",
          "ECB Survey of Professional Forecasters, assumed ECB policy rate 3 to 12 months ahead, by survey "
          "round, %",
          kicker="Rate expectations", decimals=2, frequency="Q", build=spf_rate_path,
          default_window="max",
          series=[],
          notes="Each line is one survey round, plotted at the quarter the assumption refers to. The deposit "
                "rate is the end-of-quarter value.",
          what="The mean policy-rate assumption respondents to the ECB's SPF give 3, 6, 9 and 12 months ahead, "
               "for the four most recent rounds.",
          caveats="A survey of assumptions, quarterly; not market pricing."),
    Chart("staff-projections-inflation", PAGE, "projections", 10,
          "Staff projections for inflation", "Eurosystem/ECB staff projections, HICP inflation, annual average, %",
          kicker="Projections", decimals=1, frequency="A", build=projection_vintages("mpd_hicp"),
          reference_lines=TARGET, default_window="max", series=[],
          notes="Each line is one projection round; the latest is highlighted. Years before the round are "
                "outturns as known at the time.",
          what="The HICP inflation path in the four most recent ECB (March, September) and Eurosystem (June, "
               "December) staff projection rounds.",
          caveats="Projections are conditional on market assumptions for rates, oil and the exchange rate at "
                  "the cut-off date."),
    Chart("staff-projections-growth", PAGE, "projections", 20,
          "Staff projections for growth", "Eurosystem/ECB staff projections, real GDP, % change on a year earlier",
          kicker="Projections", decimals=1, frequency="A", build=projection_vintages("mpd_gdp"),
          default_window="max", series=[],
          notes="Each line is one projection round; the latest is highlighted.",
          what="The real GDP growth path in the four most recent staff projection rounds."),
    Chart("eurosystem-balance-sheet", PAGE, "balance-sheet", 10,
          "The Eurosystem balance sheet", "Total assets of the Eurosystem, weekly, EUR billion",
          kicker="Balance sheet", units="EUR bn", format="eur_bn", decimals=0,
          series=[Ref("eurosystem_assets", "assets", "Total assets", "story")], default_window="max",
          what="Total assets in the Eurosystem's consolidated weekly financial statement.",
          transform_text="EUR millions divided by 1,000. Weekly periods are dated to the Friday of the ISO week.",
          caveats="Quarter-end revaluations of gold and foreign currency cause small jumps."),
    Chart("bls-firms", PAGE, "lending", 10,
          "Bank lending to firms", "ECB Bank Lending Survey, loans to enterprises, net percentage of banks",
          kicker="Bank lending survey", units="net %", format="level", decimals=0,
          series=[Ref("bls_firms_standards", "standards", "Credit standards (net tightening)", "story"),
                  Ref("bls_firms_demand", "demand", "Loan demand (net increase)", "base")],
          reference_lines=ZERO, default_window="max",
          what="Weighted net percentage of banks reporting tighter credit standards, and higher loan demand, "
               "over the past three months.",
          caveats="A positive standards reading means tightening; a positive demand reading means rising "
                  "demand."),
    Chart("bls-housing", PAGE, "lending", 20,
          "Bank lending for house purchase",
          "ECB Bank Lending Survey, loans to households for house purchase, net percentage of banks",
          kicker="Bank lending survey", units="net %", format="level", decimals=0,
          series=[Ref("bls_house_standards", "standards", "Credit standards (net tightening)", "story"),
                  Ref("bls_house_demand", "demand", "Loan demand (net increase)", "base")],
          reference_lines=ZERO, default_window="max",
          what="Weighted net percentage of banks reporting tighter credit standards, and higher demand, for "
               "mortgages over the past three months."),
]
