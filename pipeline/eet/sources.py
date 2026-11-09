"""Turn a registry Series into a request URL, fetch it, parse it, and return observations.

One function per publisher family. ``fetch(series)`` returns a FetchResult whose ``obs`` maps a
series id (or ``<id>__<code>`` for panel children) to its observation list.
"""
import urllib.parse
from dataclasses import dataclass, field

from . import http
from .parsers import csvdata, jsonstat

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ECFIN = "https://webgate.ec.europa.eu/ecfin/redisstat/api/dissemination/statistics/1.0/data/"
ECB = "https://data-api.ecb.europa.eu/service/data/"
BIS = "https://stats.bis.org/api/v1/data/"
OECD = "https://sdmx.oecd.org/public/rest/data/"
INDEED = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/"


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
    return url_for(s)


def source_text(s):
    if s.source_name:
        return s.source_name
    pub = {"eurostat": "Eurostat", "ecfin": "European Commission", "ecb": "ECB", "bis": "BIS",
           "oecd": "OECD", "indeed": "Indeed Hiring Lab"}.get(s.source, "")
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
        if s.split is not None:
            group_by = csvdata.ecb_key_part(s.split) if isinstance(s.split, int) else s.split
            groups = csvdata.parse_multi(body, group_by, period_col, value_col, flag_col, where=where)
        else:
            groups = {None: csvdata.parse(body, period_col, value_col, flag_col, where=where)}
    out = {}
    for code, obs in groups.items():
        if code is None:
            out[s.id] = _scale(obs, s.scale)
        elif s.keep is None or s.keep(code):
            out[child_id(s.id, code)] = _scale(obs, s.scale)
    return out, updated


def fetch(s, offline=False):
    """Fetch and parse one registry Series. Raises on HTTP errors and on empty results."""
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
