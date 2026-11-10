# Registry: how to add a series and a chart

Everything the tracker shows is declared in this folder, one Python module per section
(`home.py`, `inflation.py`, `financial.py`, `ecb.py`, ...). Modules are discovered automatically:
any `*.py` here whose name does not start with `_` is loaded. **A section module is
self-contained: you never edit core files** (`eet/*.py`) to add data or charts. Read
`CONTRACT.md` (repo root) first; this file explains the Python side only.

Run everything from `pipeline/`:

```bash
python3 -m eet.build --only labour     # fetch your module's series, build its charts
python3 -m eet.build --offline         # rebuild every bundle from store/ (no network)
python3 -m eet.check                   # validate site/data against the contract
python3 -m unittest discover -s tests  # tests (no network)
```

## The six lists a module can define

```python
from ..spec import Series, Derived, Section, Chart, Ref, Tile, Page   # or: from eet.registry import ...

SERIES   = [...]   # data to fetch and store (one request each)
DERIVED  = [...]   # series computed from other series (spreads, averages, re-indexing)
SECTIONS = [...]   # page sections your charts go into
CHARTS   = [...]   # one bundle each: site/data/charts/<id>.json
TILES    = [...]   # home-page key-indicator tiles (normally only home.py)
PAGES    = [...]   # optional: override a page's title or description
```

Ids are global. A series id may appear in two modules only if both declarations are identical;
a chart id, section `(page, id)`, tile id or derived id must be unique. The loader fails loudly
on duplicates, unknown pages, unknown series in a chart, unknown transforms and more than one
`story` series per chart.

## Series

```python
Series("unemployment_rate", "eurostat", dataset="une_rt_m",
       filters={"geo": "EA21", "s_adj": "SA", "sex": "T", "age": "TOTAL", "unit": "PC_ACT"},
       freq="M", unit="%", label="Unemployment rate", decimals=1, start="2000-01")
```

