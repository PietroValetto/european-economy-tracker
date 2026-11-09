"""Labour page, section "National monthly data": the national monthly counts that come out before
Eurostat's quarterly employment numbers (research/04_national_sources.md, sections 2 to 6 and 10).

Every chart shows countries side by side and never sums or averages them: the definitions differ
(ESA national-accounts employment in Germany, monthly LFS persons in Italy and the Netherlands, an
establishment survey of firms with more than nine persons in Poland, payroll jobs in France,
registered unemployment in Germany against ILO unemployment elsewhere).

Sources, all open and keyless (verified 9 Nov 2026):

* Germany: Bundesbank SDMX flow BBDL1, which mirrors Destatis (Erwerbstätige) and the Federal
  Employment Agency (registered unemployment, reported vacancies, short-time work).
* Italy: ISTAT SDMX flows 150_875 (employed) and 151_874 (unemployment rate); the release edition
  is part of the key and is discovered on every run.
* Netherlands: CBS StatLine table 80590ned (monthly labour force).
* Poland: GUS DBW API, variables 375 (average paid employment) and 376 (average gross wage) in the
  enterprise sector, published as indices on the same month a year earlier.
* France: INSEE BDM, quarterly private payroll employment flash (IDBANK 001796854).
* Spain: Seguridad Social affiliation has no working API (PX-Web API paths return 404); deferred.
"""
from .. import sources as S
from ..spec import Chart, Ref, Section, Series

PAGE = "labour"
SECTION = "national"

BBK_URL = "https://www.bundesbank.de/en/statistics/time-series-databases"
ISTAT_URL = "https://esploradati.istat.it/databrowser/"
CBS_URL = "https://opendata.cbs.nl/statline/#/CBS/nl/dataset/80590ned/table"
GUS_URL = "https://dbw.stat.gov.pl/"
INSEE_URL = "https://www.insee.fr/en/statistiques/serie/001796854"


def _bbk(sid, key, label, unit, decimals=1, scale=1.0):
    return Series(sid, "csv", dataset=S.BUNDESBANK + "BBDL1/" + key, freq="M", unit=unit, decimals=decimals,
                  start="2005-01", geo="DE", label=label, scale=scale,
                  source_name="Bundesbank (BBDL1), from Destatis and the Federal Employment Agency",
                  source_url=BBK_URL)


def _gus(sid, variable, measure, label):
    return Series(sid, "csv",
                  dataset=S.GUS_DBW + f"1.1.0/variable/variable-data-section?id-zmienna={variable}&id-przekroj=12",
                  filters={"position": 6661598, "measure": measure}, freq="M",
                  unit="index, same month a year earlier = 100", start="2019-01", geo="PL", label=label,
                  source_name="GUS (Statistics Poland), enterprise sector", source_url=GUS_URL)


