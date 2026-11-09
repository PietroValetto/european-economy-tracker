"""Financial conditions page: euro area yield curve, country yields and spreads, stress, the euro,
the cost and growth of credit, and a markets table.

Daily market series come from the ECB Data Portal (one key per request). Country 10-year yields
are Eurostat's monthly convergence-criterion yields (``irt_lt_mcby_m``): daily country yields need
a market data vendor.
"""
from .. import builders, transforms
from ..spec import Chart, Derived, Ref, Section, Series

PAGE = "financial"


def _yc(sid, item, label, curve="G_N_A", start="2004-09-01"):
    return Series(sid, "ecb", dataset="YC", key=f"B.U2.EUR.4F.{curve}.SV_C_YM.{item}", freq="D", unit="%",
                  label=label, decimals=2, start=start)


YIELD_COUNTRIES = ["DE", "FR", "IT", "ES", "NL", "PT", "EL", "BE", "AT"]
SPREAD_COUNTRIES = ["IT", "FR", "ES", "PT", "EL", "BE"]
SPREAD_NAMES = {"IT": "Italy", "FR": "France", "ES": "Spain", "PT": "Portugal", "EL": "Greece", "BE": "Belgium"}

SERIES = [
    _yc("yc_aaa_2y", "SR_2Y", "2-year"),
    _yc("yc_aaa_10y", "SR_10Y", "10-year"),
    _yc("yc_all_10y", "SR_10Y", "10-year, all euro area governments", curve="G_N_C", start="2024-01-01"),
    Series("y10_country", "eurostat", dataset="irt_lt_mcby_m",
           filters={"int_rt": "MCBY", "geo": YIELD_COUNTRIES}, split="geo", freq="M", unit="%", decimals=2,
           start="1999-01", label="10-year government bond yield (EMU convergence criterion)"),
    Series("ciss_ea", "ecb", dataset="CISS", key="D.U2.Z0Z.4F.EC.SS_CIN.IDX", freq="D", unit="index",
           decimals=3, start="1999-01-01", label="Euro area"),
] + [
    Series(f"ciss_{c.lower()}", "ecb", dataset="CISS", key=f"D.{c}.Z0Z.4F.EC.SS_CIN.IDX", freq="D",
           unit="index", decimals=3, start="2015-01-01", label=name)
    for c, name in (("DE", "Germany"), ("FR", "France"), ("IT", "Italy"), ("ES", "Spain"))
] + [
    Series("eurusd", "ecb", dataset="EXR", key="D.USD.EUR.SP00.A", freq="D", unit="US$ per euro", decimals=4,
           start="1999-01-01", label="EUR/USD"),
    Series("neer", "ecb", dataset="EXR", key="M.E03.EUR.EN00.A", freq="M", unit="index", decimals=1,
           start="1999-01", label="Nominal effective exchange rate (EER-41)"),
    Series("neer_daily", "ecb", dataset="EXR", key="D.E03.EUR.EN00.A", freq="D", unit="index", decimals=2,
           start="2024-01-01", label="Nominal effective exchange rate (EER-41), daily"),
    Series("rate_mortgage", "ecb", dataset="MIR", key="M.U2.B.A2C.AM.R.A.2250.EUR.N", freq="M", decimals=2,
           start="2003-01", label="Loans to households for house purchase"),
    Series("rate_firms", "ecb", dataset="MIR", key="M.U2.B.A2I.AM.R.A.2240.EUR.N", freq="M", decimals=2,
           start="2003-01", label="Loans to non-financial corporations"),
    Series("m3_growth", "ecb", dataset="BSI", key="M.U2.Y.V.M30.X.I.U2.2300.Z01.A", freq="M", decimals=1,
           start="1999-01", label="M3"),
    Series("loans_hh_growth", "ecb", dataset="BSI", key="M.U2.Y.U.A20T.A.I.U2.2250.Z01.A", freq="M",
           decimals=1, start="2004-01", label="Loans to households (adjusted)"),
    Series("loans_nfc_growth", "ecb", dataset="BSI", key="M.U2.Y.U.A20T.A.I.U2.2240.Z01.A", freq="M",
           decimals=1, start="2004-01", label="Loans to firms (adjusted)"),
]


def _spread_fn(a, b):
    return transforms.spread(a, b)