| field | meaning |
|---|---|
| `source` | `eurostat`, `ecfin` (DG ECFIN Redisstat, same JSON-stat engine, UPPERCASE dimension names), `ecb`, `bis`, `oecd`, `indeed`, `csv`, or a national family: `bundesbank`, `insee`, `cbs`, `istat`, `gus`, `indeed_wages` (see "National families" below) |
| `dataset` | Eurostat/ECFIN dataset; ECB/BIS flow (`"HICP"`); OECD `"AGENCY,DSD@DF,VERSION"`; Indeed country folder (`"EA"`); `csv` and national families: the full URL (build it from the prefixes in `eet.sources`, e.g. `sources.BUNDESBANK + "BBDL1/<key>"`) |
| `key` | SDMX series key for ECB/BIS/OECD, e.g. `"M.U2.N.XEF000.4D0.ANR"`. **One key per ECB request.** `+` is allowed only inside one dimension (`P3M+P6M`), never between whole keys |
| `filters` | Eurostat/ECFIN `{dimension: code}`; every non-time dimension must end up with exactly one code (the build checks). For `indeed`/`csv`, a row filter `{column: value}` |
| `freq` | `A`, `S` (half-years `YYYY-S1`/`YYYY-S2`, e.g. Eurostat energy prices), `Q`, `M`, `W`, `D` (weekly and daily periods are `YYYY-MM-DD`; ECB `2026-W44` is converted to that week's Friday) |
| `start` | first period requested (`sinceTimePeriod` / `startPeriod`). Never use Eurostat `lastTimePeriod`: it counts periods of the whole dataset |
| `unit`, `label`, `geo`, `decimals` | display metadata; `decimals` is the display precision used for rounding in bundles and tiles |
| `split` | makes a **panel**: Eurostat dimension name (with a list of codes in `filters`) or ECB key position (0-based, after the flow) holding a wildcard or `+`. Children are stored and referenced as `<id>__<code>`, e.g. `hicp_country__DE` |
| `keep` | optional `callable(code) -> bool` filtering panel children |
| `labels` | optional `{code: label}` for panel children (country codes get names automatically) |
| `scale` | multiply values, e.g. `0.001` for EUR millions to billions |
| `event` | `True` for change-date series (ECB policy rates). Draw them with `transform="step"` |
| `period_col`, `value_col`, `flag_col` | CSV column names when they are not `TIME_PERIOD` / `OBS_VALUE` / `OBS_STATUS` |
| `source_name`, `source_url` | override the printed source and the link (defaults: `Eurostat (une_rt_m)`, Eurostat data browser / ECB Data Portal page) |

Flags: the parsers keep the publisher's observation status (`e`, `p`, `b`, ...) as the flag, except
codes that only mean "normal value" (BIS and OECD `OBS_STATUS` `A`), which are dropped. No
section-level flag cleaning is needed.

### National families

National publishers have their own fetch logic in `eet/sources.py` (second half) and parsers in
`eet/parsers/national.py`. Name the family as the `source`; `dataset` is the full request URL.

| source | `dataset` | other fields |
|---|---|---|
| `bundesbank` | `BUNDESBANK + "<FLOW>/<KEY>"` (one series per request) | |
| `insee` | `INSEE_BDM + "SERIES_BDM/<IDBANK>"` (SDMX-ML) | |
| `cbs` | `CBS + "<table id>"` | `filters` = `{dimension: code}`, `value_col` = topic key; the update stamp comes from `TableInfos` |
| `istat` | `ISTAT + "<flow ref>/<key with {EDITION}>"` | the newest release edition is discovered on every run (about 20 to 40 s; ISTAT allows 5 calls a minute) |
| `gus` | `GUS_DBW + "...variable-data-section?id-zmienna=N&id-przekroj=M"` | `filters` = `{"position", "measure"}`; one request per month, quota 100 per 15 minutes, so a fresh store backfills over several runs |
| `indeed_wages` | `INDEED_WAGES + "<file>.csv"` | `split="jobcountry"`, `value_col` |

The store hashes these series as before they had family names (`csv`), so renaming a source never
restarts a stored history.

Rules learned the hard way (CONTRACT section 2): the euro area is `EA21` at Eurostat and `U2` at
the ECB; HICP is `prc_hicp_minr` (dimension `coicop18`) and ECB flow `HICP`; vacancies are
`jvs_q_r21` (`nace_r2_1=B-T`); one source per series. Eurostat answers a bad code with an empty
200: the build turns that into a failure naming the series, so check the log after adding one.
To discover codes, call the dataset with only `geo=EA21&lastTimePeriod=1` and read
`dimension.*.category.index`; for ECB flows, `.../service/dataflow/ECB/<FLOW>?references=all`.

## Derived series (the hook for section-local computations)

```python
from .. import transforms

def weighted_mean(de, fr, it):
    w = {"DE": 0.5, "FR": 0.3, "IT": 0.2}
    ...  # return [(period, value, flag), ...]

DERIVED = [
    Derived("spread_it_de", ["y10_country__IT", "y10_country__DE"], transforms.spread,
            freq="M", unit="pp", decimals=2, label="Italy"),
    Derived("big3_mean", ["hicp_country__DE", "hicp_country__FR", "hicp_country__IT"], weighted_mean,
            freq="M", label="Big three"),
]
```

`fn` receives the input observation lists in order and returns an observation list
(`[(period, value, flag), ...]`, sorted). An input written `"<panel>__*"` arrives as a dict
`{code: obs}`. Derived series are recomputed on every build (they are not stored) and can be
used anywhere a series id is accepted. A chart that uses a derived series is credited with its
inputs (source line, `data_updated`, methods entry), even when another chart computed it first:
no hook is needed to "read" the inputs. Put the function in your module; never edit
`transforms.py` for a one-off.

## Sections and charts

```python
SECTIONS = [Section("labour", "unemployment", "Unemployment", "One-sentence intro.", order=10)]

CHARTS = [
    Chart("unemployment-rate", "labour", "unemployment", 10,
          "Unemployment is near a record low",                     # title, sentence case
          "Euro area, % of the labour force, seasonally adjusted",  # subtitle
          kicker="Labour market",
          series=[Ref("unemployment_rate", "rate", "Unemployment rate", "story")],
          reference_lines=[{"axis": "y", "value": 6.5, "label": "2019 low"}],
          default_window="10y",
          what="What the chart shows, for methods.json.",
          transform_text="How the numbers were transformed, if at all.",
          caveats="What a reader should not over-read."),
]
```

`Chart` fields map one-to-one onto the bundle (CONTRACT section 3): `type` (`line`, `bar`,
`bar-line`, `stacked-bar`, `contrib`, `scatter`, `heatmap`, `table`, `country-strip`), `units`,
`format` (`pct`, `pp`, `index`, `eur_bn`, `level`), `decimals`, `frequency` (`A`, `S`, `Q`, `M`,
`W`, `D`; default: the first series' `freq`), `geo`, `reference_lines`, `markers`, `y_domain`, `default_window`
(`1y`/`5y`/`10y`/`max`), `total_key` (stacked/contrib), `x_label`/`y_label` (scatter),
`highlight` (categorical bars), `source`/`source_url` (default: built from the series used),
`notes`, `original` (the tracker computes the measure itself), `start` (trim every series).
`extra={...}` adds any other bundle field verbatim.

`Ref(series, key, label, role, transform=None, start=None, end=None, decimals=None, mark=None, curve=None)`:

* `role`: `story` (amber, at most one), `base` (green), `context` (muted), `band`.
* `transform`: a string from the list below, a `callable(obs)`, or `None`. Chain with `|`.
* `mark`: `"bar"` or `"line"` for `bar-line` charts. `curve`: `"step-after"` (set automatically
  when the transform contains `step`).
* For `country-strip`, use the Eurostat geo code as `key` (`"DE"`).

Transform strings (`eet/transforms.py`, all pure and tested):

| string | result |
|---|---|
| `level` | as published |
| `yoy` | % change on a year earlier (from an index); daily: as-of 365 days back |
| `mom`, `qoq`, `pct:n` | % change on the previous / n-th previous period |
| `ann3m`, `ann6m`, `ann1q`, `ann:n` | n-period change compounded to an annual rate |
| `diff:n`, `chg12m` | difference vs n periods ago; 12-month (or 4-quarter) change of a rate |
| `roll:n` | rolling mean of n periods |
| `rebase:2019` or `rebase:2019-12` | index = 100 in that year (mean) or period |
| `z:2015-01:2019-12` | z-score against that window |
| `trim:2019-01` | drop earlier periods |
| `scale:k`, `dropna` | multiply; drop nulls |
| `step` | event series to step points extended to the build date |
| `resample:Q:last:ffill` | to a lower frequency (`last`, `mean`, `first`); `ffill` for event series |

Monthly, quarterly and annual comparisons are by calendar (`2026-10` vs `2025-10`), so a missing
month gives a gap, never a wrong comparison.

### Charts that are not plain lines: the `build` hook

`build=callable(ctx, chart) -> dict` returns bundle fields to add: `series` (bundle-format dicts
with raw values: `{"key", "label", "role", "points": [[period, value], ...]}`), or `columns`
and `rows` for tables, or `rows`, `columns`, `cells`, `scale`, `midpoint` for heatmaps. The core
rounds everything afterwards. A chart whose hook returns the series needs no `Ref`s
(`series=[]`). Any other field the hook returns (`latest`, `previous`, `notes`, `subtitle`,
`highlight`, ...) replaces the core's.

Categorical bars (one bar per country) are a hook returning points labelled by category
(`[["Italy", 137.1], ...]`) plus `latest` (and `previous`) for the snapshot period: the core
computes latest/previous only for series indexed by periods. `fiscal.country_bars(panel, key,
label, codes=..., highlight="IT", sort="desc")` does all of it, including the latest common period
and a note naming late publishers.

Table columns may use format `text` (string cells, shown as written): use it for a period, a lag or
a short note instead of pushing them into headers (`international.overview_table`). `ctx` gives `ctx.obs(id)`, `ctx.panel(id)`, `ctx.apply(obs, "yoy")`,
`ctx.label(id)`, `ctx.today`; everything read through it lands in the chart's source line,
`data_updated` stamp and methods entry automatically. Raise `eet.context.Missing` if the chart
cannot be built; the previous bundle then stays on the site.

Ready-made hooks in `eet/builders.py`:

* `transform_table(columns, rows, period_from=None)`: a "bank" table, each cell the latest value
  of `(series, transform)`. Column formats: `pct`, `pp`, `index`, `level`, `eur_bn`, `change`.
  A row whose latest period differs from the table's gets the period appended to its label.
* `markets_table(rows)`: latest value vs a week and a month ago, with changes.
* `heatmap(series_ids, last_n=24, scale="diverging", midpoint=2, pin_first="EA21")`.

Examples of each are in `inflation.py` (`hicp-bank`, `hicp-flash-final`, `hicp-country-heatmap`)
and `ecb.py` (`spf-rate-path`, `staff-projections-*`, which draw one line per survey or
projection round).

## Tiles (home page strip)

`Tile(id, label, series, unit, chart_id, page, good_direction="up"|"down"|"none", transform=None,
decimals=None, order=n)`. The value, previous value, period, flag and `decimals` are computed
from the series. If a tile's series is missing on a run, the last good tile from the previous
`index.json` is kept.

## Ids already in use (do not reuse; build these charts with exactly these ids)

The home strip links to charts that other sections own. Use these ids and pages:

| chart id | page | tile | series already declared in `home.py` |
|---|---|---|---|
| `gdp-growth` | `gdp` | GDP growth | `gdp_qoq` (namq_10_gdp, CLV_PCH_PRE, SCA, B1GQ) |
| `unemployment-rate` | `labour` | Unemployment rate | `unemployment_rate` (une_rt_m) |
| `job-vacancy-rate` | `labour` | Job vacancy rate | `job_vacancy_rate` (jvs_q_r21, B-T) |
| `indeed-postings` | `labour` | Job postings | `indeed_postings_ea` (Indeed EA, total postings, SA) |
| `wage-growth` | `wages` | Negotiated wages | `negotiated_wages` (ECB INW) |
| `gov-debt` | `fiscal` | Government debt | `gov_debt` (gov_10q_ggdebt) |
| `economic-sentiment` | `europe` | Economic sentiment | `esi` (ei_bssi_m_r2, BS-ESI-I) |

Reference those series ids in your charts instead of declaring new ones for the same data.
Charts built so far: `hicp-*`, `ecb-underlying`, `inflation-expectations-*`,
`consumer-price-expectations` (inflation); `yields-*`, `yield-curve-slope`, `spreads-vs-bund`,
`ciss*`, `eur-usd`, `euro-effective-rate`, `lending-rates`, `money-credit`, `markets-table`
(financial); `policy-rates`, `estr-vs-dfr`, `rate-path-forwards`, `spf-rate-path`,
`staff-projections-*`, `eurosystem-balance-sheet`, `bls-*` (ecb); `gdp-*`, `industrial-production`,
`retail-sales`, ... (gdp); `unemployment-*`, `job-vacancy-rate`, `beveridge-curve`, `sahm-rule`,
`national-*` (labour, `labour.py` and `national_labour.py`); `wage-growth`, `real-wages`, `ecb-wage-tracker`, `indeed-wage-tracker`, `wages-table`
(wages); `gov-*`, `fiscal-table` (fiscal); `intl-*`, `ea-*`, `current-account-countries`
(international); `europe-at-a-glance`, `economic-sentiment`, `house-prices*`, `electricity-prices`,
`gas-prices`, ... (europe). Run `ls site/data/charts` for the full list. Other useful series ids:
`hicp_headline`, `hicp_core`, `hicp_country__<geo>`, `dfr`, `estr`, `yc_aaa_2y`, `yc_aaa_10y`,
`y10_country__<geo>`, `eurusd`, `neer`, `m3_growth`, `rate_mortgage`.

## Worked example: a new `labour.py`

```python
"""Labour page."""
from .. import transforms
from ..spec import Chart, Derived, Ref, Section, Series

PAGE = "labour"

SERIES = [
    Series("unemployment_youth", "eurostat", dataset="une_rt_m",
           filters={"geo": "EA21", "s_adj": "SA", "sex": "T", "age": "Y_LT25", "unit": "PC_ACT"},
           freq="M", label="Under 25", start="2000-01"),
    Series("unemployment_country", "eurostat", dataset="une_rt_m",
           filters={"s_adj": "SA", "sex": "T", "age": "TOTAL", "unit": "PC_ACT",
                    "geo": ["DE", "FR", "IT", "ES", "NL", "PL"]},
           split="geo", freq="M", start="2015-01", label="Unemployment rate by country"),
]

DERIVED = [
    Derived("youth_gap", ["unemployment_youth", "unemployment_rate"], transforms.spread,
            freq="M", unit="pp", label="Youth minus overall"),
]

SECTIONS = [Section(PAGE, "unemployment", "Unemployment", "Who is out of work.", 10)]

CHARTS = [
    Chart("unemployment-rate", PAGE, "unemployment", 10,
          "Unemployment rate", "Euro area, % of the labour force, seasonally adjusted",
          kicker="Labour market",
          series=[Ref("unemployment_rate", "total", "All ages", "story"),          # declared in home.py
                  Ref("unemployment_youth", "youth", "Under 25", "context")],
          default_window="10y", what="ILO unemployment rate, 15 to 74."),
    Chart("unemployment-countries", PAGE, "unemployment", 20,
          "Unemployment in the largest economies", "% of the labour force, SA",
          type="country-strip",
          series=[Ref(f"unemployment_country__{c}", c, role="base") for c in ["DE", "FR", "IT", "ES", "NL", "PL"]]),
]
```

Then: `python3 -m eet.build --only labour`, read the summary (every series must say `ok`), run
`python3 -m eet.check`, add a test if you wrote a non-trivial `fn` or `build`, and open the page
with `?` in the site to see it render.

## What the core does with your declarations

1. `eet.build` fetches each `Series` once (sequentially, pausing between Eurostat calls; the ECB
   gets retries with backoff for its random 504s), asserts at least one observation and caches
   the raw body in `pipeline/.cache/<source>/<id>.<ext>`.
2. `eet.store` appends new or revised observations to `store/<id>.csv` (vintages: `first_seen`,
   `last_seen`).
3. Charts are built from the store, so a failed fetch leaves the last good data in place; the
   failure is listed in `index.json` `failed` with the `chart_ids` that use the series. A
   partial (`--only`) or `--offline` build keeps the earlier failures of series it did not fetch
   live.
4. `eet.bundles` rounds, writes bundles, `index.json`, `methods.json` and `snapshot.csv`;
   `eet.check` validates them. Every file is written atomically (temp file plus rename); the
   shared files and `store/_meta.json` are rebuilt under a lock (`pipeline/.cache/build.lock`)
   from what is on disk at that moment, so two `--only` builds can run at the same time.
