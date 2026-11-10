# Roadmap

Everything planned for the European Economy Tracker that is **not built yet**, grouped and in the
order we expect to build it. What exists today is in `README.md` and `CONTRACT.md`; the research
behind each item is in `~/Library/CloudStorage/Dropbox/Popular Economics/07 Ideas & Series/EU EconVitals/`
(top-level report and `research/01` to `05`).

Each item gives: **what** it is, **why** it matters, the **data** and its access status, the
**effort** and what it **depends on**.

- Access status: **free** (open, keyless API), **free, files** (open but only as xlsx, PDF or HTML
  pages, no API), **key needed** (free or paid registration, token stored as a repo secret),
  **licensed** (vendor data we may not republish without a contract), **not machine-readable**.
- Effort: **S** up to a day, **M** a few days, **L** a week or more.

---

## 1. Going public

### 1.1 Flip the repository to public and turn on Pages
- What: Settings > General > Change visibility to public; then Settings > Pages > Source:
  "GitHub Actions". The `deploy` job in `.github/workflows/build.yml` is already written and
  skips itself while the repo is private (`if: github.event.repository.private == false`). Run
  the workflow once by hand (Actions > Build > Run workflow, mode `deploy`) to publish.
- Why: the site, the calendar and the alerts all link to
  `https://pietrovaletto.github.io/european-economy-tracker/`; nothing is visible until then.
  Public repos also get unlimited free Actions minutes (the private budget is 2,000 a month).
- Data: none. Access: free.
- Effort: S. Depends on: a last look at `store/` and `site/data/` for anything licensed
  (section 9.1), and the About page wording.

### 1.2 Custom domain (optional)
- What: a domain such as `tracker.populareconomics.eu` with a `CNAME` file in `site/` and the DNS
  record GitHub asks for; enforce HTTPS.
- Why: a stable, branded URL that survives a repo rename. Every URL in `site/` is relative, so
  nothing in the code changes.
- Effort: S. Depends on: 1.1; a domain decision (open question in the study).

### 1.3 Cookie-less analytics
- What: Plausible or GoatCounter script tag, no consent banner (Econvitals checklist item 100).
- Effort: S. Depends on: 1.1. Paid for Plausible; GoatCounter is free for small sites.

---

## 2. Newsletters and alerts

Nothing is sent today. `eet.release` writes numbers-only data notes to `outbox/alerts/` on
release mornings; everything below turns those into email and posts.

### 2.1 Choose the email provider
- What: one provider for confirmed opt-in lists, transactional sends and an API callable from
  GitHub Actions. Candidates: Buttondown (Markdown-native, API, cheap), Resend or Postmark plus a
  small list store, Mailchimp/Brevo (heavier), or Substack (no public send API, see 2.6).
- Why: everything else in this section depends on it. Econvitals keeps the list at its web host
  and delivers through a mail provider, with no open or click tracking.
- Access: key needed (API key as a repo secret). Effort: S to decide, M to wire.
- Depends on: 1.1 (links in emails must resolve).

### 2.2 Release alerts from `outbox/`
- What: send each `outbox/alerts/<date>-<release>.md` within minutes of the release, with a
  one-line human-readable lead added by a writer (2.8), a chart PNG (6.5) and a link to the chart
  anchor. Subscriber choice as on Econvitals: All / Major (tier 1: GDP flashes, HICP flash,
  unemployment, ECB decisions, about four a month) / Choose / None.
- Why: the "first read within minutes" is Econvitals' most distinctive product; the detection,
  calendar and numbers already exist.
- Data: the chart bundles. Access: free. Effort: M.
- Depends on: 2.1, 2.7 (opt-in), 2.8 (verification) if any prose is added; a "sent" ledger in
  `outbox/` so a re-run never sends twice.

### 2.3 Noon reaction and roundup (major release days)
- What: a second email around 13:00 on tier-1 mornings: the data in a few sentences, how markets
  moved (Bund and BTP yields, EUR/USD, the ECB-dated EUR STR path), what analysts said.
- Why: Econvitals' "Reaction and Roundup" is the reason people open the second email.
- Data: intraday markets are **licensed** (exchange and vendor data). Free alternatives: ECB
  daily series (published after 16:00, so too late for noon), Bundesbank daily Bund yields
  (free, end of day). A noon version needs a licensed feed; an end-of-day "reaction" works free.
- Effort: M (L with a market-data feed). Depends on: 2.2, 7.1 for the market path.

