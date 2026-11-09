# GDP, labour and wages: what was deferred and why

Built on 9 Nov 2026 (registry modules `gdp.py`, `labour.py`, `national_labour.py`, `wages.py`; national
source families in `pipeline/eet/sources.py` and `pipeline/eet/parsers/national.py`). Every series below
was tried live; nothing here is in the tracker yet.

## Deferred

| Item | Why | What it would take |
|---|---|---|
| Spain, Social Security affiliation (monthly, t+2) | The PX-Web API paths on `w6.seg-social.es` (`/PXWeb/api/v1/es/`, `/PxWeb/api/v1/es/`, `/api/v1/es/`) all return 404; only the HTML interface answers. | Find the xlsx/PX download behind the PX-Web tables, or a datos.gob.es distribution, and add an `ss` family. Spain is the most payroll-like monthly series in Europe, so this is the top national gap. |
| Spain, SEPE registered unemployment | Only a BIFF `.xls` file; the standard library cannot read it. | A small BIFF reader, or the PDF twin. |
| Italy, cassa integrazione (CIG) and INPS hires/separations | No monthly machine-readable endpoint found (CKAN has annual files only). | Locate the INPS databrowser web service (research/04, section 1). Would sit next to German Kurzarbeit. |
| France, monthly signal (URSSAF DPAE hires) | Dataset not confirmed on open.urssaf.fr. | Verify the Opendatasoft dataset id. France has only the quarterly INSEE payroll flash today. |
| Euro area monthly "jobs panel" (weighted national growth) | The brief asks for side by side, not aggregated; Spain is also missing, so coverage would be about 47%. | research/04 section 10.2 recipe once Spain is in. Label it a house proxy with a coverage bar. |
| GDP nowcast | Out of scope for this pass (research/02 section C, gap 2). | Bridge equations on IP, retail, services, ESI; publish a track record. |
| Industrial production excluding Ireland | Eurostat has no EA-ex-IE aggregate in `sts_inpr_m`; an approximation needs country weights. | Weighted average of country indices with value-added weights. |
| Services volume index | `sts_setu_m` has only nominal turnover (NETTUR) for EA21; `VOL_SLS` is empty. The chart says "nominal". | Nothing to do until Eurostat publishes a volume series. |
| LFS flows before 2021 | `lfsi_long_q` seasonally adjusted EA21 flows start in 2021-Q2. | NSA flows go further back but would need the tracker's own seasonal adjustment. |
| Hours worked, hours per worker | Not requested this pass. | `namq_10_a10_e` (THS_HW) and `lfsi_ahw_q`. |
| Vacancies per unemployed, EC labour-shortage indicator | Not requested this pass. | `jvs_q_r21` levels (not every country reports them) and `ei_bsin_q_r2`. |
| GDP release vintages (revisions table) | Not requested this pass. | `ei_na_q_vtg`. |

## Things the next person should know

- **GUS (Poland) quota**: the DBW API admits 100 calls per 15 minutes and needs one call per month per
  variable. The `gus` family refetches the last 6 months on every run and backfills at most 48 missing
  months per series per run, newest first, so a fresh store fills the 2019-onward history in two runs at
  least 15 minutes apart. A 429 in the middle of a run keeps what was fetched.
- **ISTAT**: the release edition is part of the key (`2026M10G29`); the `istat` family discovers it on
  every run with an edition-wildcard query (about 20 to 40 s) before fetching the data, and pauses 13 s
  between ISTAT calls (limit 5 per minute). The edition date is the series' `data_updated`.
- **CBS**: the right monthly labour-force table is `80590ned` (to 2026-09, modified 2026-10-15). The
  `83131NED` mentioned in research/04 is a price table.
- **Bundesbank BBDL1** mirrors Destatis employment and the BA's unemployment, vacancies and Kurzarbeit with
  no login. Vacancies (`VBA000`) are already in thousands; Kurzarbeit (`LKA100`) is in persons.
- **Ireland**: the GDP heatmap and the GDP level chart carry an "excluding Ireland" line computed from
  chain-linked levels (EA21 minus IE). Chain-linked volumes are not additive, so it is marked original and
  approximate.
- **ECB wage tracker**: the series already runs to 2027-09. The chart splits it at the current month
  (`ctx.today`) and marks the forward-looking part as context.
