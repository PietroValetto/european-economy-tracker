# Fiscal, International and Europe pages: what was built, what was deferred

Built on 2026-11-09 in `pipeline/eet/registry/fiscal.py`, `international.py` and `europe.py`
(tests: `pipeline/tests/test_fiscal_international_europe.py`). Every series below was fetched live
on that date; all 42 series and 39 charts build, and `eet.check` reports no errors.

## Built

**Fiscal** (`fiscal`): `gov-debt` (reserved tile chart), `gov-debt-countries`, `gov-debt-heatmap`,
`gov-balance`, `gov-deficit-countries`, `gov-primary-balance`, `gov-revenue-expenditure`,
`gov-interest-countries`, `gov-interest-ea`, `gov-r-minus-g` (original), `gov-forecast-deficit`,
`gov-forecast-debt`, `fiscal-table`.

**International** (`international`): `intl-overview` (table), `intl-gdp-growth`, `intl-gdp-level`
("the transatlantic gap", original), `intl-inflation`, `intl-unemployment`, `intl-policy-rates`,
`intl-10y-yields`, `intl-fx-usd` (original), `ea-current-account` (12-month sums, original),
`ea-trade-balance`, `ea-exports-imports`, `current-account-countries`.

**Europe** (`europe`): `europe-at-a-glance` (table), `economic-sentiment` (reserved tile chart),
`sentiment-components`, `esi-countries`, `capacity-utilisation`, `target2-balances`,
`house-prices` (with the owner-occupied housing index), `house-prices-countries`,
`household-saving-rate`, `wealth-top10` (ECB DWA), `business-demography`, `electricity-prices`,
`gas-prices`, `hicp-administered`.

## Source decisions worth knowing

- Country fiscal data are the annual EDP table `gov_10dd_edpt1` (B9, GD, D41PAY for every member);
  euro area quarterly data are `gov_10q_ggnfa` (SCA) and `gov_10q_ggdebt`. Quarterly interest
  (D41PAY) is published unadjusted only, so it is shown as a four-quarter average.
- Commission forecasts: DG ECFIN Redisstat `FDMS_UBLGE` (balance) and `FDMS_UDGG` (debt). On
  2026-11-09 the latest vintage is the Spring 2026 forecast (updated 2026-05-21); the Autumn
  forecast will replace it automatically. Redisstat keeps only the latest vintage.
- r minus g uses the annual 10-year convergence yield (`irt_lt_mcby_a`) minus nominal GDP growth
  (`nama_10_gdp`, CP_MEUR), for EA, DE, FR, IT, ES. Marked original, with a caveat that the
  effective rate on the debt stock is the relevant one for debt dynamics.
- Non-euro CPIs come from BIS `WS_LONG_CPI` (one panel), because the OECD's Japan CPI stops at
  2021-06 and its euro area CPI at 2025-12. Euro area lines use Eurostat (HICP, GDP,
  unemployment).
- The euro area 10-year yield is Eurostat's EMU convergence series (`irt_lt_mcby_m`, geo `EA`),
  one month behind the OECD's `EA20` series: the existing test `test_urls_follow_quirks` forbids
  `EA20` in any URL, including OECD ones.
- Current account by country uses `bop_gdp6_q` (already % of GDP; same BoP data as `bop_c6_q`,
  which has no euro area aggregate and returns 413 unfiltered). Its euro area row exists only
  against non-members, so the country chart shows members and Poland; the euro area total is the
  monthly `ei_bpm6ca_m` chart.
- Goods trade: euro indicator dataset `ei_etea_m` (extra-euro area, SA, EUR mn).
- Administered prices: the indices are the special aggregates `AP` and `TOT_X_AP` of
  `prc_hicp_minr`; `prc_hicp_admp` is only the annual list of administered items.
- Household energy prices: `nrg_pc_204` band DC and `nrg_pc_202` band D2, all taxes, EUR/kWh x 100.
  Cyprus, Finland and Malta publish no household gas price. Data are half-yearly (`2026-S1`).