### 2.4 Morning Note (weekdays)
- What: about 3,000 characters before 07:00 Brussels: a chart piece, research picks, "the day
  ahead" from `site/data/calendar.json` with times and the previous value.
- Why: a daily habit; the calendar and the latest values are already machine-readable.
- Data: calendar.json, chart bundles, research feeds (ECB working papers RSS, CEPR VoxEU,
  Bruegel; free). Effort: M. Depends on: 2.1, 2.8.

### 2.5 Weekly briefing (Saturday)
- What: euro area cycle, structure and policy, the countries, research; web text plus PDF.
  Econvitals already sends a Weekly Europe Briefing as a six-page PDF with no charts: ours leads
  with the tracker's charts.
- Effort: L. Depends on: 2.1, 2.8, 6.5 (chart PNGs).

### 2.6 Substack cross-posting
- What: publish the weekly (and selected notes) on `populareconomics.substack.com` as well.
- Why: the existing audience lives there.
- Access: **not machine-readable** in the sense that matters: Substack has no public posting
  API, and Blotato cannot post Substack Notes. Plan: generate a paste-ready post (HTML with
  hosted chart images) in `outbox/substack/` and post by hand, or import via Substack's email
  import if that proves workable. Effort: S for the paste-ready export. Depends on: 2.5.

### 2.7 Signup with confirmed opt-in
- What: a `site/subscribe/` page (name, email, product checkboxes, the four-way alert choice, a
  honeypot field), confirmed opt-in email, one-click unsubscribe and a manage link in every email,
  no tracking pixels, automatic removal on bounces and spam reports.
- Why: GDPR and deliverability; Econvitals does exactly this.
- Access: depends on 2.1 (most providers host the form and the double opt-in). Effort: S to M.

### 2.8 Verification design for anything with prose: ledger and receipts
- What: Econvitals' Briefwright discipline, applied to every generated email: every number and
  quote goes into a **ledger** with a **receipt** (series id, period, value read from the bundle
  or store, source URL); the writer may cite only ledger tokens, resolved at build time; two
  mechanical checks (re-read every number from its source; reverse sweep: every number, date and
  quotation in the text must be in the ledger); model judges try to refute claims; the issue is
  **held** if a number is unexplained or a raised problem is unresolved. One text renders to email,
  web and PDF.
- Why: AI-written notes with wrong numbers would cost the newsletter its credibility. Our notes
  are numbers-only today precisely so this can be added first.
- Data: the store and bundles. Effort: L. Depends on: none; blocks 2.2 (prose), 2.3, 2.4, 2.5.
- Open decision for Pietro: unreviewed publication (as Econvitals does, with a disclosure) or his
  sign-off before sending.

### 2.9 RSS feeds and social posting
- What: `site/feeds/*.xml` for alerts and briefings; a posting schedule through **Blotato**
  (already chosen for Popular Economics) for X, Bluesky, Threads, LinkedIn and Instagram, with the
  chart PNG.
- Access: Blotato key needed; media must be public URLs (the Pages site or 6.5 provides them).
- Effort: M. Depends on: 1.1, 6.5.

---

## 3. Nowcasts and early reads

### 3.1 Euro area GDP nowcast with a public track record
- What: a house nowcast of current-quarter euro area GDP from bridge equations on industrial
  production, retail trade, services production, the ESI and sector confidence, trade and the
  Indeed postings; updated after each input release; shown as a path through the quarter with a
  band, next to €-coin and the Bundesbank WAI. Publish its errors against the t+30 preliminary
  flash from the first quarter, and a back-test.
- Why: the biggest gap the study found: no public GDPNow exists for the euro area. This is where
  the tracker can lead rather than copy.
- Data: Eurostat STS and national accounts, DG ECFIN surveys, Indeed (all free); €-coin (free,
  press release PDF: free, files); Bundesbank WAI (free, `BBDE1`). Effort: L.
- Depends on: the GDP and labour sections (built by the section agents), vintage storage (built:
  `store/` keeps first_seen/last_seen, so real-time back-tests are possible from now on).

### 3.2 Early GDP read from national flashes (flash day)
- What: on the t+30 flash day, a running GDP-weighted average of country q/q growth as the
  national flashes arrive: INSEE 07:30, INE 09:00, Austria/Belgium/Portugal/Ireland around
  09:00-10:00, Destatis and ISTAT 10:00, CBS (verify time), then Eurostat at 11:00. Show the share of
  euro area GDP reported so far, and "EA ex Ireland" next to the headline (Ireland swings by
  several points). Log the miss at 11:00.