SERIES = [
    _bbk("de_employment", "M.DE.Y.EMP.EAA000.A0000.A00.D10.0.ABA.A",
         "Germany, persons in employment (ESA, domestic concept), thousand, SA", "thousand", 0),
    _bbk("de_unemployment_rate", "M.DE.Y.UNE.UBA000.A0000.A01.D00.0.R00.A",
         "Germany, registered unemployment rate (BA), %, SA", "%", 1),
    _bbk("de_vacancies", "M.DE.Y.VAC.VBA000.A0000.A00.D00.0.ABA.A",
         "Germany, vacancies reported to the BA, thousand, SA", "thousand", 0),
    _bbk("de_kurzarbeit", "M.DE.Y.LMP.LKA100.A0000.A02.D00.0.ABA.A",
         "Germany, workers on cyclical short-time work (Kurzarbeit, section 96 SGB III), thousand, SA",
         "thousand", 0, scale=0.001),
    Series("it_employment", "csv", dataset=S.ISTAT + "IT1,150_875,1.0/M.IT.EMP.Y.9.Y15-89.9.9.{EDITION}",
           freq="M", unit="thousand", decimals=0, start="2004-01", geo="IT",
           label="Italy, employed persons 15 to 89 (monthly LFS), thousand, SA",
           source_name="ISTAT (150_875)", source_url=ISTAT_URL),
    Series("it_unemployment_rate", "csv", dataset=S.ISTAT + "IT1,151_874,1.0/M.IT.UNEM_R.Y.9.Y15-74.{EDITION}",
           freq="M", unit="%", decimals=1, start="2004-01", geo="IT",
           label="Italy, ILO unemployment rate 15 to 74 (monthly LFS), %, SA",
           source_name="ISTAT (151_874)", source_url=ISTAT_URL),
    Series("nl_employment", "csv", dataset=S.CBS + "80590ned",
           filters={"Geslacht": "T001038", "Leeftijd": "52052   "}, value_col="Seizoengecorrigeerd_4",
           freq="M", unit="thousand", decimals=0, start="2003-01", geo="NL",
           label="Netherlands, employed labour force 15 to 74 (monthly LFS), thousand, SA",
           source_name="CBS (80590ned)", source_url=CBS_URL),
    Series("nl_unemployment_rate", "csv", dataset=S.CBS + "80590ned",
           filters={"Geslacht": "T001038", "Leeftijd": "52052   "}, value_col="Seizoengecorrigeerd_8",
           freq="M", unit="%", decimals=1, start="2003-01", geo="NL",
           label="Netherlands, ILO unemployment rate 15 to 74 (monthly LFS), %, SA",
           source_name="CBS (80590ned)", source_url=CBS_URL),
    _gus("pl_employment_index", 375, 5, "Poland, average paid employment in the enterprise sector"),
    _gus("pl_wage_index", 376, 184, "Poland, average gross wage in the enterprise sector"),
    Series("fr_payroll", "csv", dataset=S.INSEE_BDM + "SERIES_BDM/001796854", freq="Q", unit="thousand",
           decimals=1, start="2000-Q1", geo="FR",
           label="France, private payroll employment, thousand jobs, SA",
           source_name="INSEE (BDM 001796854)", source_url=INSEE_URL),
]


def minus_100(obs):
    """GUS publishes 'same month a year earlier = 100': turn it into a % change."""
    return [(p, None if v is None else v - 100.0, f) for p, v, f in obs]


NOT_COMPARABLE = ("National definitions, shown side by side: they are not comparable in levels and are "
                  "not summed or averaged into a euro area figure.")

SECTIONS = [
    Section(PAGE, SECTION, "National monthly data",
            "There is no monthly payroll count for the euro area. These national monthly series come out "
            "weeks before Eurostat's quarterly numbers, each on its own national definition.", 50),
]

