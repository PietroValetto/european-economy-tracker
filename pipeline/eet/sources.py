"""Turn a registry Series into a request URL, fetch it, parse it, and return observations.

One function per publisher family. ``fetch(series)`` returns a FetchResult whose ``obs`` maps a
series id (or ``<id>__<code>`` for panel children) to its observation list. National publishers
(Bundesbank, INSEE, CBS, ISTAT, GUS) and the Indeed wage tracker are at the end of the file.
"""
import datetime as _dt
import json as _json
import time as _time
import urllib.parse
from dataclasses import dataclass, field

from . import http
from . import periods as _P
from . import store as _store
from .parsers import csvdata, jsonstat, national

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ECFIN = "https://webgate.ec.europa.eu/ecfin/redisstat/api/dissemination/statistics/1.0/data/"
ECB = "https://data-api.ecb.europa.eu/service/data/"
BIS = "https://stats.bis.org/api/v1/data/"
OECD = "https://sdmx.oecd.org/public/rest/data/"
INDEED = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/"


# OBS_STATUS codes that mean "normal value": dropped by the parser so they never show as a flag.
NORMAL_FLAGS = {"bis": ("A",), "oecd": ("A",)}


class EmptySeries(ValueError):
    pass


@dataclass
class FetchResult:
    obs: dict = field(default_factory=dict)       # id -> obs
    empty: list = field(default_factory=list)     # panel children with no observations
    updated: str | None = None
    url: str = ""
    secs: float = 0.0
    attempts: int = 1


def child_id(sid, code):
    return f"{sid}__{code}"


def url_for(s):
    """The request URL for a Series."""
    fam = family(s)
    if fam is not None:
        return _family_url(s, fam)
    if s.source in ("eurostat", "ecfin"):
        q = []
        for k, v in s.filters.items():
            for code in (v if isinstance(v, (list, tuple)) else [v]):
                q.append((k, code))
        if s.start:
            q.append(("sinceTimePeriod", s.start))
        q += [("format", "JSON"), ("lang", "EN")]
        base = EUROSTAT if s.source == "eurostat" else ECFIN
        return base + s.dataset + "?" + urllib.parse.urlencode(q)
    if s.source == "ecb":
        q = [("format", "csvdata"), ("detail", "dataonly")]
        if s.start:
            q.append(("startPeriod", s.start))
        return f"{ECB}{s.dataset}/{s.key}?" + urllib.parse.urlencode(q)
    if s.source == "bis":
        q = [("format", "csv")]
        if s.start:
            q.append(("startPeriod", s.start))
        return f"{BIS}{s.dataset}/{s.key}/all?" + urllib.parse.urlencode(q)
    if s.source == "oecd":
        q = [("format", "csvfile")]
        if s.start:
            q.append(("startPeriod", s.start))
        return f"{OECD}{s.dataset}/{s.key}?" + urllib.parse.urlencode(q)
    if s.source == "indeed":
        cc = s.dataset
        return f"{INDEED}{cc}/aggregate_job_postings_{cc}.csv"
    if s.source == "csv":
        return s.dataset
    raise ValueError(f"unknown source {s.source}")


def display_url(s):
    """A human page for the source line (data browser rather than API)."""
    if s.source_url:
        return s.source_url
    if s.source == "eurostat":
        return f"https://ec.europa.eu/eurostat/databrowser/view/{s.dataset}/default/table"
    if s.source == "ecfin":
        return "https://economy-finance.ec.europa.eu/economic-research-and-databases/economic-databases_en"
    if s.source == "ecb":
        if s.split is None and "+" not in s.key and ".." not in s.key:
            return f"https://data.ecb.europa.eu/data/datasets/{s.dataset}/{s.dataset}.{s.key}"
        return f"https://data.ecb.europa.eu/data/datasets/{s.dataset}"
    if s.source == "bis":
        return f"https://data.bis.org/topics/{s.dataset}"
    if s.source == "oecd":
        return "https://data-explorer.oecd.org/"
    if s.source == "indeed":
        return "https://github.com/hiring-lab/job_postings_tracker"
    if s.source in FAMILY_HOME:
        return FAMILY_HOME[s.source]
    return url_for(s)


def source_text(s):
    if s.source_name:
        return s.source_name
    pub = {"eurostat": "Eurostat", "ecfin": "European Commission", "ecb": "ECB", "bis": "BIS",
           "oecd": "OECD", "indeed": "Indeed Hiring Lab", "bundesbank": "Bundesbank", "insee": "INSEE",
           "cbs": "CBS", "istat": "ISTAT", "gus": "GUS", "indeed_wages": "Indeed Hiring Lab"}.get(s.source, "")
    if s.source in ("eurostat", "ecfin"):
        return f"{pub} ({s.dataset})"
    if s.source in ("ecb", "bis"):
        return f"{pub} ({s.dataset})"
    return pub


