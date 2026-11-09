"""Release calendar: write ``site/data/calendar.json`` (CONTRACT section 5), today to +45 days.

    cd pipeline
    python3 -m eet.calendar                    # live: fetch the Eurostat iCal
    python3 -m eet.calendar --offline          # use the cached iCal (pipeline/.cache/calendar/)
    python3 -m eet.calendar --start 2026-12-01 --days 10 --print

Sources:

* Eurostat release calendar, iCalendar feed (``EUROSTAT_ICAL``). Dates only: no time, no dataset
  code, no reference period (research/03 section 2). Kept: every event tagged "Euro indicators
  release", plus the other data releases listed in ``RELEASES``. Euro indicators go out at 11:00
  Brussels time; other Eurostat data releases also at 11:00.
* ECB Governing Council monetary policy meetings and staff projection months, hand-maintained in
  ``eet/data/ecb_meetings.json`` (decision 14:15, press conference 14:45).
* European Commission business and consumer surveys and forecast dates, hand-maintained in
  ``eet/data/ec_events.json``.

``RELEASES`` maps each Eurostat event SUMMARY to a short title, a tier, the dataset codes it
updates and the lag used to infer the reference period. Datasets are then mapped to the chart
ids that use them by scanning the registry at run time (series declarations, the methods
register for charts drawn by ``build`` hooks, and home tiles), so a new section module is picked
up without editing this file.

Tiers: 1 = GDP flashes, HICP flash, unemployment, ECB decisions; 2 = other euro indicators and
EC surveys, staff projections, EC forecasts; 3 = the rest.

Each event carries the contract fields plus ``id`` (``<date>-<release key>``, used by
``eet.release`` for alert file names) and ``period`` (inferred reference period, or null).
"""
import argparse
import datetime
import json
import os
import re
import sys
import zoneinfo

from . import http, paths

EUROSTAT_ICAL = "https://ec.europa.eu/eurostat/o/calendars/eventsIcal"
TZ = "Europe/Brussels"
BRUSSELS = zoneinfo.ZoneInfo(TZ)
WINDOW_DAYS = 45
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CALENDAR_JSON = os.path.join(paths.SITE_DATA, "calendar.json")
EURO_INDICATORS = "Euro indicators release"


def R(key, title, tier, datasets, freq=None, lag=0, time="11:00"):
    """One release type. ``freq``/``lag``: the reference period is the latest period of that
    frequency whose last day plus ``lag`` days is on or before the release date."""
    return {"key": key, "title": title, "tier": tier, "datasets": list(datasets), "freq": freq, "lag": lag,
            "time": time}