- Why: tested on Q3 2026, ten countries (93.8% of EA GDP) gave 0.41% against the 0.4% flash. A
  10:30 "what the countries say" note is a live-blog product, not a day-ahead one.
- Data: INSEE BDM, INE tempus, CBS OData, Bundesbank/Destatis, ISTAT SDMX (free; ISTAT is slow,
  5 requests a minute); weights from `nama_10_gdp` (free). Recipe: research/04 section 10.3.
- Effort: M. Depends on: national fetchers (one exists in `eet/parsers/national.py` from a section
  agent), a polling run from 07:30 on flash days (the calendar knows the date).

### 3.3 Combined monthly European jobs panel
- What: a house proxy for euro area employment growth about three weeks before Eurostat's
  quarterly flash: employment-weighted average of monthly growth (never summed levels) in Spain
  (Social Security affiliation, day 2), the Netherlands (CBS monthly LFS, about m+15), Germany
  (Erwerbstätige via Bundesbank, about m+30) and Italy (ISTAT monthly LFS, about m+30); France's
  quarterly payroll flash when out; Poland's enterprise employment for an EU view. Published only
  when DE, IT and ES are in, with a coverage bar ("Spain only" on day 2), then bridged to EA
  employment with an error band and track record.
- Why: Europe has no payrolls day; this is the closest honest substitute. Coverage is about
  **60%** of EA employment monthly (DE+IT+ES+NL), about **70%** adding AT, PT, FI, EL; France,
  the second-largest market, is quarterly only. Label it "European jobs panel (house measure)".
- Data: CBS, Bundesbank, ISTAT, GUS, INSEE: free (ISTAT needs the edition code in the key);
  Spain: see 4.1. Recipe and weights: research/04 section 10.2. Effort: L.
- Depends on: 4.1, national fetchers, `original: true` methods entry.

---

## 4. National and key-gated sources

### 4.1 Spanish Social Security affiliation
- What: afiliados medios (monthly average, SA) on the 2nd working day at 09:00, plus the
  mid-month reading around the 15th: the earliest employment signal in Europe.
- Why: the most US-payroll-like series in Europe; input to 3.3. Caveat: counts registrations
  (a person with two jobs counts twice) and includes the self-employed.
- Data: Ministerio de Inclusión, Seguridad Social y Migraciones. Access: **free, files**: the
  PX-Web interface works but its API paths returned 404; pull the xlsx/PX files or the press
  release table. Effort: M (a fragile scraper). Depends on: a file-based fetcher.

### 4.2 Destatis GENESIS
- What: German national releases not mirrored by the Bundesbank (orders, detailed CPI, turnover).
- Access: **key needed** (free account; username/password or token on every call). Store as a
  secret. Most labour data come free through the Bundesbank `BBDL1` flow instead. Effort: S once
  registered.

### 4.3 Banque de France Webstat
- What: French money, credit and survey series, the BdF monthly business survey and nowcast.
- Access: **key needed** (client id and secret; the catalogue answered 401). Effort: S once keyed.

### 4.4 De Nederlandsche Bank (DNB)
- What: Dutch financial and pension statistics.
- Access: **key needed** (subscription key; endpoint not verified). Effort: S to M.

### 4.5 ENTSO-E Transparency Platform
- What: day-ahead wholesale electricity prices by bidding zone, load and generation mix.
- Access: **key needed** (free security token requested from ENTSO-E). Effort: M (XML API).
- Depends on: section 8.2.

### 4.6 GIE AGSI+ (gas storage)
- What: EU and country gas storage fill levels, daily, against targets.
- Access: **key needed** (free API key in an `x-key` header). Effort: S. Depends on: 8.2.

---

## 5. Licensed data (budget decision)

Shipping the free, labelled proxies is the default. Each item below needs a contract, and none of
its history may be republished on the public repo (section 9.1).

### 5.1 Market-implied ECB path (OIS / ECB-dated EUR STR futures / Euribor futures)
- What: a FedWatch-style ECB meeting-by-meeting path and year-end distribution.
- Why: the free proxy on the site (`rate-path-forwards`: ECB AAA-curve forwards) is biased upward
  by term premium; the SPF and staff-projection rate assumptions are surveys, not markets.
- Access: **licensed** (Eurex / Deutsche Börse data services, ICE, LSEG, Bloomberg). No free
  documented feed exists; scraping exchange pages is fragile and probably against their terms.