def _scale(obs, k):
    if k == 1.0:
        return obs
    return [(p, v * k, f) for p, v, f in obs]


def parse_body(s, body):
    """Parse a response body for Series ``s``. Returns ``({id: obs}, updated_from_body)``."""
    fam = family(s)
    if fam is not None:
        return _parse_family(s, fam, body)
    updated = None
    if s.source in ("eurostat", "ecfin"):
        if s.split is not None:
            groups, updated = jsonstat.parse_multi(body, split=s.split)
        else:
            obs, updated = jsonstat.parse(body)
            groups = {None: obs}
    else:
        period_col = s.period_col or ("date" if s.source == "indeed" else "TIME_PERIOD")
        value_col = s.value_col or ("indeed_job_postings_index_SA" if s.source == "indeed" else "OBS_VALUE")
        flag_col = s.flag_col or ("" if s.source == "indeed" else "OBS_STATUS")
        where = s.filters if s.source in ("indeed", "csv") else None
        normal = NORMAL_FLAGS.get(s.source, ())
        if s.split is not None:
            group_by = csvdata.ecb_key_part(s.split) if isinstance(s.split, int) else s.split
            groups = csvdata.parse_multi(body, group_by, period_col, value_col, flag_col, where=where,
                                         normal=normal)
        else:
            groups = {None: csvdata.parse(body, period_col, value_col, flag_col, where=where, normal=normal)}
    out = {}
    for code, obs in groups.items():
        if code is None:
            out[s.id] = _scale(obs, s.scale)
        elif s.keep is None or s.keep(code):
            out[child_id(s.id, code)] = _scale(obs, s.scale)
    return out, updated


def fetch(s, offline=False):
    """Fetch and parse one registry Series. Raises on HTTP errors and on empty results."""
    fam = family(s)
    if fam is not None:
        return _fetch_family(s, fam, offline=offline)
    url = url_for(s)
    ext = "json" if s.source in ("eurostat", "ecfin") else "csv"
    if offline:
        resp = http.read_cache(s.source, s.id, ext)
        if resp is None:
            raise http.FetchError("offline and no cached response")
    else:
        resp = http.get(url, source=s.source, cache_id=s.id, ext=ext)
    groups, updated = parse_body(s, resp.body)
    res = FetchResult(updated=updated or resp.updated, url=url, secs=resp.secs, attempts=resp.attempts)
    for sid, obs in groups.items():
        if obs:
            res.obs[sid] = obs
        else:
            res.empty.append(sid)
    if not res.obs:
        raise EmptySeries("no observations returned (check the filter codes: Eurostat answers bad codes "
                          "with an empty 200)")
    return res


# =========================================================================== national families
#
# National statistical offices and agencies (research/04_national_sources.md) and the Indeed wage
# tracker. A Series names its family as its ``source`` (``spec.NATIONAL``); ``dataset`` is the full
# request URL, built from the prefixes below.
#
#   bundesbank    dataset = BUNDESBANK + "<FLOW>/<KEY>"               one CSV per series
#   insee         dataset = INSEE_BDM + "SERIES_BDM/<IDBANK>"          SDMX-ML
#   cbs           dataset = CBS + "<table id>", filters = {dim: code}, value_col = topic key
#                 (one OData request plus TableInfos for the update stamp)
#   istat         dataset = ISTAT + "<flow ref>/<key with {EDITION}>"  two requests: the newest
#                 release edition is discovered first (research/04: the EDITION trap)
#   gus           dataset = GUS_DBW + "...variable-data-section?id-zmienna=N&id-przekroj=M",
#                 filters = {"position": id-pozycja-2, "measure": id-sposob-prezentacji-miara};
#                 one request per month: each run refetches the last GUS_REFRESH months and
#                 backfills at most GUS_BUDGET months the vintage store lacks (quota 100 per 15 min)
#   indeed_wages  dataset = INDEED_WAGES + "<file>.csv", split = "jobcountry", value_col

BUNDESBANK = "https://api.statistiken.bundesbank.de/rest/data/"
INSEE_BDM = "https://bdm.insee.fr/series/sdmx/data/"
CBS = "https://opendata.cbs.nl/ODataApi/odata/"
ISTAT = "https://esploradati.istat.it/SDMXWS/rest/data/"
GUS_DBW = "https://api-dbw.stat.gov.pl/api/"
INDEED_WAGES = "https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/"

FAMILY_PREFIXES = {"bundesbank": BUNDESBANK, "insee": INSEE_BDM, "cbs": CBS, "istat": ISTAT, "gus": GUS_DBW,
                   "indeed_wages": INDEED_WAGES}
