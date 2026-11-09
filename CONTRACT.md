# European Economy Tracker: build contract

This file is the shared agreement between the data pipeline and the website. Every agent working
on this repo reads it first. If you need to change it, say so in your report instead of editing it
silently.

Product name: **European Economy Tracker**, by Popular Economics.
Public URL (GitHub Pages project site): `https://pietrovaletto.github.io/european-economy-tracker/`.
Because the site lives under a sub-path, **every URL inside `site/` is relative**. Never write a
link, fetch or `src` that starts with `/`.

Research behind every decision: `~/Library/CloudStorage/Dropbox/Popular Economics/07 Ideas & Series/EU EconVitals/`
(top-level report plus `research/01..05`). Read the parts your brief points to.

## 1. Repo layout and ownership

| Path | What | Owner |
|---|---|---|
| `pipeline/eet/` | Python package `eet`: fetchers, parsers, transforms, store, bundle writer, build entry point | core pipeline |
| `pipeline/eet/registry/<section>.py` | One module per section: the series it pulls and the charts it builds | one agent per section |
| `pipeline/tests/` | `unittest` tests, run with `python3 -m unittest discover -s pipeline/tests` | whoever adds code |
| `pipeline/seed/pull_eu_vitals.py` | The verified seed script from the research. Reference only, do not import | nobody |
| `store/` | Committed vintage store (tidy CSV per series). Survives CI runs | written by the pipeline |
| `site/` | The static website, deployed as-is. No build step | site frontend |
| `site/data/` | **Generated** by the pipeline. Never hand-edit | pipeline |
| `site/_fixtures/` | Hand-made sample bundles that follow this contract, for building the site before real data exists | site frontend |
| `lfs/` | Plan and results drop-folder for Pietro's local Labour Force Survey analyses. No microdata here, ever | plan only for now |
| `.github/workflows/` | CI: daily build, release-morning polling, Pages deploy | ops |
| `ROADMAP.md` | Planned work that is not built yet | ops / lead |

Python is **standard library only** (3.11+; CI uses 3.12). No pandas, no requests. Raw HTTP
responses go to `pipeline/.cache/` (git-ignored).

## 2. Data rules learned in the research (do not relearn them)

- The euro area is `EA21` in Eurostat (Bulgaria joined 1 Jan 2026) and `U2` in ECB keys. `EA20` returns empty data.
- HICP moved to ECOICOP v2: use Eurostat `prc_hicp_minr` (dimension `coicop18`), `prc_hicp_fpd` (flash vs final), `prc_hicp_ctr` (contributions); ECB flow `HICP` (not `ICP`). Old datasets stop at 2025-12.
- Job vacancies: `jvs_q_r21`, dimension `nace_r2_1`, total `B-T`. Negotiated wages: ECB flow `INW`. Wage tracker: `EWT`.
- Eurostat never errors on a bad code: it returns HTTP 200 with an empty dimension. **Every series must assert at least one observation**, and the build must fail loudly naming the series.
- Eurostat `lastTimePeriod=N` counts periods of the whole dataset; prefer `sinceTimePeriod`.
- ECB API: one key per request, 60 s timeout, retry with backoff on 5xx and timeouts (random 504s at 30 s). Do not OR whole keys with `+`.
- IMF rejects custom User-Agents; send a plain one.
- Use **one source per series** (ECB HICP and Eurostat flash can differ by 0.1 on the same month). Record which.

## 3. Chart bundle: `site/data/charts/<chart_id>.json`

`chart_id` is kebab-case, unique, stable (it becomes a URL anchor).