- DWA top-10% share: ECB key `DWA.Q.<area>.S14._Z._Z.NWA.T10.PT.S.N`; area `I10` is used as the
  euro area (I9 stops at 2025-Q4). Hungary is in the flow but dropped (not a member).
- TARGET balances: one ECB request, `TGB/M.DE+IT+ES+FR+NL.N.A094T.U2.EUR.E` (OR inside one
  dimension).

## Deferred (for the roadmap)

| Item | Why |
|---|---|
| Wholesale electricity (ENTSO-E), gas storage (GIE AGSI+), TTF | Need API keys (ENTSO-E token, AGSI+ key) or licensed data |
| NGEU / RRF disbursements, EU fiscal-rules metrics (net expenditure paths, EDP status, escape clauses) | HTML pages and Semester documents, no machine-readable feed found |
| IMF comparisons (WEO forecasts, Fiscal Monitor debt for US/UK/JP) | No IMF source family in the pipeline |
| China unemployment | No harmonised series at OECD or BIS |
| Euro area current account from the ECB BOP flow (SA, % of GDP) | BOP flow blocked by the ECB WAF in the research; Eurostat used instead |
| Debt maturity, Eurosystem holdings net of the central bank (`gov_10dd_rmd`, ECB GST, PSPP) | Not attempted in this pass |
| Defence spending (COFOG GF02) | Not attempted in this pass |
| Effective interest rate on government debt (D41PAY over lagged GD) for a second r - g line | Computable from data already stored; not built |
| Archive of past Commission forecast vintages | Redisstat serves only the latest vintage; would need storing each vintage on release |
| Daily sovereign spreads | Licensed (MTS / vendor); monthly spreads are in the glance table and on the financial page |
| Cheap follow-ups | Services capacity utilisation, labour as a factor limiting production, house sales (`prc_hpi_hsnq`), household debt to income, DWA bottom-50% share and Gini (same flow), TARGET balances of other NCBs and the ECB, current accounts of US/UK/JP, real policy rates |

## Core changes requested (not made; workarounds are local)

1. **Categorical bars cannot go through the core.** `bundles.latest_previous` sorts the last points
   with `periods.compare_key`, which raises on category labels such as `"Italy"`, so a build hook
   returning categorical `series` makes the chart fail. Workaround: `fiscal.Fields`, a dict whose
   `pop("series")` leaves the series in place so the final `bundle.update()` copies it verbatim,
   plus one placeholder `Ref` (the core refuses charts with no series). Fix wanted: skip
   `latest`/`previous` computation for non-period points and let the hook supply them; then
   `Fields` and the placeholder Refs can go. A test covers the workaround so a core change that
   breaks it fails loudly.
2. **Text table columns.** CONTRACT section 3 allows `format: "text"` and the renderer supports it,
   but `spec.COLUMN_FORMATS` and `check.py` reject it (and reject string cell values). Wanted for
   period/lag columns in `intl-overview`; for now periods are in column headers and the notes.
3. **Half-yearly frequency.** Eurostat energy prices use `YYYY-S1/S2`; `periods.freq_of` does not
   parse them and the contract has no `S` frequency. The energy bar charts carry `frequency: "A"`
   and say "first half of 2026" in the subtitle.
4. **OBS_STATUS "A" from BIS and OECD** ("normal value") is stored and shown as a flag. Worked
   around with `international.clean_flags` on every BIS/OECD Ref; better mapped to `""` in the
   CSV parser for those sources.
5. **The `EA20` URL test** should apply to Eurostat only; OECD's euro area code is `EA20`.
6. **Concurrent partial builds** (`--only` from several agents at once) rewrite
   `store/_meta.json` and `site/data/index.json` from whatever each process loaded; the last
   writer wins. Worth a file lock or a merge on write.