# Eurostat SUMMARY text (normalised: lower case, single spaces, plain hyphen) -> release type.
# Euro-indicator releases that are not listed here still appear, as tier 2 with no datasets.
RELEASES = {
    # tier 1
    "preliminary flash estimate gdp - eu and euro area":
        R("gdp-preliminary-flash", "GDP, preliminary flash estimate", 1, ["namq_10_gdp"], "Q", 25),
    "flash estimate gdp and employment - eu and euro area":
        R("gdp-flash", "GDP and employment, flash estimate", 1, ["namq_10_gdp", "namq_10_pe"], "Q", 40),
    "flash estimate inflation euro area":
        R("hicp-flash", "Inflation (HICP), flash estimate", 1, ["prc_hicp_fpd", "prc_hicp_minr", "HICP"], "M", -2),
    "unemployment":
        R("unemployment", "Unemployment", 1, ["une_rt_m"], "M", 25),
    # tier 2: the other euro indicators
    "gdp main aggregates and employment":
        R("gdp-full", "GDP and employment, detailed estimate", 2,
          ["namq_10_gdp", "namq_10_pe", "namq_10_a10", "namq_10_a10_e", "namq_10_fcs", "namq_10_lp_ulc"], "Q", 60),
    "inflation (hicp)":
        R("hicp-final", "Inflation (HICP), final", 2,
          ["prc_hicp_minr", "prc_hicp_ctr", "prc_hicp_ct", "prc_hicp_fpd", "prc_hicp_inw", "HICP"], "M", 14),
    "industrial production": R("industrial-production", "Industrial production", 2, ["sts_inpr_m"], "M", 40),
    "industrial producer prices, domestic market":
        R("producer-prices", "Industrial producer prices", 2, ["sts_inppd_m"], "M", 28),
    "retail trade": R("retail-trade", "Retail trade", 2, ["sts_trtu_m"], "M", 28),
    "services production": R("services-production", "Services production", 2, ["sts_sepr_m"], "M", 35),
    "production in construction": R("construction", "Production in construction", 2, ["sts_copr_m"], "M", 40),
    "international trade in goods": R("trade", "International trade in goods", 2, ["ext_st_eu27_2020sitc"], "M", 40),
    "balance of payments": R("balance-of-payments", "Balance of payments", 2, ["bop_c6_m", "bop_c6_q"], "M", 40),
    "job vacancy": R("job-vacancies", "Job vacancies", 2, ["jvs_q_r21"], "Q", 70),
    "labour cost index": R("labour-costs", "Labour cost index", 2, ["lc_lci_r2_q", "ei_lmlc_q"], "Q", 70),
    "house price index": R("house-prices", "House price index", 2, ["prc_hpi_q"], "Q", 85),
    "quarterly government debt": R("government-debt", "Government debt", 2, ["gov_10q_ggdebt"], "Q", 100),
    "government debt": R("government-debt", "Government debt", 2, ["gov_10q_ggdebt"], "Q", 100),
    "quarterly government deficit": R("government-deficit", "Government deficit", 2, ["gov_10q_ggnfa"], "Q", 100),
    "government deficit": R("government-deficit", "Government deficit", 2, ["gov_10q_ggnfa"], "Q", 100),
    "general government deficit and debt":
        R("edp-notification", "Government deficit and debt (EDP notification)", 2, ["gov_10dd_edpt1"], "A", 90),
    "first release sector accounts (households and businesses)":
        R("sector-accounts", "Household and business accounts", 2, ["nasq_10_ki", "nasq_10_nf_tr"], "Q", 85),
    "second release sector accounts (households)":
        R("sector-accounts-households", "Household accounts, second release", 2, ["nasq_10_ki"], "Q", 110),
    "economic sentiment indicator & business and consumer survey results":
        R("business-consumer-surveys", "Economic sentiment and business and consumer surveys", 2,
          ["ei_bssi_m_r2", "ei_bsco_m"], "M", -5),
    # tier 3: other Eurostat data releases worth listing
    "flash labour cost index": R("labour-costs-flash", "Labour cost index, flash estimate", 3, ["lc_lci_r2_q"], "Q", 45),
    "flash job vacancy statistics": R("job-vacancies-flash", "Job vacancies, flash estimate", 3, ["jvs_q_r21"], "Q", 45),
    "labour force survey - data":
        R("labour-force-survey", "Labour force survey, quarterly results", 3,
          ["lfsi_emp_q", "lfsi_sla_q", "lfsq_ergan"], "Q", 65),
    "labour market flow statistics in the eu": R("labour-flows", "Labour market flows", 3, ["lfsi_long_q"], "Q", 65),
    "building permits": R("building-permits", "Building permits", 3, ["sts_cobp_m"]),
    "industrial import prices": R("import-prices", "Industrial import prices", 3, ["sts_inpi_m"], "M", 28),
    "business registrations and bankruptcies":
        R("bankruptcies", "Business registrations and bankruptcies", 3, ["sts_rb_q"]),
    "eu/ea aggregates for detailed gdp and employment breakdowns by industry":
        R("gdp-by-industry", "GDP and employment by industry", 3, ["namq_10_a10", "namq_10_a10_e"], "Q", 45),
    "household consumption by purpose":
        R("consumption-by-purpose", "Household consumption by purpose", 3, ["nama_10_co3_p3"]),
    "monthly energy": R("energy", "Monthly energy statistics", 3, ["nrg_cb_gasm", "nrg_cb_oilm", "nrg_cb_em"]),
    "purchasing power parities results for": R("ppp", "Purchasing power parities", 3, ["prc_ppp_ind"]),
    "structure of government debt": R("government-debt-structure", "Structure of government debt", 3, []),
    "statistics related to the recovery and resilience facility":
        R("recovery-facility", "Recovery and Resilience Facility statistics", 3, []),
    "services turnover": R("services-turnover", "Services turnover", 3, ["sts_setu_m"]),
    "industrial turnover": R("industrial-turnover", "Industrial turnover", 3, ["sts_intv_m"]),
}

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


