"""Release-morning detection: has a publisher updated the series behind today's calendar events?

    cd pipeline
    python3 -m eet.release                    # today's events (Brussels date)
    python3 -m eet.release --date 2026-11-04  # any date the Eurostat iCal covers
    python3 -m eet.release --alerts           # after the rebuild: write the data notes

Exit status: **0** if at least one mapped series changed (rebuild), **3** if nothing changed or
there is nothing to check (skip), 1 on a crash, 2 on bad arguments.

How it decides. For each event of the day, the event's datasets (see ``eet.calendar``) are mapped
to the registry series that use them. Then, cheaply, without downloading data:

* Eurostat: one request for the statistics-update RSS (about 300 KB, a week of dataset updates
  with timestamps). A dataset's newest RSS timestamp is compared with each series' stored
  publisher stamp (``store/_meta.json`` ``updated``). Datasets absent from the RSS get a minimal
  JSON-stat query (``lastTimePeriod=1``) whose ``updated`` field is read instead.
* ECFIN (Redisstat): the minimal JSON-stat query.
* ECB: one request per series key with ``updatedAfter=<stored stamp + 1 s>`` (the ECB treats the
  value as inclusive). HTTP 404 means nothing changed; 200 means new data, and ``Last-Modified``
  is the new stamp.

A series counts as changed only when the publisher stamp is later than the stored one (or the
series was never fetched), so a calendar error can never fire an alert by itself.

The run prints the changed series, the registry modules to rebuild (``--only`` arguments for
``eet.build``) and the pages they feed; on GitHub Actions it also writes ``changed``, ``modules``
and ``releases`` to ``$GITHUB_OUTPUT``. The result is saved to ``pipeline/.cache/release/state.json``.

``--alerts`` (run after ``eet.build`` has rebuilt those modules) reads that state and writes, for
each changed tier-1 or tier-2 release, a numbers-only data note to
``outbox/alerts/<event id>.md``: latest value, previous, change, period, source line and a link to
the chart anchor, taken from the rebuilt chart bundles. Nothing is sent: email is planned, not
built (ROADMAP.md).
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import urllib.parse
import zoneinfo

from . import calendar as cal
from . import http, paths, sources

RSS_URL = "https://ec.europa.eu/eurostat/api/dissemination/catalogue/rss/en/statistics-update.rss"
SITE_URL = "https://pietrovaletto.github.io/european-economy-tracker/"
OUTBOX = os.path.join(paths.ROOT, "outbox", "alerts")
STATE = os.path.join(paths.CACHE, "release", "state.json")
LUX = zoneinfo.ZoneInfo("Europe/Luxembourg")  # Eurostat RSS pubDate is local time without offset
MAX_CHARTS = 5
WORKERS = 6        # parallel stamp checks (ECB answers slowly, sometimes with a 504 after 30 s)
PROBE_TIMEOUT = 25  # seconds; one try: a missed probe is retried by the next 5-minute poll
EXIT_CHANGED, EXIT_NOTHING = 0, 3


# --- stamps ---------------------------------------------------------------------------------------

def parse_stamp(value, tz=datetime.timezone.utc):
    """Publisher stamps in any of the shapes we store or receive -> aware datetime (or None).

    '2026-11-04T11:00:00+0100', '2026-11-04T10:06:25+00:00', '2026-11-04T10:06:25Z',
    '2026-11-09 11:00:00.0' (no offset: ``tz`` applies), 'Wed, 04 Nov 2026 10:06:25 GMT'.
    """
    if not value:
        return None
    v = str(value).strip()
    if re.match(r"^[A-Za-z]{3}, ", v):
        iso = http.http_date_to_iso(v)
        return parse_stamp(iso) if iso else None
    v = v.replace(" ", "T", 1)
    v = re.sub(r"Z$", "+00:00", v)
    v = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", v)
    v = re.sub(r"(T\d\d:\d\d:\d\d)\.\d+", r"\1", v)
    try:
        d = datetime.datetime.fromisoformat(v)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=tz)
    return d


def fmt_stamp(d):
    return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def stored_stamp(meta, sid):
    """Newest stored ``updated`` for a series or, for a panel, any of its children."""
    best = None
    for k, m in meta.items():
        if k == sid or k.startswith(sid + "__"):
            d = parse_stamp((m or {}).get("updated"))
            if d and (best is None or d > best):
                best = d
    return best


def parse_rss(body):
    """Eurostat statistics-update RSS -> {dataset code (lower case): newest data-update datetime}."""
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    out = {}
    for item in re.findall(r"<item>(.*?)</item>", body, flags=re.S):
        title = re.search(r"<title>([^<]*)</title>", item)
        cat = re.search(r"<category>([^<]*)</category>", item)
        pub = re.search(r"<pubDate>([^<]*)</pubDate>", item)
        if not (title and pub) or (cat and "DATA" not in cat.group(1)):
            continue
        code = title.group(1).split(" - ")[0].strip().lower()
        d = parse_stamp(pub.group(1), tz=LUX)
        if d and (code not in out or d > out[code]):
            out[code] = d
    return out


# --- polling --------------------------------------------------------------------------------------

def minimal_jsonstat_url(s):
    base = sources.EUROSTAT if s.source == "eurostat" else sources.ECFIN
    q = []
    for k, v in s.filters.items():
        for code in (v if isinstance(v, (list, tuple)) else [v]):
            q.append((k, code))
    q += [("lastTimePeriod", "1"), ("format", "JSON"), ("lang", "EN")]
    return base + s.dataset + "?" + urllib.parse.urlencode(q)


def ecb_probe_url(s, after):
    q = [("updatedAfter", fmt_stamp(after)), ("detail", "dataonly"), ("format", "csvdata"), ("lastNObservations", "1")]
    return f"{sources.ECB}{s.dataset}/{s.key}?" + urllib.parse.urlencode(q)


class Poller:
    """Cheap publisher-stamp checks. ``get(url)`` returns an ``http.Response`` or raises FetchError."""

    def __init__(self, get=None, log=print):
        self.get = get or (lambda url: http.get(url, cache=False, tries=1, timeout=PROBE_TIMEOUT))
        self.log = log
        self._rss = None
        self._jsonstat = {}

    def rss(self):
        if self._rss is None:
            try:
                self._rss = parse_rss(self.get(RSS_URL).body)
            except http.FetchError as e:
                self.log(f"  warning: Eurostat RSS unavailable ({e}); using JSON-stat stamps")
                self._rss = {}
        return self._rss

    def jsonstat_stamp(self, s):
        url = minimal_jsonstat_url(s)
        if url not in self._jsonstat:
            r = self.get(url)
            self._jsonstat[url] = parse_stamp(http.extract_updated(r.body, r.headers))
        return self._jsonstat[url]

    def check(self, s, stored):
        """Return ``(status, publisher stamp, how)``: status is changed, unchanged, unknown or error."""
        try:
            if s.source == "eurostat":
                stamp = self.rss().get(s.dataset.lower())
                how = "rss"
                if stamp is None:
                    stamp, how = self.jsonstat_stamp(s), "json-stat"
            elif s.source == "ecfin":
                stamp, how = self.jsonstat_stamp(s), "json-stat"
            elif s.source == "ecb":
                if stored is None:
                    return "changed", None, "never fetched"
                try:
                    r = self.get(ecb_probe_url(s, stored + datetime.timedelta(seconds=1)))
                except http.FetchError as e:
                    if e.status == 404:
                        return "unchanged", stored, "updatedAfter 404"
                    raise
                stamp = parse_stamp(http.extract_updated(b"", r.headers)) or stored + datetime.timedelta(seconds=1)
                return ("changed" if stamp > stored else "unchanged"), stamp, "updatedAfter 200"
            else:
                return "unknown", None, f"no cheap check for {s.source}"
        except http.FetchError as e:
            return "error", None, str(e)[:120]
        if stamp is None:
            return "unknown", None, how + ": no stamp"
        if stored is None or stamp > stored:
            return "changed", stamp, how
        return "unchanged", stamp, how


# --- detection ------------------------------------------------------------------------------------

def events_for(day, offline=False, log=print):
    """Calendar events on ``day``: from site/data/calendar.json when it covers the date, else rebuilt
    for that single day from the Eurostat iCal and the hand-maintained ECB and EC files."""
    try:
        with open(cal.CALENDAR_JSON, encoding="utf-8") as fh:
            c = json.load(fh)
        if c.get("from", "9999") <= day.isoformat() <= c.get("to", ""):
            return [e for e in c.get("events", []) if e.get("date") == day.isoformat()]
    except (OSError, ValueError):
        pass
    return cal.make_calendar(day, day, offline=offline, log=log)["events"]


def detect(day, events, reg, meta, index, poller, log=print):
    """Check every series behind ``events``. Returns the state dict (see module docstring)."""
    per_event = []
    for ev in events:
        sids = []
        for ds in ev.get("datasets", []):
            for sid in (index.get(ds) or {}).get("series", []):
                if sid not in sids and sid in reg.series:
                    sids.append(sid)
        per_event.append(sids)
    todo = sorted({sid for sids in per_event for sid in sids})
    if any(reg.series[sid].source == "eurostat" for sid in todo):
        poller.rss()  # one shared request, before the parallel checks

    def one(sid):
        s = reg.series[sid]
        stored = stored_stamp(meta, sid)
        status, stamp, how = poller.check(s, stored)
        return {"series": sid, "source": s.source, "dataset": s.dataset, "status": status,
                "stored": fmt_stamp(stored), "publisher": fmt_stamp(stamp), "how": how, "module": s.module}

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        checked = dict(zip(todo, pool.map(one, todo)))
    releases = []
    for ev, sids in zip(events, per_event):
        rows = [checked[sid] for sid in sids]
        changed = [r["series"] for r in rows if r["status"] == "changed"]
        modules, pages, charts = set(), set(), []
        for r in rows:
            if r["status"] != "changed":
                continue
            entry = index.get(r["dataset"]) or {}
            modules.update(entry.get("modules", []))
            pages.update(entry.get("pages", []))
        if changed:
            charts = alert_charts(reg, index, ev, rows)
        releases.append({"event": ev, "series": rows, "changed": changed, "modules": sorted(modules),
                         "pages": sorted(pages), "charts": charts})
    modules = sorted({m for r in releases for m in r["modules"]})
    return {"date": day.isoformat(),
            "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "changed": any(r["changed"] for r in releases), "modules": modules,
            "pages": sorted({p for r in releases for p in r["pages"]}),
            "releases": releases}


def alert_charts(reg, index, ev, rows):
    """Charts for a changed release: those drawing a changed series first, then other charts of the
    changed datasets (``build``-hook charts are known only by dataset); home-tile charts lead each group."""
    from .build import _static_uses
    changed = {r["series"] for r in rows if r["status"] == "changed"}
    datasets = sorted({r["dataset"] for r in rows if r["status"] == "changed"})
    allowed = cal.charts_for(datasets, index)
    listed = [c for c in ev.get("chart_ids", []) if c in reg.charts and c in allowed]
    pool = listed + [c for c in allowed if c not in listed and c in reg.charts]

    def direct(cid):
        return any(u.split("__")[0] in changed for u in _static_uses(reg, reg.charts[cid]))

    return [c for c in pool if direct(c)] + [c for c in pool if not direct(c)]


def report(state, log=print):
    log(f"Release check {state['date']} (checked {state['checked_at']}): {len(state['releases'])} event(s)")
    for r in state["releases"]:
        ev = r["event"]
        log(f"  {ev.get('time', ''):5} tier {ev.get('tier')}  {ev.get('title')}  [{', '.join(ev.get('datasets', [])) or 'no datasets'}]")
        if not r["series"]:
            log("        no tracked series use these datasets")
        for row in r["series"]:
            log(f"        {row['status'].upper():9} {row['series']:30} {row['dataset']:16} stored {row['stored'] or '-':20} "
                f"publisher {row['publisher'] or '-':20} ({row['how']})")
    changed = sorted({s for r in state["releases"] for s in r["changed"]})
    if changed:
        log(f"Changed series ({len(changed)}): {', '.join(changed)}")
        log(f"Modules to rebuild: {', '.join(state['modules'])}; pages: {', '.join(state['pages']) or '-'}")
        log("Rebuild: python3 -m eet.build " + " ".join(f"--only {m}" for m in state["modules"]))
    else:
        log("Nothing changed.")


def save_state(state, path=STATE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)


def github_output(state):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    ids = [r["event"].get("id", "") for r in state["releases"] if r["changed"]]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"changed={'true' if state['changed'] else 'false'}\n")
        fh.write(f"modules={','.join(state['modules'])}\n")
        fh.write(f"releases={','.join(ids)}\n")


# --- alerts ---------------------------------------------------------------------------------------

def _num(v, d):
    return "n/a" if v is None else f"{v:,.{d}f}"


def _chg(a, b, d, fmt):
    if a is None or b is None:
        return "n/a"
    unit = " pp" if fmt in ("pct", "pp") else ""
    x = round(a - b, d)
    return f"{x:+,.{d}f}{unit}" if x != 0 else f"{0:.{d}f}{unit}"


def chart_rows(b):
    """Table rows (label, period, latest, previous, change) from one chart bundle."""
    latest, prev = b.get("latest") or {}, b.get("previous") or {}
    vals, pvals = latest.get("values") or {}, prev.get("values") or {}
    d = b.get("decimals", 1)
    fmt = b.get("format", "pct")
    labels = {s.get("key"): s.get("label") or s.get("key") for s in b.get("series", [])}
    periods = latest.get("periods") or {}
    rows = []
    for key, v in vals.items():
        if not isinstance(v, (int, float)):
            continue
        pv = pvals.get(key)
        pv = pv if isinstance(pv, (int, float)) else None
        rows.append((labels.get(key, key), periods.get(key, latest.get("period", "")), _num(v, d),
                     _num(pv, d), _chg(v, pv, d, fmt)))
    return rows


def render_alert(release, bundles, site_url=SITE_URL):
    """Markdown data note for one changed release. ``bundles``: chart id -> bundle dict."""
    ev = release["event"]
    lines = [f"# {ev.get('title')}", "",
             f"- Released: {ev.get('date')} {ev.get('time', '')} Brussels time",
             f"- Publisher: {ev.get('publisher')}",
             f"- Tier: {ev.get('tier')}"]
    if ev.get("period"):
        lines.append(f"- Reference period: {ev['period']}")
    lines.append(f"- Updated series: {', '.join(release['changed'])}")
    shown = 0
    for cid in release.get("charts", []):
        b = bundles.get(cid)
        if not b or shown >= MAX_CHARTS:
            continue
        rows = chart_rows(b)
        if not rows:
            continue
        shown += 1
        lines += ["", f"## {b.get('title') or cid}"]
        if b.get("subtitle"):
            lines += ["", b["subtitle"]]
        lines += ["", "| Series | Period | Latest | Previous | Change |", "|---|---|---:|---:|---:|"]
        lines += [f"| {a} | {p} | {l} | {pv} | {c} |" for a, p, l, pv, c in rows]
        lines += ["", f"Source: {b.get('source', '')}" + (f" ({b['data_updated']})" if b.get("data_updated") else ""),
                  f"Chart: {site_url}{b.get('page')}/#{cid}"]
    if not shown:
        lines += ["", "No chart bundle uses these series yet."]
    lines += ["", f"Detected {release.get('checked_at', '')}. Numbers only; generated by eet.release.", ""]
    return "\n".join(lines)


def write_alerts(state, charts_dir=paths.CHARTS, outbox=OUTBOX, log=print):
    written = []
    bundles = {}
    for r in state["releases"]:
        if not r["changed"] or r["event"].get("tier", 3) > 2:
            continue
        for cid in r.get("charts", []):
            if cid not in bundles:
                try:
                    with open(os.path.join(charts_dir, f"{cid}.json"), encoding="utf-8") as fh:
                        bundles[cid] = json.load(fh)
                except (OSError, ValueError):
                    pass
        r = dict(r, checked_at=state.get("checked_at"))
        ev = r["event"]
        name = ev.get("id") or f"{ev.get('date')}-{re.sub(r'[^a-z0-9]+', '-', ev.get('title', '').lower()).strip('-')}"
        os.makedirs(outbox, exist_ok=True)
        path = os.path.join(outbox, f"{name}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_alert(r, bundles))
        written.append(path)
        log(f"alert: {os.path.relpath(path, paths.ROOT) if path.startswith(paths.ROOT) else path}")
    if not written:
        log("alerts: no changed tier-1 or tier-2 release")
    return written


# --- entry point ----------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Detect publisher updates for the day's calendar events.")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in Brussels)")
    ap.add_argument("--alerts", action="store_true", help="write data notes from the saved state and current bundles")
    ap.add_argument("--meta", default=None, help="publisher stamps file (default store/_meta.json)")
    ap.add_argument("--state", default=STATE, help="state file (default pipeline/.cache/release/state.json)")
    ap.add_argument("--outbox", default=OUTBOX, help="alert folder (default outbox/alerts)")
    ap.add_argument("--offline", action="store_true", help="calendar from the cached iCal (polling is always live)")
    a = ap.parse_args(argv)

    if a.alerts:
        try:
            with open(a.state, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            print(f"no release state at {a.state}; run python3 -m eet.release first")
            return EXIT_NOTHING
        written = write_alerts(state, outbox=a.outbox)
        return EXIT_CHANGED if written else EXIT_NOTHING

    try:
        day = datetime.date.fromisoformat(a.date) if a.date else cal.today_brussels()
    except ValueError:
        print(f"bad --date {a.date!r}")
        return 2
    from .registry import load
    reg = load()
    meta_path = a.meta or os.path.join(paths.STORE, "_meta.json")
    try:
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        meta = {}
    events = events_for(day, offline=a.offline)
    if not events:
        print(f"Release check {day}: no calendar events; nothing to do.")
        state = {"date": day.isoformat(), "checked_at": "", "changed": False, "modules": [], "pages": [], "releases": []}
        save_state(state, a.state)
        github_output(state)
        return EXIT_NOTHING
    index = cal.dataset_index(reg)
    http.reset()
    state = detect(day, events, reg, meta, index, Poller())
    report(state)
    save_state(state, a.state)
    github_output(state)
    return EXIT_CHANGED if state["changed"] else EXIT_NOTHING


if __name__ == "__main__":
    sys.exit(main())