- Effort: M once licensed. Depends on: a budget decision by Pietro.

### 5.2 HCOB / S&P Global PMIs
- What: flash and final PMIs for the euro area, Germany, France, Italy, Spain.
- Access: **licensed** (the PMI site answers 403 to scripts). Free substitutes already planned:
  EC ESI and sector confidence, INSEE climate, ifo (file per month), Indeed postings.
- Effort: S once licensed. Depends on: budget.

### 5.3 Daily country government bond yields
- What: daily 2y and 10y yields for IT, FR, ES, PT, EL and spreads to the Bund.
- Access: **licensed** for most countries. Free today: monthly Maastricht yields
  (`irt_lt_mcby_m`, on the site), the daily Bund curve (Bundesbank `BBSIS`), the ECB AAA curve.
- Effort: S once licensed.

### 5.4 Equities, volatility, inflation swaps
- What: Euro Stoxx 50, DAX, FTSE MIB, CAC, IBEX, VSTOXX; 5y5y inflation swaps.
- Access: **licensed** (index and swap data). Effort: S once licensed.

---

## 6. Site features not built

### 6.1 Site search
- What: a client-side index of page, section and chart titles plus curated synonyms
  ("jobs" -> unemployment, vacancies; "prices" -> HICP), generated by the pipeline as
  `site/data/search.json`. Effort: S to M.

### 6.2 Tracker twins
- What: for charts whose period is in progress (the current quarter's GDP, this month's HICP
  before the flash), a twin series from the nowcast or the national flashes with an
  Actual/Tracker toggle remembered per reader (Econvitals checklist item 36).
- Depends on: 3.1, 3.2. Effort: M.

### 6.3 Keyboard navigation (j/k between charts) and paragraph anchors
- What: j/k to move between charts, a copy-link pilcrow on section headings. Effort: S.

### 6.4 Dark mode
- What: a dark palette from the Popular Economics tokens, `prefers-color-scheme` plus a toggle;
  charts re-themed (Econvitals lacks it). Needs dark tokens agreed in the design system first
  (do not invent colours). Effort: M.

### 6.5 Branded PNG chartbook
- What: every chart rendered by the pipeline (headless) to a branded PNG with title, units,
  source and logo, committed under `site/chartbook/` and referenced by URL from emails and posts;
  alt text from the bundle. Per-chart PNG download in the browser already exists; this is the
  batch, server-side version.
- Why: emails and social posts need images at a public URL (Blotato requires public media URLs).
- Effort: M (needs a headless browser in CI, or a small SVG renderer). Depends on: 1.1.

### 6.6 Italian translation
- What: an Italian edition (`site/it/`) with translated chrome, titles and subtitles; numbers and
  bundles shared. Open decision in the study. Effort: M to L (every chart title needs an Italian
  field in the registry).

### 6.7 Smaller home-page items from the checklist
- "New since last visit" dots and glossary tooltips on the tiles; "The economy in four
  questions" cards; a composite activity/inflation grid in standard deviations against history;
  an email signup strip; an "as of" stamp per section. Effort: S each.

---

## 7. Tools

Ordered by reader value and data readiness. Each is a page under `site/tools/` with shareable URL
state and its own methods entry.

### 7.1 ECB projections animator (the European "dot plot")
- What: every ECB/Eurosystem staff projection round for GDP, HICP, core and unemployment, with
  play/step controls and the realised outcomes; the ECB Survey of Monetary Analysts (SMA) median
  policy-rate path as the "dots", plus SPF; accuracy tables (projected vs actual).
- Data: ECB `MPD` flow (free, already used), SPF (free, used), SMA (free, files: ECB publishes
  SMA results as spreadsheets; check for a Data Portal flow). Effort: M.

### 7.2 ECB-speak hawk-dove tracker
- What: Governing Council speeches, interviews and press conferences scored from -3 (dovish) to
  +3 (hawkish) under a frozen, published rubric; three reads per document and a second model on
  disagreement; scores by member and by meeting cycle; validation against the staff projections
  and decisions.
- Data: the ECB speeches dataset and press conference transcripts (free); national central bank
  speeches (free, HTML). Effort: L. Depends on: an LLM budget and the verification rules of 2.8.

### 7.3 Per-country debt explorer
- What: debt and deficit paths per country under the EC's assumptions, with dials for growth,
  interest rates, inflation and the primary balance; debt-stabilising primary balance; the EU
  fiscal rules' net-expenditure path (8.1).
