"""Home page: the 12 key-indicator tiles (index.json ``strip``).

Tiles link to a chart on another page. Some of those charts are built by the GDP, labour, wages,
fiscal and Europe sections; they must use exactly these chart ids (also listed in README.md):

    gdp-growth (gdp), unemployment-rate (labour), job-vacancy-rate (labour), indeed-postings (labour),
    wage-growth (wages), gov-debt (fiscal), economic-sentiment (europe)

The series below that belong to those sections are declared here so the strip works today.
Section agents should reference these ids rather than declare duplicates (an identical
redeclaration is allowed; a different one with the same id is an error).
"""
from ..spec import Series, Tile

SERIES = [
    Series("gdp_qoq", "eurostat", dataset="namq_10_gdp",
           filters={"geo": "EA21", "unit": "CLV_PCH_PRE", "s_adj": "SCA", "na_item": "B1GQ"}, freq="Q",
           unit="% q/q", label="Real GDP, % change on the previous quarter", start="1995-Q1"),
    Series("unemployment_rate", "eurostat", dataset="une_rt_m",
           filters={"geo": "EA21", "s_adj": "SA", "sex": "T", "age": "TOTAL", "unit": "PC_ACT"}, freq="M",
           unit="%", label="Unemployment rate", start="2000-01"),
    Series("job_vacancy_rate", "eurostat", dataset="jvs_q_r21",
           filters={"geo": "EA21", "nace_r2_1": "B-T", "sizeclas": "TOTAL", "s_adj": "SA", "indic_em": "JVR"},
           freq="Q", unit="%", label="Job vacancy rate (industry, construction and services)"),
    Series("gov_debt", "eurostat", dataset="gov_10q_ggdebt",
           filters={"geo": "EA21", "sector": "S13", "na_item": "GD", "unit": "PC_GDP"}, freq="Q",
           unit="% of GDP", label="General government gross debt", start="2000-Q1"),
    Series("esi", "eurostat", dataset="ei_bssi_m_r2",
           filters={"geo": "EA21", "s_adj": "SA", "indic": "BS-ESI-I"}, freq="M", unit="index",
           label="Economic Sentiment Indicator", start="1985-01"),
    Series("negotiated_wages", "ecb", dataset="INW", key="Q.U2.N.INWR.000000.4F0.GY.IX", freq="Q", unit="% y/y",
           decimals=1, label="Negotiated wages, % change on a year earlier"),
    Series("indeed_postings_ea", "indeed", dataset="EA", filters={"variable": "total postings"}, freq="D",
           unit="index", label="Indeed job postings, euro area (1 Feb 2020 = 100, SA)", decimals=1,
           source_name="Indeed Hiring Lab"),
]

TILES = [
    Tile("gdp-qq", "GDP growth", "gdp_qoq", "% q/q", "gdp-growth", "gdp", "up", order=1),
    Tile("unemployment", "Unemployment rate", "unemployment_rate", "%", "unemployment-rate", "labour", "down",
         order=2),
    Tile("hicp", "Inflation", "hicp_headline", "% y/y", "hicp-headline-core", "inflation", "none", order=3),
    Tile("hicp-core", "Core inflation", "hicp_core", "% y/y", "hicp-headline-core", "inflation", "none", order=4),
    Tile("dfr", "ECB deposit rate", "dfr", "%", "policy-rates", "ecb", "none", decimals=2, order=5),
    Tile("yield-10y", "10-year yield (AAA)", "yc_aaa_10y", "%", "yields-aaa", "financial", "none", decimals=2,
         order=6),
    Tile("eur-usd", "EUR/USD", "eurusd", "US$ per €", "eur-usd", "financial", "none", decimals=4, order=7),
    Tile("esi", "Economic sentiment", "esi", "index, long-run average = 100", "economic-sentiment", "europe", "up",
         order=8),
    Tile("wages", "Negotiated wages", "negotiated_wages", "% y/y", "wage-growth", "wages", "none", order=9),
    Tile("job-vacancies", "Job vacancy rate", "job_vacancy_rate", "%", "job-vacancy-rate", "labour", "none",
         order=10),
    Tile("gov-debt", "Government debt", "gov_debt", "% of GDP", "gov-debt", "fiscal", "down", order=11),
    Tile("job-postings", "Job postings (Indeed)", "indeed_postings_ea", "index, Feb 2020 = 100", "indeed-postings",
         "labour", "up", order=12),
]