DERIVED = [
    Derived("yc_slope_10y2y", ["yc_aaa_10y", "yc_aaa_2y"], _spread_fn, freq="D", unit="pp", decimals=2,
            label="10-year minus 2-year"),
] + [
    Derived(f"spread_{c.lower()}_de", [f"y10_country__{c}", "y10_country__DE"], _spread_fn, freq="M", unit="pp",
            decimals=2, label=SPREAD_NAMES[c])
    for c in SPREAD_COUNTRIES
]

SECTIONS = [
    Section(PAGE, "rates", "Government bond yields",
            "The euro area yield curve, and what each government pays to borrow for ten years.", 10),
    Section(PAGE, "stress", "Financial stress",
            "The ECB's composite indicator of systemic stress across money, bond, equity and currency markets.", 20),
    Section(PAGE, "fx", "The euro", "The euro against the dollar and against a basket of trading partners.", 30),
    Section(PAGE, "credit", "Money and credit",
            "What households and firms pay to borrow, and how fast money and bank lending are growing.", 40),
    Section(PAGE, "markets", "Markets at a glance", "Latest readings against a week and a month ago.", 50),
]

CHARTS = [
    Chart("yields-aaa", PAGE, "rates", 10,
          "Euro area government bond yields", "Yields on AAA-rated euro area government bonds, %",
          kicker="Bond markets",
          series=[Ref("yc_aaa_2y", "y2", "2-year", "base"), Ref("yc_aaa_10y", "y10", "10-year", "story")],
          default_window="5y", decimals=2,
          what="Spot yields at 2 and 10 years on the ECB's estimated yield curve for AAA-rated euro area "
               "central government bonds (Svensson model), daily.",
          caveats="A fitted curve, not a single bond. The AAA set changes when ratings change."),
    Chart("yield-curve-slope", PAGE, "rates", 20,
          "Slope of the yield curve", "10-year minus 2-year yield, AAA euro area curve, percentage points",
          kicker="Bond markets", units="pp", format="pp", decimals=2,
          series=[Ref("yc_slope_10y2y", "slope", "10-year minus 2-year", "story")],
          reference_lines=[{"axis": "y", "value": 0, "label": "Flat curve"}], default_window="10y",
          what="Difference between the 10-year and 2-year spot yields on the AAA euro area curve.",
          transform_text="10-year yield minus 2-year yield on the same day."),
    Chart("yields-by-country", PAGE, "rates", 30,
          "Ten-year yields by country", "Long-term government bond yields, monthly average, %",
          kicker="Bond markets", decimals=2,
          series=[Ref("y10_country__DE", "DE", "Germany", "base"),
                  Ref("y10_country__FR", "FR", "France", "story"),
                  Ref("y10_country__IT", "IT", "Italy", "context"),
                  Ref("y10_country__ES", "ES", "Spain", "context"),
                  Ref("y10_country__NL", "NL", "Netherlands", "context")],
          default_window="10y",
          what="Ten-year benchmark government bond yields used for the EMU convergence criterion, monthly "
               "averages.",
          caveats="Monthly averages of daily yields, so the latest month lags market moves."),
    Chart("spreads-vs-bund", PAGE, "rates", 40,
          "Spreads over the German Bund", "10-year government bond yield minus Germany's, percentage points",
          kicker="Fragmentation", units="pp", format="pp", decimals=2,
          series=[Ref(f"spread_{c.lower()}_de", c, SPREAD_NAMES[c],
                      "story" if c == "FR" else ("base" if c == "IT" else "context"))
                  for c in SPREAD_COUNTRIES],
          default_window="10y", original=True,
          what="The extra yield investors demand to hold each government's 10-year bonds rather than "
               "Germany's.",
          transform_text="Country 10-year yield minus the German 10-year yield, monthly averages "
                         "(Eurostat irt_lt_mcby_m).",
          caveats="Monthly averages; intra-month spikes are smoothed out."),
    Chart("ciss", PAGE, "stress", 10,
          "Systemic stress in euro area markets", "Composite Indicator of Systemic Stress (CISS), 0 to 1",
          kicker="Financial stress", units="index", format="index", decimals=3,
          series=[Ref("ciss_ea", "ea", "Euro area", "story")], default_window="10y",
          what="The ECB's CISS combines stress measures from money, bond, equity, financial intermediary and "
               "foreign exchange markets, weighted by how correlated they are.",
          caveats="A higher reading means more stress; the scale is bounded between 0 and 1."),
    Chart("ciss-countries", PAGE, "stress", 20,
          "Financial stress by country", "Country Composite Indicators of Systemic Stress, 0 to 1",
          kicker="Financial stress", units="index", format="index", decimals=3,
          series=[Ref("ciss_de", "DE", "Germany", "base"), Ref("ciss_fr", "FR", "France", "story"),
                  Ref("ciss_it", "IT", "Italy", "context"), Ref("ciss_es", "ES", "Spain", "context")],
          default_window="5y",
          what="The ECB's country-level CISS for the four largest euro area economies."),
    Chart("eur-usd", PAGE, "fx", 10,
          "The euro against the dollar", "ECB euro reference rate, US dollars per euro",
          kicker="The euro", units="US$", format="level", decimals=4,
          series=[Ref("eurusd", "eurusd", "EUR/USD", "story")], default_window="5y",
          what="The ECB's daily euro foreign exchange reference rate against the US dollar, set around 14:10 CET.",
          caveats="A rise means a stronger euro."),
    Chart("euro-effective-rate", PAGE, "fx", 20,
          "The euro against its trading partners",
          "Nominal effective exchange rate of the euro, 41 partners, index 1999 Q1 = 100",
          kicker="The euro", units="index", format="index", decimals=1,
          series=[Ref("neer", "neer", "Nominal effective exchange rate", "story")], default_window="10y",
          what="Trade-weighted average of the euro against the currencies of 41 trading partners, monthly "
               "average.",
          caveats="A rise means a stronger euro."),
    Chart("lending-rates", PAGE, "credit", 10,
          "What it costs to borrow from banks",
          "Composite cost of borrowing, new loans, euro area, %",
          kicker="Credit", decimals=2,
          series=[Ref("rate_mortgage", "mortgage", "Loans for house purchase", "story"),
                  Ref("rate_firms", "firms", "Loans to firms", "base")],
          default_window="10y",
          what="The ECB's composite cost-of-borrowing indicators for new bank loans to households for house "
               "purchase and to non-financial corporations.",
          caveats="Averages across very different national markets: fixed-rate mortgages dominate in Germany and "
                  "France, variable rates in Spain, Italy and Portugal."),
    Chart("money-credit", PAGE, "credit", 20,
          "Money and bank lending growth", "Euro area, % change on a year earlier",
          kicker="Credit",
          series=[Ref("m3_growth", "m3", "M3", "story"),
                  Ref("loans_hh_growth", "households", "Loans to households", "base"),
                  Ref("loans_nfc_growth", "firms", "Loans to firms", "context")],
          default_window="10y",
          what="Annual growth of the broad money aggregate M3 and of bank loans to households and to "
               "non-financial corporations.",
          caveats="Loans are adjusted for sales, securitisation and cash pooling (ECB definition)."),
    Chart("markets-table", PAGE, "markets", 10,
          "Markets at a glance", "Latest daily readings, with values a week and a month earlier",
          kicker="Markets", type="table", units="", format="level", decimals=2,
          build=builders.markets_table([
              ("Euro short-term rate (€STR), %", "estr", 3, "level"),
              ("2-year yield, AAA curve, %", "yc_aaa_2y", 2, "level"),
              ("10-year yield, AAA curve, %", "yc_aaa_10y", 2, "level"),
              ("10-year yield, all governments, %", "yc_all_10y", 2, "level"),
              ("Curve slope, 10y minus 2y, pp", "yc_slope_10y2y", 2, "level"),
              ("EUR/USD", "eurusd", 4, "pct"),
              ("Euro effective exchange rate", "neer_daily", 2, "pct"),
              ("Systemic stress (CISS)", "ciss_ea", 3, "level"),
          ]),
          source="ECB Data Portal (EST, YC, EXR, CISS)", source_url="https://data.ecb.europa.eu/",
          notes="Changes are in percentage points for rates and in % for exchange rates (column 'change_unit' "
                "on each row). Equity indices, oil and gas prices need licensed data and are not shown.",
          what="Latest values of the main free daily euro area market series and their changes over a week "
               "and a month.",
          transform_text="Value on the latest date against the last value on or before 7 and 30 calendar days "
                         "earlier."),
]
