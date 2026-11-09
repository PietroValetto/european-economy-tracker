# European Economy Tracker

**By [Popular Economics](https://populareconomics.substack.com/).** A running read on the euro area and
EU economy: growth, jobs, wages, inflation, financial conditions, the ECB, public finances and the
indicators that only Europe has, in one set of charts rebuilt automatically as the numbers come out.

Live site (once the repository is public, see below): https://pietrovaletto.github.io/european-economy-tracker/

## How it works

1. `pipeline/` (Python, standard library only) pulls every series in the registry from Eurostat,
   the ECB Data Portal, the European Commission and other public, keyless APIs.
2. It stores every vintage in `store/`, computes transforms, and writes one JSON bundle per chart to
   `site/data/`.
3. `site/` is a static website (no build step) that renders those bundles with Observable Plot in the
   Popular Economics house style.
4. GitHub Actions rebuilds the data every morning, polls for new numbers on release mornings,
   refreshes markets in the afternoon, commits the results and deploys `site/` to GitHub Pages.

See `CONTRACT.md` for the data and site contract and `ROADMAP.md` for what is planned but not built.

## Run locally

Everything runs from `pipeline/` with Python 3.11 or later (CI uses 3.12).

```bash
cd pipeline
python3 -m eet.build                         # full live build (about 10 minutes: the ECB API is slow)
python3 -m eet.build --only inflation        # one registry module; others are read from store/
python3 -m eet.build --only financial --only ecb   # several modules in one run (repeat --only)
python3 -m eet.build --offline               # no network: rebuild every bundle from store/
python3 -m eet.calendar                      # site/data/calendar.json, today to +45 days
python3 -m eet.calendar --offline --print    # from the cached iCal, and list the events
python3 -m eet.release                       # did today's releases come out? exit 0 yes, 3 no
python3 -m eet.release --date 2026-11-04     # the same check for any date in the Eurostat calendar
python3 -m eet.release --alerts              # after a rebuild: write data notes to outbox/alerts/
python3 -m eet.check                         # validate site/data against the contract
python3 -m unittest discover -s tests        # tests (no network)
cd ../site && python3 -m http.server 8000    # then open http://localhost:8000/
```

Add `?fixtures=1` to any page URL to render the hand-made sample bundles in `site/_fixtures/`.

## Release calendar and release detection

`eet.calendar` merges three sources into `site/data/calendar.json`:

- the **Eurostat release calendar** iCal (every "Euro indicators release" event plus a list of
  other relevant data releases; dates only, so euro indicators get the standard 11:00 Brussels
  time and a reference period inferred from the release's usual lag);
- **ECB Governing Council monetary policy meetings** (decision 14:15, press conference 14:45) and
  the staff projection rounds in March, June, September and December, hand-maintained in
  `pipeline/eet/data/ecb_meetings.json` (2026 and 2027, checked against the ECB schedule);
- **European Commission** business and consumer survey dates (ESI 11:00, flash consumer
  confidence 16:00) and forecast dates, hand-maintained in `pipeline/eet/data/ec_events.json`.

Tiers: 1 = GDP flashes, HICP flash, unemployment, ECB decisions; 2 = the other euro indicators,
EC surveys, staff projections, EC forecasts; 3 = other Eurostat releases. Each event lists the
dataset codes it updates; the chart ids come from scanning the registry at run time, so a new
section module is picked up without touching the calendar code. Update the two JSON files once a
year (the ECB publishes its meeting schedule about a year ahead; DG ECFIN its survey dates each
December).

`eet.release` decides whether a release has landed without downloading the data: for the
day's events it maps datasets to series and compares each series' stored publisher stamp
(`store/_meta.json`) with the publisher's current one: the Eurostat statistics-update RSS (one
request) or a one-period JSON-stat query, and for the ECB an `updatedAfter=<stored stamp>` probe
per key (404 means nothing new). Only a later stamp counts as a change, so a wrong calendar date
cannot trigger anything. It prints the changed series and the modules to rebuild, and exits 0
(changed) or 3 (nothing changed). `eet.release --alerts` then writes, for each changed tier-1 or
tier-2 release, a numbers-only note (latest, previous, change, period, source, chart link) to
`outbox/alerts/<date>-<release>.md` from the rebuilt bundles. Nothing is emailed yet.

## How CI works

One workflow, `.github/workflows/build.yml`, one job per run, with a concurrency guard so two data
runs never overlap. GitHub cron runs in UTC; Brussels is UTC+1 in winter and UTC+2 in summer.

| Run | When (UTC) | What it does |
|---|---|---|
| **Daily** | 05:00 every day (06:00 Brussels in winter, 07:00 in summer) | Tests, full build, calendar, contract check; commits `store/`, `site/data/` and `outbox/` to `main` as "Data: daily run ..." |
| **Release polling** | Weekdays every 5 minutes, 09:55 to 10:40 in winter months and 08:55 to 09:40 in summer months (10:55 to 11:40 Brussels all year). March and October run both sets; a time gate skips the one that is an hour early | `eet.release`; only if it exits 0: rebuild the affected modules, write the data notes, check, commit "Data: poll run ... (release ids)" |
| **Markets** | 16:30 weekdays | `eet.release` for the afternoon events (ECB decision, EC flash consumer confidence), then rebuild `financial` and `ecb` plus anything changed; check; commit |
| **Deploy** | After any run that committed, or on a push to `site/` | Uploads `site/` and deploys it to GitHub Pages. Runs only when the repository is public |

Manual runs: Actions > Build > Run workflow, with mode `daily`, `poll`, `markets` or `deploy`
(and an optional date for `poll`). A failed build, test or contract check fails the run and
commits nothing, so the site keeps the last good data. The raw-response cache
(`pipeline/.cache/`) is not carried between runs: every run fetches live, and the store is the
memory that matters.

### Actions minutes (private repository)

Private repositories on the free plan get 2,000 minutes a month; jobs are billed by the minute,
rounded up. Estimate at today's registry size, where ECB requests dominate (about 10 seconds
each, including retries on its random 504s):

| Run | Runs a month | Minutes each | Minutes a month |
|---|---|---|---|
| Daily full build (about 130 series now, more as sections land) | 30 | 12 to 15 | 360 to 450 |
| Release polls (10 a weekday in the window, plus the gated no-ops in March and October) | about 255 | 1 (2 on release days) | 255 to 300 |
| Rebuilds after a detected release | about 15 | 3 to 4 | 45 to 60 |
| Markets run | about 22 | 6 to 8 | 130 to 175 |
| **Total** | | | **about 800 to 1,000** |

That is about half the free allowance. Once the repository is public, standard GitHub-hosted
runners are free and unlimited, and the Pages deploy job (about 1 minute per committed run) starts.
If the private budget gets tight: drop polling to every 10 minutes (saves about 130 minutes) or
move the markets run to the financial module only.

## Going public

1. Check that nothing licensed is in `store/` or `site/data/` (ROADMAP section 9.1).
2. Settings > General > Danger zone > Change visibility > Public.
3. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
4. Actions > Build > Run workflow, mode `deploy` (or wait for the next scheduled run). The
   `deploy` job, skipped while the repo was private, now publishes `site/` to
   https://pietrovaletto.github.io/european-economy-tracker/.
5. Optional: a custom domain (Settings > Pages > Custom domain, plus a `site/CNAME` file). All URLs
   in `site/` are relative, so nothing else changes.