- Data: AMECO and EC forecasts via Redisstat (free), EC Debt Sustainability Monitor (free,
  files), `gov_10q_ggdebt` (free). Effort: L.

### 7.4 Policy-rule tool
- What: Taylor-type prescriptions for the ECB (Taylor 1993, balanced approach, inertial,
  first-difference) on real-time data vintages, with dials for r*, the inflation measure and
  the output gap; range tables; "the arithmetic for the next meeting".
- Data: HICP and core (free), output gap from AMECO or the EC forecast (free), r* estimates
  (HLW from the NY Fed, free; ECB staff estimates, files). Vintages: our `store/` from now on,
  earlier from the ECB Real-Time Database (research use; verify terms). Effort: M to L.

### 7.5 Rate decomposer
- What: change in a yield between two dates split into expected policy path and term premium,
  and into real yield and inflation compensation, for the euro area AAA curve, the Bund and
  (with licensed data) other countries; named windows and ECB decision-day windows.
- Data: ECB YC (free), Bundesbank curve (free), inflation compensation needs swaps (licensed,
  5.4) or inflation-linked bonds (partly free). Effort: L (own ACM-style term premium model).

### 7.6 Economy vs pre-COVID trend
- What: ~50 euro area series against trends fitted before 2020 (log-linear over 2/5/10 years,
  peak-to-peak, HP), with the gap in percent. Data: all free, mostly already stored. Effort: M.

### 7.7 Forecasts comparison
- What: this year and next for GDP, HICP, core, unemployment and the deposit rate from the EC,
  ECB staff, SPF, SMA, IMF and OECD, side by side, each on its own basis (nothing converted).
- Data: Redisstat, MPD, SPF, IMF and OECD APIs (free); consensus forecasts are licensed.
  Effort: M.

### 7.8 Inequality explorer on the ECB Distributional Wealth Accounts
- What: wealth shares by decile, top 10% and bottom 50%, by country and asset class, quarterly;
  net wealth, housing, deposits and debt by group.
- Data: ECB `DWA` flow (free). Effort: M.

---

## 8. European-only trackers

### 8.1 NGEU and EU fiscal rules
- What: Recovery and Resilience Facility grants and loans committed and disbursed per country
  (and as % of GDP), milestones met, EU joint debt outstanding; under the reformed fiscal
  framework, each country's net expenditure path against the agreed plan, the EDP status and the
  control-account balance.
- Data: EC RRF Scoreboard (free, files and an open-data download), Eurostat RRF statistics
  (in the calendar as "Recovery and Resilience Facility statistics"), EC funding operations page
  (free, HTML), Council recommendations and EC fiscal surveillance reports (**not
  machine-readable**: PDF tables to transcribe by hand). Effort: M for RRF, L for the rules.

### 8.2 Energy wholesale prices and gas storage
- What: TTF gas and day-ahead electricity prices, gas storage against the EU fill targets,
  weekly pump prices by country, linked to Pietro's existing fuel trackers.
- Data: GIE AGSI+ (key needed, 4.6), ENTSO-E (key needed, 4.5), EC Weekly Oil Bulletin (free,
  files), TTF settlement prices (**licensed** from ICE Endex; free proxies: Eurostat and EC
  monthly gas prices, `nrg_pc_*`), national TSOs SMARD, RTE eco2mix, REE (free).
- Effort: M. Depends on: 4.5, 4.6.

---

## 9. Operations and licence hygiene

### 9.1 Licence hygiene
- What: a `licence` field per series (open / attribution / licensed), checked by `eet.check`:
  licensed series may appear only as the latest value, never as committed history in `store/`;
  a withdrawal switch that removes a series and its bundles; source credits on every chart
  (built); CC0 or CC BY for our own measures; an attribution page listing each publisher's terms
  (Eurostat and ECB reuse policies allow reuse with attribution).
- Why: Econvitals took down FRED series after a St. Louis Fed notice on 2 November 2026; the same
  risk applies to PMIs and vendor market data here. Effort: S to M. Depends on: before 1.1.

### 9.2 Discontinuation monitor
- What: a weekly job comparing each series' latest period with the dataset's end date in
  Eurostat `catalogue/toc/txt`, flagging datasets whose title gains a "(YYYY-YYYY)" range and series
  whose latest period is unexpectedly old. In 2026 HICP, job vacancies, ECB ICP and the old
  negotiated-wages key all broke this way.
- Data: Eurostat TOC (free). Effort: S.