```json
{
  "id": "hicp-headline-core",
  "page": "inflation",
  "section": "headline",
  "order": 10,
  "title": "Inflation is above the 2% target",
  "kicker": "Consumer prices",
  "subtitle": "Euro area HICP, % change on a year earlier",
  "type": "line",
  "units": "%",
  "frequency": "M",
  "geo": "EA21",
  "series": [
    {"key": "headline", "label": "Headline", "role": "base",
     "points": [["2024-01", 2.8], ["2024-02", 2.6]],
     "flags": {"2026-10": "e"}},
    {"key": "core", "label": "Core (ex energy, food, alcohol, tobacco)", "role": "story",
     "points": [["2024-01", 3.3], ["2024-02", 3.1]]}
  ],
  "latest": {"period": "2026-10", "values": {"headline": 4.0, "core": 2.6}, "flag": "e"},
  "previous": {"period": "2026-09", "values": {"headline": 3.8, "core": 2.5}},
  "reference_lines": [{"axis": "y", "value": 2, "label": "ECB target"}],
  "markers": [{"x": "2022-07", "label": "First ECB hike"}],
  "y_domain": null,
  "default_window": "5y",
  "source": "Eurostat, HICP (prc_hicp_minr)",
  "source_url": "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table",
  "notes": "Flash estimate for the latest month (flag e).",
  "methods_id": "hicp-headline-core",
  "original": false,
  "data_updated": "2026-10-31T10:00:00+0100",
  "built_at": "2026-11-09T06:00:00Z"
}
```

Field rules:

- `type` is one of the renderer's chart types (section 6).
- `series[].points` is a list of `[period, value]`. `value` is a number or `null` (a known gap: the renderer breaks the line). Periods use the source's own format: `YYYY` annual, `YYYY-Qn` quarterly, `YYYY-MM` monthly, `YYYY-MM-DD` daily or weekly. All points in one series share one frequency.
- `series[].role`: `story` (the series the chart is about: drawn in amber, **at most one per chart**), `base` (green), `context` (slate or mute, thinner), `band` (two-value range drawn as an area: then `points` are `[period, low, high]`).
- For `type: "stacked-bar"` or `"contrib"`, add `"total_key"` naming the series drawn as a line or dot on top of the stack.
- For `type: "scatter"` (for example a Beveridge curve), points are `[period, x, y]` and the bundle adds `"x_label"` and `"y_label"`.
- For `type: "heatmap"`, the bundle carries `"rows"` (country or item labels, in display order), `"columns"` (periods or indicator names) and `"cells"`: `[[row_index, column_index, value], ...]`, plus `"scale": "diverging"` or `"sequential"` and an optional `"midpoint"`.
- For `type: "table"`, the bundle carries `"columns": [{"key","label","format"}]` and `"rows": [{"label": "...", "values": {...}, "flag": null}]`; `series` may be empty.
- For `type: "country-strip"` (small multiples, one panel per country), `series[]` has one entry per country with `"key"` = Eurostat geo code and `"label"` = country name; the story country (if any) has role `story`.
- `latest` and `previous` are what the key-indicator tile and the "latest value" label show. Values are already rounded for display by the pipeline (`decimals` below).
- Optional `"decimals": 1` (display precision, default 1) and `"format": "pct" | "pp" | "index" | "eur_bn" | "level"`.
- Optional `series[].mark`: `"bar"` or `"line"`. For `bar-line`, it says which series are bars (default: the first series is bars, the rest lines).
- Optional `series[].curve`: `"step-after"` for policy rates and other step series (default: linear).
- Categorical bars (for example debt by country): `points` may use category labels instead of periods (`[["Italy", 137.1], ...]`), with an optional bundle-level `"highlight": "IT"` naming the one bar drawn in amber.
- Table `columns[].format` is one of `pct`, `pp`, `index`, `level`, `eur_bn`, `change` (`pp` and `change` are shown signed). Rows may carry `"decimals"`.
- `original: true` marks a measure the tracker computes itself (it shows an "Original" tag and links to its methods entry).
- `data_updated` is the publisher's own update stamp (Eurostat `updated`, ECB `Last-Modified`). `built_at` is the pipeline run time as an ISO timestamp in `UTC` (suffix `Z`).

## 4. Index: `site/data/index.json`

```json
{
  "schema": 1,
  "built_at": "2026-11-09T06:00:00Z",
  "pages": [
    {"id": "inflation", "title": "Inflation", "path": "inflation/",
     "description": "Consumer prices in the euro area: headline, core, services and the ECB's underlying measures.",
     "sections": [
       {"id": "headline", "title": "Headline and core", "intro": "One or two sentences.",
        "charts": ["hicp-headline-core", "hicp-components"], "tables": ["hicp-bank"]}
     ]}
  ],
  "strip": [
    {"id": "gdp-qq", "label": "GDP growth", "value": 0.4, "unit": "% q/q", "period": "2026-Q3",
     "previous": 0.6, "decimals": 1, "good_direction": "up", "chart_id": "gdp-growth", "page": "gdp", "flag": null}
  ],
  "countries": ["DE", "FR", "IT", "ES", "NL", "PL"],
  "failed": [{"id": "some-series", "error": "empty response", "chart_ids": ["chart-that-uses-it"]}]
}
```