CHARTS = [
    Chart("national-employment-growth", PAGE, SECTION, 10,
          "Monthly employment counts, country by country",
          "Employment, % change on a year earlier, seasonally adjusted (Poland: unadjusted index). "
          "Germany: ESA persons in employment; Italy and the Netherlands: monthly LFS; Poland: firms with more "
          "than 9 persons",
          kicker="National data", type="country-strip",
          series=[Ref("de_employment", "DE", "Germany (Destatis, ESA employment)", "base", transform="yoy"),
                  Ref("it_employment", "IT", "Italy (ISTAT, LFS employed 15 to 89)", "base", transform="yoy"),
                  Ref("nl_employment", "NL", "Netherlands (CBS, LFS employed 15 to 74)", "base", transform="yoy"),
                  Ref("pl_employment_index", "PL", "Poland (GUS, enterprise-sector paid employment)", "base",
                      transform=minus_100)],
          start="2015-01", default_window="5y", decimals=1,
          notes=NOT_COMPARABLE + " Typical lag after the month: Netherlands about 15 days, Poland about 20, "
                "Germany and Italy about 30. Spain (Social Security affiliation) is not yet included: it has no "
                "working open API.",
          what="Year-on-year change in the monthly national employment counts of Germany, Italy, the Netherlands "
               "and Poland.",
          transform_text="Germany, Italy, Netherlands: % change of the seasonally adjusted level on the same month "
                         "a year earlier. Poland: GUS index (same month a year earlier = 100) minus 100, which GUS "
                         "computes on a comparable sample of firms.",
          caveats="German monthly employment follows the national-accounts concept (like Eurostat's namq_10_pe); "
                  "Italian and Dutch figures are survey estimates with sampling error of tens of thousands a "
                  "month; Polish data cover about 6.4 million of 17.5 million employed. ISTAT revises past months "
                  "with every release (edition)."),
    Chart("national-unemployment-rates", PAGE, SECTION, 20,
          "Monthly unemployment rates, national releases",
          "%, seasonally adjusted. Germany: registered unemployment (Federal Employment Agency); Italy and the "
          "Netherlands: ILO rate from the monthly LFS",
          kicker="National data", type="country-strip",
          series=[Ref("de_unemployment_rate", "DE", "Germany (BA, registered)", "base"),
                  Ref("it_unemployment_rate", "IT", "Italy (ISTAT, ILO 15 to 74)", "base"),
                  Ref("nl_unemployment_rate", "NL", "Netherlands (CBS, ILO 15 to 74)", "base")],
          start="2015-01", default_window="5y",
          notes=NOT_COMPARABLE + " The German registered rate is about two points above Germany's ILO rate. "
                "Typical lag: Germany 0 to 2 days after the month (count date mid-month), Netherlands about 15 "
                "days, Italy about 30.",
          what="The national monthly unemployment rates as first published by the Federal Employment Agency, "
               "ISTAT and CBS.",
          transform_text="As published.",
          caveats="Eurostat's une_rt_m carries harmonised rates for every country a few days to weeks later; use "
                  "it for comparisons across countries."),
    Chart("germany-vacancies-kurzarbeit", PAGE, SECTION, 30,
          "Germany: vacancies and short-time work",
          "Thousand, seasonally adjusted. Vacancies reported to the Federal Employment Agency; workers on "
          "cyclical short-time work (Kurzarbeit)",
          kicker="National data", units="thousand", format="level", decimals=0, geo="DE",
          series=[Ref("de_vacancies", "vacancies", "Reported vacancies", "story"),
                  Ref("de_kurzarbeit", "kurzarbeit", "Workers on cyclical short-time work", "base")],
          start="2015-01", default_window="10y",
          notes="National definitions. Vacancies are those employers report to the BA (about half of all "
                "vacancies) and are published with unemployment, about 0 to 2 days after the month. Short-time "
                "work (section 96 SGB III, realised, projected) is known only with a lag of about three months.",
          what="Two German administrative counts with no euro area counterpart: posts reported vacant to the "
               "Federal Employment Agency and workers on cyclical short-time work.",
          transform_text="As published by the Bundesbank (BBDL1), converted to thousands.",
          caveats="The 2020 short-time work peak (about 6 million) dwarfs later values; use the window buttons. "
                  "Italy's cassa integrazione and Spain's ERTE are not yet in the tracker."),
    Chart("france-payroll-employment", PAGE, SECTION, 40,
          "France: private payroll employment",
          "Private-sector payroll jobs, % change, seasonally adjusted (quarterly flash)",
          kicker="National data", type="bar-line", geo="FR",
          series=[Ref("fr_payroll", "qoq", "% change on previous quarter", "base", transform="qoq", mark="bar"),
                  Ref("fr_payroll", "yoy", "% change on a year earlier", "story", transform="yoy", mark="line")],
          start="2015-Q1", default_window="10y", decimals=1,
          notes="National definition (payroll jobs from social declarations, DSN), quarterly: France has no "
                "monthly employment count. The flash comes about 30 days after the quarter, the detailed release "
                "at about 65 days.",
          what="Growth of private-sector payroll employment in France from INSEE's quarterly flash estimate.",
          transform_text="% change of the seasonally adjusted level on the previous quarter and on a year earlier.",
          caveats="Counts jobs, not persons, and excludes the public sector and the self-employed."),
    Chart("poland-enterprise-sector", PAGE, SECTION, 50,
          "Poland: jobs and pay in the enterprise sector",
          "Firms with more than 9 persons, % change on the same month a year earlier, not seasonally adjusted",
          kicker="National data", geo="PL", decimals=1,
          series=[Ref("pl_wage_index", "wage", "Average gross wage (nominal)", "story", transform=minus_100),
                  Ref("pl_employment_index", "employment", "Average paid employment", "base",
                      transform=minus_100)],
          start="2015-01", default_window="5y",
          notes="National definitions. Published about 20 days after the month. Poland is not in the euro area; "
                "wages are in zloty and nominal.",
          what="GUS's monthly year-on-year indices of employment and of the average gross wage in the enterprise "
               "sector.",
          transform_text="GUS index (same month a year earlier = 100) minus 100.",
          caveats="The survey covers about 6.4 million workers (firms with more than nine persons); the sample of "
                  "firms changes every January."),
]