### 9.3 Ops notifications
- What: when a scheduled run fails, a series has been in `failed` for three days, or the iCal has
  not been refreshed, open a GitHub issue (or send Pietro an email once 2.1 exists).
- Effort: S.

### 9.4 More calendar sources
- What: national release times for the early reads (INSEE, INE, Destatis, ISTAT, CBS, BA, GUS),
  ECB statistical releases (monetary developments, negotiated wages, SPF, BLS, CES, wage tracker),
  ifo/ZEW/Sentix, the HCOB PMI dates (dates only, no data). Today the calendar has Eurostat, ECB
  meetings and projections, and the EC surveys. Add the 2027 EC survey dates when DG ECFIN
  publishes its calendar (usually December) to `pipeline/eet/data/ec_events.json`, and the
  Autumn 2026 and Spring 2027 forecast dates once announced.
- Data: publisher calendars (mostly free, files or HTML; some have ICS, verify). Effort: M.

---

## 10. LFS microdata pathway (waiting on Pietro)

Summary of `research/05_lfs_microdata_pathway.md`. **Nothing in this repo or any pipeline touches
microdata until Pietro has answered the five questions below.** `lfs/` holds only the plan and a
drop-folder for checked aggregate results; `.gitignore` already blocks microdata file types there.

**What Pietro's data most likely is.** "An LFS that updates quarterly" does not fit the Eurostat
EU-LFS scientific use files: they contain quarterly files but are released **once a year** (each
December, for the previous year; a quarter arrives 11 to 23 months after it ends). It fits the
**ISTAT RCFL research files (MFR)**: Italian microdata released quarterly about 100 to 110 days
after the quarter, with 3-month and 12-month **longitudinal** files that link the same people (the
only source of labour-market flows by group in Europe). Or it may be the Eurostat **published**
LFS tables (`lfsq_*`, `lfsi_*`, quarterly, about t+72), which are aggregates, not microdata.

**The five questions for Pietro.**
1. Did you sign a Eurostat or an ISTAT confidentiality declaration?
2. Which research entity and project number is the access under?
3. Do the files come as per-country encrypted zips (Eurostat) or as Italian files (ISTAT)?
4. What is the latest reference period you hold?
5. When does the project end, and does it cover recurring publication of aggregate tables on a
   public website? (Confirm in writing with estat-microdata-access@ec.europa.eu or the ISTAT
   Contact Centre.)

**Results contract.** One JSON per analysis and reference period
(`out/<analysis_id>/<period>.json` plus `latest.json`), schema `eu-econvitals/lfs-result/1.0`: source
block with release, DOI and the mandatory Eurostat citation; provenance tag "Computed from EU-LFS
microdata by Pietro Valetto"; run metadata (date, code commit); method (weights, seasonal
treatment, approximate standard errors); a confidentiality block (rules version, cells suppressed
and flagged, `check_passed`); dimensions and series with `value`, `se` and `flag`. Unweighted counts
and weighted totals never leave the local audit log. The site renders these as ordinary bundles
(`site/data/lfs/<analysis_id>.json`, CONTRACT section 5) with `original: true` and `lfs_vintage`.

**Local flow, on Pietro's machine only** (a separate project, `~/Developer/eu-econvitals-lfs/`,
outside Dropbox, on an encrypted disk). `make lfs`: ingest CSV to parquet if needed; run every
analysis for the new vintage; run the confidentiality gate; validate each JSON against the
contract; benchmark headline cells against Eurostat's published tables (EA21 employment rate
20-64 within 0.3 pp); diff against the previous vintage; write a run report; stop. `make publish`
is a separate, deliberate step that copies `out/` into this repo's `lfs/results/` after a human
has read the run report. No push without that look.

**Confidentiality rules** (Eurostat Guidelines for publication, 17/09/2026), applied to every cell
before any file is written: fewer than 3 unweighted observations, or a weighted population below
reliability limit "a": not published (null, flag `a`); between "a" and "b": published with a
limited-reliability flag (shown with a dagger); country groups use the maximum of member-country
limits; 5-year age bands only, never single years; a deny list of row-level keys; complementary
suppression so a hidden cell cannot be recovered by subtraction; fixed, precomputed cubes only, no
querying of microdata from the site, ever; tests with synthetic thin cells. Microdata stay out of
Dropbox and git; at project end `data/`, `cache/` and `audit/` are deleted and the closing
declaration signed.

**The first ten analyses**, in build order of value and feasibility:
1. Labour market by group table (employment, unemployment, participation, slack, 20-64, by sex,
   age band, education and migrant status, change from 2019).