FAMILY_HOME = {"bundesbank": "https://www.bundesbank.de/en/statistics/time-series-databases",
               "insee": "https://www.insee.fr/en/statistiques", "cbs": "https://opendata.cbs.nl/statline/",
               "istat": "https://esploradati.istat.it/databrowser/", "gus": "https://dbw.stat.gov.pl/",
               "indeed_wages": "https://github.com/hiring-lab/indeed-wage-tracker"}
FAMILY_EXT = {"bundesbank": "csv", "insee": "xml", "cbs": "json", "istat": "csv", "gus": "json",
              "indeed_wages": "csv"}

ISTAT_PAUSE = 13.0     # seconds between ISTAT requests (documented limit: 5 per minute)
ISTAT_TIMEOUT = 120    # ISTAT data queries take 1 to 40 s
GUS_PAUSE = 0.3        # seconds between GUS month requests (limit: 10,000 per 7 days)
GUS_REFRESH = 6        # months refetched on every run once the store holds the history
GUS_BUDGET = 48        # month requests per series per run (quota: 100 calls per 15 minutes)
_last_istat = [0.0]


def family(s):
    """The national family name for Series ``s``, or None for the core families."""
    return s.source if s.source in FAMILY_PREFIXES else None


def _cbs_filter(s, start_year=None):
    parts = [f"{k} eq '{v}'" for k, v in s.filters.items()]
    if start_year:
        parts.append(f"substring(Perioden,0,4) ge '{start_year}'")
    return " and ".join(parts)


def _family_url(s, fam):
    """The (main) request URL of a national-family Series; ISTAT keeps its {EDITION} placeholder."""
    if fam == "bundesbank":
        q = [("format", "csv"), ("lang", "en")]
        if s.start:
            q.insert(0, ("startPeriod", s.start))
        return s.dataset + "?" + urllib.parse.urlencode(q)
    if fam == "insee":
        return s.dataset + ("?" + urllib.parse.urlencode([("startPeriod", s.start)]) if s.start else "")
    if fam == "cbs":
        q = [("$filter", _cbs_filter(s, s.start[:4] if s.start else None)),
             ("$select", f"Perioden,{s.value_col}")]
        return s.dataset.rstrip("/") + "/TypedDataSet?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    if fam == "istat":
        q = [("format", "csv")]
        if s.start:
            q.insert(0, ("startPeriod", s.start))
        return s.dataset + "?" + urllib.parse.urlencode(q)
    if fam == "gus":
        return s.dataset
    return s.dataset  # indeed_wages: the file itself


def _parse_family(s, fam, body):
    """Parse one stored body of a national-family Series. Returns ``({id: obs}, updated)``."""
    updated = None
    if fam == "bundesbank":
        obs, updated = national.bundesbank(body)
        groups = {None: obs}
    elif fam == "insee":
        obs, updated = national.insee(body)
        groups = {None: obs}
    elif fam == "cbs":
        groups = {None: national.cbs(body, s.value_col)}
    elif fam == "istat":
        groups = {None: csvdata.parse(body, s.period_col or "TIME_PERIOD", s.value_col or "OBS_VALUE",
                                      s.flag_col or "OBS_STATUS")}
    elif fam == "gus":  # the family's own cache: {"values": {period: value}, "updated": ...}
        d = _json.loads(body)
        groups = {None: [(p, float(v), "") for p, v in sorted(d.get("values", {}).items()) if v is not None]}
        updated = d.get("updated")
    elif fam == "indeed_wages":
        groups = national.indeed_wages(body, value_col=s.value_col or "posted_wage_growth_yoy_3moavg")
        if s.split is None:
            raise ValueError("indeed_wages series need split='jobcountry'")
    else:
        raise ValueError(f"unknown family {fam}")
    out = {}
    for code, obs in groups.items():
        if code is None:
            out[s.id] = _scale(obs, s.scale)
        elif s.keep is None or s.keep(code):
            out[child_id(s.id, code)] = _scale(obs, s.scale)
    return out, updated


def _result(s, groups, updated, url, secs=0.0, attempts=1):
    res = FetchResult(updated=updated, url=url, secs=secs, attempts=attempts)
    for sid, obs in groups.items():
        if obs:
            res.obs[sid] = obs
        else:
            res.empty.append(sid)
    if not res.obs:
        raise EmptySeries(f"no observations returned by {family(s)} (check the key or filters)")
    return res


def _istat_wait():
    gap = _time.time() - _last_istat[0]
    if _last_istat[0] and gap < ISTAT_PAUSE:
        http._sleep(ISTAT_PAUSE - gap)
    _last_istat[0] = _time.time()