# --- iCalendar --------------------------------------------------------------------------------

def _unescape(v):
    return (v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";")
            .replace("\\\\", "\\").strip())


def parse_ical(text):
    """Return VEVENTs as dicts: ``date`` (datetime.date), ``time`` ("HH:MM" Brussels or None),
    ``summary``, ``categories`` (list), ``theme``, ``uid``."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold continuation lines
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        block = block.split("END:VEVENT")[0]
        props = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            key, _, params = name.partition(";")
            props.setdefault(key.upper(), (params, value.strip()))
        if "DTSTART" not in props or "SUMMARY" not in props:
            continue
        params, raw = props["DTSTART"]
        try:
            day, time = _ical_datetime(params, raw)
        except ValueError:
            continue
        cats = props.get("X-CATEGORY", ("", ""))[1]
        events.append({
            "date": day, "time": time,
            "summary": _unescape(props["SUMMARY"][1]),
            "categories": [c.strip() for c in _unescape(cats).split(",") if c.strip()],
            "theme": _unescape(props.get("X-THEME", ("", ""))[1]),
            "uid": props.get("UID", ("", ""))[1],
        })
    return events


def _ical_datetime(params, raw):
    if "VALUE=DATE" in params.upper() or len(raw) == 8:
        return datetime.datetime.strptime(raw[:8], "%Y%m%d").date(), None
    dt = datetime.datetime.strptime(raw[:15], "%Y%m%dT%H%M%S")
    if raw.endswith("Z"):
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        m = re.search(r"TZID=([^;]+)", params)
        dt = dt.replace(tzinfo=zoneinfo.ZoneInfo(m.group(1)) if m else BRUSSELS)
    dt = dt.astimezone(BRUSSELS)
    return dt.date(), dt.strftime("%H:%M")


def normalise(summary):
    s = summary.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


# --- reference periods --------------------------------------------------------------------------

def _period_end(freq, year, n):
    if freq == "A":
        return datetime.date(year, 12, 31)
    month = n if freq == "M" else 3 * n
    nxt = datetime.date(year + (month == 12), month % 12 + 1, 1)
    return nxt - datetime.timedelta(days=1)


def reference_period(freq, lag, release_date):
    """Latest period of ``freq`` whose last day + ``lag`` days falls on or before ``release_date``.

    Returns ``(code, label)`` such as ``("2026-11", "November")`` or ``("2026-Q3", "Q3 2026")``;
    the month label carries the year only when it differs from the release year.
    """
    if not freq:
        return None, None
    y = release_date.year
    n = {"M": release_date.month, "Q": (release_date.month - 1) // 3 + 1, "A": 1}[freq]
    for _ in range(40):
        if _period_end(freq, y, n) + datetime.timedelta(days=lag) <= release_date:
            break
        n -= 1
        if n == 0:
            y -= 1
            n = {"M": 12, "Q": 4, "A": 1}[freq]
    if freq == "A":
        return str(y), str(y)
    if freq == "Q":
        return f"{y}-Q{n}", f"Q{n} {y}"
    label = MONTHS[n - 1] + ("" if y == release_date.year else f" {y}")
    return f"{y}-{n:02d}", label


# --- registry scan: dataset -> series, charts, modules ------------------------------------------

def dataset_index(reg=None, methods=None):
    """Map dataset/flow code -> {"series": [...], "charts": [...], "modules": [...], "pages": [...]}.

    Charts come from series references (derived inputs expanded), from the methods register
    (``sources[].dataset``, which also covers charts drawn by ``build`` hooks) and from home tiles
    (a tile's chart counts even if its section has not been built yet). Tile charts come first.
    """
    if reg is None:
        try:
            from .registry import load
            reg = load()
        except Exception as e:  # noqa: BLE001 - a broken section module must not stop the calendar
            print(f"warning: registry not loaded ({type(e).__name__}: {e}); events get no chart ids")
            return {}
    if methods is None:
        methods = _load_methods()
    from .build import _static_uses
    out = {}

    def slot(ds):
        return out.setdefault(ds, {"series": [], "charts": [], "modules": [], "pages": [], "_tiles": []})

    def add(lst, v):
        if v and v not in lst:
            lst.append(v)

    by_series = {}
    for s in reg.series.values():
        if not s.dataset:
            continue
        e = slot(s.dataset)
        add(e["series"], s.id)
        add(e["modules"], s.module)
        by_series[s.id] = s.dataset
    for cid, chart in reg.charts.items():
        used = set()
        for sid in _static_uses(reg, chart):
            used.add(sid.split("__")[0])
        for ds in {by_series[s] for s in used if s in by_series}:
            e = slot(ds)
            add(e["charts"], cid)
            add(e["modules"], chart.module)
            add(e["pages"], chart.page)
    for entry in methods:
        cid = entry.get("id")
        chart = reg.charts.get(cid)
        if chart is None:
            continue
        for src in entry.get("sources") or []:
            ds = (src or {}).get("dataset")
            if ds in out:
                e = out[ds]
                add(e["charts"], cid)
                add(e["modules"], chart.module)
                add(e["pages"], chart.page)
    for t in reg.tiles:
        ds = by_series.get(t.series.split("__")[0])
        if ds:
            e = slot(ds)
            add(e["_tiles"], t.chart_id)
            add(e["modules"], t.module)
    for e in out.values():
        e["tiles"] = tiles = e.pop("_tiles")
        e["charts"] = tiles + sorted(c for c in e["charts"] if c not in tiles)
        e["modules"].sort()
        e["pages"].sort()
    return out


def _load_methods():
    try:
        with open(os.path.join(paths.SITE_DATA, "methods.json"), encoding="utf-8") as fh:
            return json.load(fh).get("entries", [])
    except (OSError, ValueError):
        return []


def charts_for(datasets, index):
    """Chart ids using any of ``datasets``: home-tile charts first, then the others."""
    out = []
    for field in ("tiles", "charts"):
        for ds in datasets:
            for c in (index.get(ds) or {}).get(field, []):
                if c not in out:
                    out.append(c)
    return out


# --- events -------------------------------------------------------------------------------------

def _event(day, key, time, title, publisher, tier, datasets, index, period=None):
    return {"id": f"{day.isoformat()}-{key}", "date": day.isoformat(), "time": time, "tz": TZ, "title": title,
            "publisher": publisher, "tier": tier, "datasets": list(datasets),
            "chart_ids": charts_for(datasets, index), "period": period}


def eurostat_events(ical_events, start, end, index):
    out = []
    for ev in ical_events:
        if not (start <= ev["date"] <= end):
            continue
        cats = ev["categories"]
        spec = RELEASES.get(normalise(ev["summary"]))
        euro = EURO_INDICATORS in cats
        if not euro and not (spec and "Data release" in cats):
            continue
        if spec is None:
            key = re.sub(r"[^a-z0-9]+", "-", normalise(ev["summary"])).strip("-")[:48]
            spec = R(key, ev["summary"], 2, [])
        code, label = reference_period(spec["freq"], spec["lag"], ev["date"])
        title = spec["title"] + (f", {label}" if label else "")
        out.append(_event(ev["date"], spec["key"], ev["time"] or spec["time"], title, "Eurostat", spec["tier"],
                          spec["datasets"], index, code))
    return out


def ecb_events(data, start, end, index):
    out = []
    proj = data.get("projections", {})
    months = proj.get("months", {})
    for m in data.get("meetings", []):
        day = datetime.date.fromisoformat(m["date"])
        if not (start <= day <= end):
            continue
        pc = data.get("press_conference_time", "14:45")
        out.append(_event(day, "ecb-decision", data.get("decision_time", "14:15"),
                          f"ECB monetary policy decision (press conference {pc})", "ECB", 1,
                          data.get("datasets", ["FM"]), index))
        who = months.get(str(day.month))
        if who:
            out.append(_event(day, "ecb-projections", pc, f"{who} macroeconomic projections", "ECB", 2,
                              proj.get("datasets", ["MPD"]), index))
    return out


def ec_events(data, start, end, index):
    out = []
    surveys = data.get("surveys", {})
    kinds = [("flash_consumer_confidence", "consumer-confidence-flash", "Consumer confidence, flash estimate"),
             ("business_and_consumer_surveys", "business-consumer-surveys",
              "Economic sentiment and business and consumer surveys")]
    for name, key, title in kinds:
        spec = surveys.get(name) or {}
        for ref, date in sorted((spec.get("dates") or {}).items()):
            day = datetime.date.fromisoformat(date)
            if not (start <= day <= end):
                continue
            y, m = int(ref[:4]), int(ref[5:7])
            label = MONTHS[m - 1] + ("" if y == day.year else f" {y}")
            out.append(_event(day, key, spec.get("time", "11:00"), f"{title}, {label}", "European Commission", 2,
                              spec.get("datasets", []), index, ref))
    fc = data.get("forecasts", {})
    for ed in fc.get("editions", []):
        if not ed.get("date"):
            continue
        day = datetime.date.fromisoformat(ed["date"])
        if start <= day <= end:
            key = "ec-forecast-" + re.sub(r"[^a-z0-9]+", "-", ed["edition"].lower()).strip("-")
            out.append(_event(day, key, ed.get("time") or fc.get("time", "11:00"),
                              f"European Commission economic forecast, {ed['edition']}", "European Commission", 2,
                              fc.get("datasets", []), index))
    return out


def build_events(start, end, ical_events, ecb=None, ec=None, index=None):
    """All events from ``start`` to ``end`` (dates, inclusive), sorted by date, time and tier.

    Duplicates (same ``id``) keep the later source: an EC survey date overrides the matching
    Eurostat entry.
    """
    index = index or {}
    by_id = {}
    for e in eurostat_events(ical_events, start, end, index):
        by_id.setdefault(e["id"], e)
    for e in ecb_events(ecb or {}, start, end, index) + ec_events(ec or {}, start, end, index):
        by_id[e["id"]] = e
    return sorted(by_id.values(), key=lambda e: (e["date"], e["time"] or "", e["tier"], e["title"]))


def validate(cal):
    """Contract check for calendar.json. Returns a list of error strings."""
    errs = []
    if not isinstance(cal.get("built_at"), str) or not cal["built_at"].endswith("Z"):
        errs.append("built_at must be an ISO UTC timestamp ending in Z")
    ids = set()
    for i, e in enumerate(cal.get("events", [])):
        w = f"event {i} ({e.get('id')})"
        try:
            datetime.date.fromisoformat(e.get("date", ""))
        except (TypeError, ValueError):
            errs.append(f"{w}: bad date {e.get('date')!r}")
        if not re.fullmatch(r"\d\d:\d\d", str(e.get("time", ""))):
            errs.append(f"{w}: bad time {e.get('time')!r}")
        if e.get("tz") != TZ:
            errs.append(f"{w}: tz must be {TZ}")
        if e.get("tier") not in (1, 2, 3):
            errs.append(f"{w}: tier must be 1, 2 or 3")
        for k in ("title", "publisher"):
            if not isinstance(e.get(k), str) or not e[k]:
                errs.append(f"{w}: {k} missing")
        for k in ("datasets", "chart_ids"):
            if not isinstance(e.get(k), list):
                errs.append(f"{w}: {k} must be a list")
        if e.get("id") in ids:
            errs.append(f"{w}: duplicate id")
        ids.add(e.get("id"))
    return errs


# --- I/O ------------------------------------------------------------------------------------------

def load_json(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


def fetch_ical(offline=False, log=print):
    """Return the iCal text, or None. Live fetch first (unless offline), then the raw cache."""
    if not offline:
        try:
            return http.get(EUROSTAT_ICAL, source="calendar", cache_id="eurostat_ical", ext="ics", tries=3).body
        except http.FetchError as e:
            log(f"warning: Eurostat iCal fetch failed ({e}); trying the cache")
    cached = http.read_cache("calendar", "eurostat_ical", "ics")
    return cached.body if cached else None


def today_brussels():
    return datetime.datetime.now(BRUSSELS).date()


def previous_eurostat_events(start, end):
    """Eurostat events from the last calendar.json, the fallback when the iCal is unavailable."""
    try:
        with open(CALENDAR_JSON, encoding="utf-8") as fh:
            old = json.load(fh).get("events", [])
    except (OSError, ValueError):
        return []
    return [e for e in old if e.get("publisher") == "Eurostat" and start.isoformat() <= e.get("date", "") <= end.isoformat()]


def make_calendar(start, end, offline=False, index=None, log=print):
    raw = fetch_ical(offline=offline, log=log)
    index = dataset_index() if index is None else index
    ecb, ec = load_json("ecb_meetings.json"), load_json("ec_events.json")
    if raw is not None:
        events = build_events(start, end, parse_ical(raw), ecb, ec, index)
    else:
        log("warning: no iCal available; keeping the Eurostat events of the previous calendar.json")
        kept = previous_eurostat_events(start, end)
        for e in kept:
            e["chart_ids"] = charts_for(e.get("datasets", []), index) or e.get("chart_ids", [])
        events = build_events(start, end, [], ecb, ec, index)
        events = sorted(kept + events, key=lambda e: (e["date"], e["time"] or "", e["tier"], e["title"]))
    built_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"built_at": built_at, "from": start.isoformat(), "to": end.isoformat(), "events": events}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write site/data/calendar.json (today to +45 days).")
    ap.add_argument("--start", help="first date, YYYY-MM-DD (default: today in Brussels)")
    ap.add_argument("--days", type=int, default=WINDOW_DAYS, help="days after the start (default 45)")
    ap.add_argument("--offline", action="store_true", help="use the cached iCal only")
    ap.add_argument("--print", dest="show", action="store_true", help="print the events")
    ap.add_argument("--out", default=CALENDAR_JSON, help="output path (default site/data/calendar.json)")
    a = ap.parse_args(argv)
    start = datetime.date.fromisoformat(a.start) if a.start else today_brussels()
    end = start + datetime.timedelta(days=a.days)
    cal = make_calendar(start, end, offline=a.offline)
    errs = validate(cal)
    for e in errs:
        print("ERROR:", e)
    if errs:
        return 1
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(cal, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    ev = cal["events"]
    tiers = {t: sum(1 for e in ev if e["tier"] == t) for t in (1, 2, 3)}
    linked = sum(1 for e in ev if e["chart_ids"])
    print(f"calendar: {len(ev)} events {cal['from']} to {cal['to']} (tier 1: {tiers[1]}, tier 2: {tiers[2]}, "
          f"tier 3: {tiers[3]}; {linked} linked to charts) -> {os.path.relpath(a.out, paths.ROOT)}")
    if a.show:
        for e in ev:
            print(f"  {e['date']} {e['time']}  t{e['tier']}  {e['publisher']:20} {e['title'][:60]:60} "
                  f"{','.join(e['chart_ids'][:3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