2. Ageing counterfactual for the country strip (version 1 from published tables: no microdata,
   ship first; version 2 adds education).
3. Italian flows by group (ISTAT 3-month longitudinal files).
4. Hires and separations from the LFS, by sector, age and reason for leaving.
5. Hours gap: hours wanted minus hours usually worked.
6. Migrant employment gap, age-adjusted, by education.
7. Involuntary part-time and temporary work, quarterly, by age and education.
8. Who is low-paid: shares in the bottom two pay deciles.
9. Slack and discouraged workers by group.
10. NEETs by region, sex and education.

Effort: L overall. Depends on: Pietro's answers; then build the pipeline on the free Eurostat
public-use files (noisy, for testing only) so analyses 1, 4, 5 and 9 are ready when access is
confirmed.

---

## 11. Data extensions left by the section agents

The GDP, labour, wages, national labour, fiscal, international and Europe sections were built on
9 November 2026; their agents' follow-up notes (formerly `docs/notes/*.md`) are merged here and
into sections 3, 4, 7 and 8 above. Every item was tried live on that date.

### 11.1 National sources not yet in (feed 3.3 and 3.2)
| Item | Why not yet | What it would take | Access | Effort |
|---|---|---|---|---|
| Spain, Social Security affiliation | PX-Web API paths on `w6.seg-social.es` (`/PXWeb/api/v1/es/`, `/PxWeb/api/v1/es/`, `/api/v1/es/`) all return 404; only the HTML interface answers | The xlsx/PX file behind the tables, or a datos.gob.es distribution; a new `ss` family (see 4.1) | free, files | M |
| Spain, SEPE registered unemployment | Only a BIFF `.xls` file; the standard library cannot read it | A small BIFF reader, or the PDF twin | free, files | M |
| Italy, cassa integrazione (CIG), INPS hires and separations | No monthly machine-readable endpoint found (CKAN has annual files only) | The INPS databrowser web service (research/04 section 1); would sit next to German Kurzarbeit | free, files | M |
| France, monthly hires (URSSAF DPAE) | Dataset id not confirmed on open.urssaf.fr | Verify the Opendatasoft dataset; France has only INSEE's quarterly payroll flash today | free | S |
| Euro area monthly jobs panel | The brief asked for side by side, not aggregated; without Spain coverage is about 47% | research/04 section 10.2 recipe once Spain is in (3.3) | free | L |

### 11.2 Indicators to add
| Item | Notes | Data | Effort |
|---|---|---|---|
| Industrial production excluding Ireland | `sts_inpr_m` has no EA-ex-IE aggregate; needs a value-added-weighted average of country indices | Eurostat | S |
| Services volume index | `sts_setu_m` has only nominal turnover (`NETTUR`) for EA21; `VOL_SLS` is empty, so the chart says "nominal". Wait for Eurostat | Eurostat | none |
| LFS flows before 2021 | SA EA21 flows in `lfsi_long_q` start 2021-Q2; NSA flows go back further but need our own seasonal adjustment | Eurostat | M |
| Hours worked and hours per worker | `namq_10_a10_e` (`THS_HW`), `lfsi_ahw_q` | Eurostat | S |
| Vacancies per unemployed; EC labour-shortage indicator | `jvs_q_r21` levels (not every country reports them); `ei_bsin_q_r2` (labour as a factor limiting production) | Eurostat | S |
| Services capacity utilisation | Quarterly services survey in the EC BCS | Eurostat (`ei_bsse*`) | S |
| GDP release vintages (revisions table) | `ei_na_q_vtg`; our own `store/` keeps vintages from now on | Eurostat | S |
| House sales | `prc_hpi_hsnq` | Eurostat | S |
| Household debt to income | `nasq_10_ki` or ECB QSA | Eurostat / ECB | S |
| DWA bottom-50% share and Gini | Same ECB `DWA` flow as the top-10% chart (`...NWA.B50.PT.S.N`); the ECB answered 504 when tried on 9 Nov, so not added | ECB | S |
| TARGET balances of the other NCBs and the ECB | Same `TGB` flow as the five shown | ECB | S |
| Current accounts of the US, UK and Japan | OECD BoP | OECD | S |
| China unemployment | No harmonised series at the OECD or BIS | none | none |
| Euro area current account, ECB BOP flow (SA, % of GDP) | The BOP flow was blocked by the ECB WAF in the research; Eurostat `ei_bpm6ca_m` is used | ECB | S once reachable |
| Debt maturity; Eurosystem holdings of government debt | `gov_10dd_rmd`, ECB GST, PSPP holdings | Eurostat / ECB | M |
| Defence spending | COFOG `GF02` (`gov_10a_exp`) | Eurostat | S |
| Archive of Commission forecast vintages | Redisstat serves only the latest vintage (Spring 2026 on 9 Nov); store each vintage on release day | DG ECFIN | S |
| IMF comparisons (WEO forecasts, Fiscal Monitor debt for US/UK/JP) | No IMF source family yet; IMF rejects custom User-Agents | IMF (free) | M (feeds 7.7) |
| Daily sovereign spreads | Licensed (MTS or a vendor); monthly spreads are in the Europe glance table and on the financial page | see 5.3 | S once licensed |
| Wholesale energy (ENTSO-E, AGSI+, TTF); NGEU and EU fiscal-rules metrics | Keys or HTML-only sources | see 4.5, 4.6, 8.1, 8.2 | |