def _today():
    return _dt.date.today()


def _gus_months(s):
    """Months to request this run, newest first, at most GUS_BUDGET of them.

    The last GUS_REFRESH months are always refetched (revisions, the newest release); older
    months are requested only while the vintage store lacks them, so the first runs backfill the
    history GUS_BUDGET months at a time (the DBW API admits 100 calls per 15 minutes).
    """
    last = _P.shift(_P.from_date(_today(), "M"), -1)
    first = s.start or "2015-01"
    if first > last:
        return []
    wanted = _P.period_range(first, last)
    meta = _store.load_meta().get(s.id, {})
    stored = set()
    if meta.get("spec") == _store.spec_hash(s):
        stored = {p for p, v, _ in _store.load(s.id) if v is not None}
    refresh = wanted[-GUS_REFRESH:]
    missing = [m for m in reversed(wanted[:-GUS_REFRESH]) if m not in stored]
    return (list(reversed(refresh)) + missing)[:GUS_BUDGET]


def _fetch_gus(s):
    position, measure = s.filters.get("position"), s.filters.get("measure")
    if position is None or measure is None:
        raise ValueError("gus series need filters position and measure")
    values, t0, n, stopped = {}, _time.time(), 0, None
    for m in _gus_months(s):
        y, mm = int(m[:4]), int(m[5:7])
        url = (f"{s.dataset}&id-rok={y}&id-okres={national.gus_period_id(mm)}&ile-na-stronie=5000")
        try:
            resp = http.get(url, source="gus", cache=False, timeout=30)
        except http.FetchError as e:
            if e.status == 404:  # month not published (yet)
                continue
            if e.status == 429 and values:  # quota: keep what this run got, the next run continues
                stopped = str(e)[:120]
                break
            raise
        n += 1
        try:
            v = national.gus_value(resp.body, position, measure)
        except ValueError:  # an empty or truncated body: try once more
            http._sleep(2.0)
            http._memo.pop(url, None)
            v = national.gus_value(http.get(url, source="gus", cache=False, timeout=30).body, position, measure)
        if v is not None:
            values[m] = v
        http._sleep(GUS_PAUSE)
    body = _json.dumps({"values": dict(sorted(values.items())), "updated": None, "months_requested": n,
                        "stopped": stopped}).encode()
    resp = http.Response(url=s.dataset, status=200, body=body, secs=round(_time.time() - t0, 2), attempts=1)
    http.write_cache(resp, "gus", s.id, "json")
    return resp


def _fetch_family(s, fam, offline=False):
    ext = FAMILY_EXT[fam]
    url = url_for(s)
    if offline:
        resp = http.read_cache(fam, s.id, ext)
        if resp is None:
            raise http.FetchError("offline and no cached response")
        groups, updated = _parse_family(s, fam, resp.body)
        if fam == "istat" and resp.updated:
            updated = resp.updated
        return _result(s, groups, updated or resp.updated, resp.url or url)
    if fam == "gus":
        resp = _fetch_gus(s)
        groups, updated = _parse_family(s, fam, resp.body)
        return _result(s, groups, updated, s.dataset, resp.secs)
    if fam == "istat":
        if "{EDITION}" not in s.dataset:
            raise ValueError("istat series need an {EDITION} placeholder in the key")
        since = _P.shift(_P.from_date(_today(), "M"), -8)
        disc = s.dataset.replace("{EDITION}", "") + "?" + urllib.parse.urlencode(
            [("lastNObservations", "1"), ("startPeriod", since), ("format", "csv")])
        _istat_wait()
        d = http.get(disc, source="istat", cache=False, timeout=ISTAT_TIMEOUT, tries=2)
        edition = national.istat_latest_edition(d.body)
        data_url = url.replace("{EDITION}", edition)
        _istat_wait()
        resp = http.get(data_url, source="istat", cache=False, timeout=ISTAT_TIMEOUT, tries=2)
        resp.updated = national.istat_edition_date(edition)
        http.write_cache(resp, "istat", s.id, ext)
        groups, _ = _parse_family(s, fam, resp.body)
        return _result(s, groups, resp.updated, data_url, resp.secs + d.secs, resp.attempts)
    resp = http.get(url, source=fam, cache_id=s.id, ext=ext)
    groups, updated = _parse_family(s, fam, resp.body)
    if fam == "cbs":
        try:
            info = http.get(s.dataset.rstrip("/") + "/TableInfos", source="cbs", cache=False)
            updated = national.cbs_modified(info.body)
        except http.FetchError:
            updated = None
    return _result(s, groups, updated or resp.updated, url, resp.secs, resp.attempts)