- Page ids and their order are fixed: `home` (no entry in `pages`; it is `site/index.html`), `gdp`, `labour`, `wages`, `inflation`, `financial`, `ecb`, `fiscal`, `international`, `europe` (European-only indicators: fragmentation, energy, surveys), `calendar`, `methods`, `about`. A page whose sections are all empty shows a short "Coming soon" note rather than disappearing.
- `strip` holds the 12 key-indicator tiles for the home page, in display order. `good_direction` is `up`, `down` or `none` and colours the change arrow.
- `failed` lists series that could not be built on this run; the site shows the last good bundle and a quiet "not updated" mark.

## 5. Other generated files in `site/data/`

| File | Content |
|---|---|
| `methods.json` | `{"entries": [{"id", "title", "what", "transform", "sources": [{"name","dataset","url"}], "frequency", "caveats", "original", "updated"}]}`, one entry per chart (`methods_id`) |
| `calendar.json` | `{"built_at", "events": [{"date": "2026-11-13", "time": "11:00", "tz": "Europe/Brussels", "title", "publisher", "tier": 1, "datasets": ["namq_10_gdp"], "chart_ids": [...]}]}`, from today to +45 days |
| `snapshot.csv` | Flat table of every strip value, for reuse in newsletters |
| `lfs/<analysis_id>.json` | Future: results of Pietro's local LFS analyses, same bundle shape as charts, `original: true`, plus `"lfs_vintage"`. Not built now |

## 6. Website rules (`site/`)

- No build step. Vanilla HTML, CSS and ES modules. Charts with **Observable Plot 0.6.16** and **d3 7.9.0** from `https://cdn.jsdelivr.net/npm/` (exact versions pinned).
- One HTML file per page: `site/index.html` (home) and `site/<page>/index.html`. Shared JS in `site/assets/js/`, shared CSS in `site/assets/css/`. Each page's HTML is a thin shell; the JS renders sections from `data/index.json` and the chart bundles, so **adding a chart needs no site change**.
- Data base path: pages compute it from their depth (a `<meta name="eet-root" content="../">` tag in each page). Append `?fixtures=1` to load `_fixtures/` instead of `data/`.
- Brand: Popular Economics design system (copied into `site/assets/brand/`). Archivo for headlines and numbers (700/800, negative tracking), Inter for body and UI. Paper `#FAF7F0` ground, ink `#1B1712` text, slate `#6B655C` secondary, mute `#A8A296` sources. Green `#1F8A5B` is the base series and accent; **amber `#F0A93B` appears once per chart**, on the story series. Hairlines (`rgba(27,23,18,.08/.12/.22)`) instead of boxes; no gradients, no shadows inside the page, no animation on load. Kicker, sentence-case headline, 52x5px amber rule, subtitle is the signature for page headers. Sentence case everywhere; the only uppercase is the small kicker.
- Chart furniture: kicker, title, subtitle, the chart, then a source line in mute type. Latest-value label at the end of each line. Window buttons (1y, 5y, 10y, max). Download PNG and Copy link per chart. Accessible: every chart gets a text alternative generated from its bundle (title, latest values, period).
- Responsive down to 360px width, 16px side gutter, no horizontal page scroll. Tables scroll inside their own container.
- Chart types the renderer must support: `line`, `bar`, `bar-line`, `stacked-bar`, `contrib`, `scatter`, `heatmap`, `table`, `country-strip`.
- Footer on every page: "European Economy Tracker by Popular Economics", links to Substack (`https://populareconomics.substack.com/`), methods and about, "Data: Eurostat, ECB, European Commission and others. Built automatically; may contain errors."

## 7. Definition of done for any change

- `python3 -m unittest discover -s pipeline/tests` passes.
- `python3 -m eet.build` (run from `pipeline/`) completes; a failed series is listed in `index.json` `failed` and in the exit summary, and the process exits non-zero only if more than 20% of series fail or if the bundle contract check fails.
- `python3 -m eet.check` validates every bundle in `site/data/` against this contract.
- The site renders with no console errors at 1280px and 375px wide.