Built in the integration pass on 9 November 2026 from data already stored: the effective
interest rate on government debt (`gov-effective-rate`, fiscal) and real policy rates
(`intl-real-policy-rates`, international).

### 11.3 Source decisions and operating notes (keep when changing these sections)
- **One source per series, recorded.** Country fiscal data are the annual EDP table
  `gov_10dd_edpt1`; euro area quarterly data are `gov_10q_ggnfa` (SCA) and `gov_10q_ggdebt`.
  Quarterly interest (`D41PAY`) is published unadjusted only, so it is shown as a four-quarter
  average. Commission forecasts are Redisstat `FDMS_UBLGE` and `FDMS_UDGG`.
- **r minus g** uses the annual 10-year convergence yield (`irt_lt_mcby_a`) minus nominal GDP
  growth (`nama_10_gdp`, `CP_MEUR`) for EA, DE, FR, IT, ES; marked original.
- **International.** Non-euro CPIs come from BIS `WS_LONG_CPI` (the OECD's Japan CPI stops at
  2021-06, its euro area CPI at 2025-12). The euro area 10-year yield on the international page is
  the OECD's `EA20` series, one month fresher than Eurostat's `irt_lt_mcby_m` (geo `EA`), which the
  Europe page keeps. Current accounts by country use `bop_gdp6_q` (`bop_c6_q` has no euro area
  aggregate and returns 413 unfiltered). Goods trade is `ei_etea_m`.
- **Europe.** Administered prices are the special aggregates `AP` and `TOT_X_AP` of
  `prc_hicp_minr` (`prc_hicp_admp` is only the annual item list). Household energy prices are
  `nrg_pc_204` band DC and `nrg_pc_202` band D2, all taxes, half-yearly (`2026-S1`); Cyprus,
  Finland and Malta publish no household gas price. DWA uses area `I10` as the euro area (`I9`
  stops at 2025-Q4). TARGET balances are one ECB request with `+` inside one dimension.
- **GUS quota.** The DBW API admits 100 calls per 15 minutes and needs one call per month per
  variable: the `gus` family refetches the last 6 months on every run and backfills at most 48
  missing months per series per run, newest first, so a fresh store fills the 2019-onward history
  in two runs at least 15 minutes apart. A 429 mid-run keeps what was fetched.
- **ISTAT.** The release edition is part of the key (`2026M10G29`); the `istat` family discovers
  it on every run (20 to 40 s) and pauses 13 s between calls (5 a minute). The edition date is the
  series' `data_updated`.
- **CBS.** The monthly labour-force table is `80590ned`; the `83131NED` in research/04 is a price
  table.
- **Bundesbank BBDL1** mirrors Destatis employment and the BA's unemployment, vacancies and
  Kurzarbeit with no login. Vacancies (`VBA000`) are in thousands; Kurzarbeit (`LKA100`) in
  persons.
- **Ireland.** The GDP heatmap and level chart carry an "excluding Ireland" line from
  chain-linked levels (EA21 minus IE): not additive, so marked original and approximate.
- **ECB wage tracker** already runs to 2027-09; the chart splits it at the build date and shows
  the forward-looking part as context.
- **Core gaps the section agents worked around** (categorical bars, text table columns,
  half-years, BIS/OECD `A` flags, the `EA20` URL test, national source names, derived-series
  provenance, failures and concurrent writes in partial builds) were fixed in the core on
  9 November 2026; the workarounds are gone.
