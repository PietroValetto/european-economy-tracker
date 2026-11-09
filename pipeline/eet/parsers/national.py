"""Parsers for national publishers (research/04_national_sources.md) and the Indeed wage tracker.

Each returns observation lists ``[(period, value, flag), ...]`` sorted by period, like the other
parsers. Publisher update stamps are returned as ISO strings (``%Y-%m-%dT%H:%M:%S%z``) or None.

* :func:`bundesbank` - Bundesbank SDMX web service, ``format=csv`` (one series per request):
  a header row with the series key, metadata rows (``unit``, ``last update``, ...), then
  ``period,value,flag-text`` rows. Used for the BBDL1 labour-market mirror of Destatis and BA.
* :func:`insee` - INSEE BDM SDMX-ML 2.1 StructureSpecificData (``SERIES_BDM/<idbank>``).
* :func:`cbs` - CBS StatLine OData v3 ``TypedDataSet`` (JSON); periods ``2026MM09``. Quarterly
  (``KW``) and annual (``JJ``) rows in the same table are skipped.
* :func:`cbs_modified` - the ``Modified`` stamp from a CBS ``TableInfos`` response.
* :func:`gus_value` - one month of the GUS DBW API (``variable-data-section``): the value for one
  position of the section and one presentation measure.
* :func:`istat_latest_edition` - the newest ``EDITION`` code (``2026M10G29`` = release of
  29 October 2026) in an ISTAT SDMX-CSV response. ISTAT data are then parsed with
  :func:`eet.parsers.csvdata.parse_multi`.
* :func:`indeed_wages` - the Indeed Hiring Lab wage tracker CSV, whose ``month`` column reads
  ``Jan-19``; returns ``{jobcountry: obs}``.
"""
import csv
import datetime
import io
import json
import re
import xml.etree.ElementTree as ET

from .. import periods as P
from . import csvdata

_DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$|^\d{4}-Q[1-4]$|^\d{4}$")


class NationalParseError(ValueError):
    pass


def _berlin_stamp(text):
    """'2026-10-30 10:11:21' (German local time) -> '2026-10-30T10:11:21+0100'."""
    try:
        d = datetime.datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    try:
        from zoneinfo import ZoneInfo
        d = d.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    except Exception:  # noqa: BLE001 - no tz database: assume CET
        d = d.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
    return d.strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------ Bundesbank

BBK_FLAGS = {"Provisional value": "p", "Estimated value": "e", "Break in series": "b"}


def bundesbank(body):
    """Return ``(obs, updated)`` from a single-series Bundesbank CSV response."""
    if isinstance(body, bytes):
        body = body.decode("utf-8-sig")
    elif body.startswith("﻿"):
        body = body[1:]
    rows = list(csv.reader(io.StringIO(body)))
    if not rows or len(rows[0]) < 2 or not rows[0][1]:
        raise NationalParseError("not a Bundesbank CSV (no series key in the header)")
    out, updated = {}, None
    for r in rows[1:]:
        if not r:
            continue
        head = r[0].strip()
        if head == "last update" and len(r) > 1:
            updated = _berlin_stamp(r[1])
            continue
        if not _DATE.match(head):
            continue
        raw = r[1].strip() if len(r) > 1 else ""
        if raw in csvdata.MISSING or raw == ".":
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        flag_text = r[2].strip() if len(r) > 2 else ""
        p = P.normalize(head)
        out[p] = (p, v, BBK_FLAGS.get(flag_text, "e" if "estimat" in flag_text.lower() else
                                    ("p" if "provisional" in flag_text.lower() else "")))
    return [out[p] for p in sorted(out)], updated


# ------------------------------------------------------------------ INSEE

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def insee(body):
    """Return ``(obs, updated)`` from an INSEE BDM SDMX-ML response holding one series.

    ``OBS_STATUS`` ``P`` (provisional) becomes flag ``p``; definitive and semi-definitive values
    carry no flag. ``LAST_UPDATE`` (a date) is the update stamp.
    """
    root = ET.fromstring(body)
    series = [el for el in root.iter() if _local(el.tag) == "Series"]
    if not series:
        raise NationalParseError("INSEE response has no Series")
    if len(series) > 1:
        raise NationalParseError(f"INSEE response has {len(series)} series; expected one")
    s = series[0]
    updated = None
    if s.get("LAST_UPDATE"):
        updated = f"{s.get('LAST_UPDATE')}T12:00:00+0100"
    out = {}
    for ob in s:
        if _local(ob.tag) != "Obs":
            continue
        raw = (ob.get("OBS_VALUE") or "").strip()
        if raw in csvdata.MISSING:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        p = P.normalize(ob.get("TIME_PERIOD", ""))
        out[p] = (p, v, "p" if (ob.get("OBS_STATUS") or "") == "P" else "")
    return [out[p] for p in sorted(out)], updated


# ------------------------------------------------------------------ CBS

_CBS_MONTH = re.compile(r"^(\d{4})MM(\d{2})$")


def cbs(body, value_col, period_col="Perioden"):
    """Monthly observations from a CBS OData ``TypedDataSet`` response (other frequencies skipped)."""
    d = json.loads(body)
    rows = d.get("value")
    if rows is None:
        raise NationalParseError("not a CBS OData response (no 'value')")
    if rows and value_col not in rows[0]:
        raise NationalParseError(f"column {value_col!r} not in CBS response {sorted(rows[0])[:10]}")
    out = {}
    for r in rows:
        m = _CBS_MONTH.match(str(r.get(period_col, "")).strip())
        v = r.get(value_col)
        if not m or v is None:
            continue
        p = f"{m.group(1)}-{m.group(2)}"
        out[p] = (p, float(v), "")
    return [out[p] for p in sorted(out)]


def cbs_modified(body):
    """``Modified`` of a CBS ``TableInfos`` response as an ISO stamp (Dutch local time)."""
    try:
        info = json.loads(body)["value"][0]
        d = datetime.datetime.strptime(info["Modified"], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    try:
        from zoneinfo import ZoneInfo
        d = d.replace(tzinfo=ZoneInfo("Europe/Amsterdam"))
    except Exception:  # noqa: BLE001
        d = d.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
    return d.strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------ GUS

GUS_FIRST_MONTH = 247  # id-okres 247 = January ... 258 = December (periods dictionary)


def gus_period_id(month):
    return GUS_FIRST_MONTH + month - 1


def gus_value(body, position, measure):
    """The value for section position ``position`` and measure ``measure`` in one month's response.

    Returns None if the row is absent (the month is not published for that position).
    """
    d = json.loads(body) if isinstance(body, (bytes, str)) else body
    rows = d.get("data")
    if rows is None:
        raise NationalParseError("not a GUS DBW response (no 'data')")
    for r in rows:
        if str(r.get("id-pozycja-2")) == str(position) and str(r.get("id-sposob-prezentacji-miara")) == str(measure):
            v = r.get("wartosc")
            return None if v is None else float(v)
    return None


# ------------------------------------------------------------------ ISTAT

_EDITION = re.compile(r"^(\d{4})M(\d{1,2})G(\d{1,2})$")


def istat_edition_key(code):
    m = _EDITION.match(code or "")
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def istat_latest_edition(body):
    """The newest EDITION code in an ISTAT SDMX-CSV response (calendar order, not string order)."""
    rows = csvdata.read_rows(body)
    eds = {r.get("EDITION", "") for r in rows if r.get("OBS_VALUE", "").strip() not in csvdata.MISSING}
    eds = [e for e in eds if istat_edition_key(e)]
    if not eds:
        raise NationalParseError("no EDITION codes in the ISTAT response")
    return max(eds, key=istat_edition_key)


def istat_edition_date(code):
    y, m, d = istat_edition_key(code)
    return f"{y:04d}-{m:02d}-{d:02d}T10:00:00+0100"


# ------------------------------------------------------------------ Indeed wage tracker

_MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                    "Nov", "Dec"], start=1)}


def month_label(text):
    """'Jan-19' -> '2019-01'. Already-normalised periods pass through."""
    t = text.strip()
    m = re.match(r"^([A-Z][a-z]{2})-(\d{2})$", t)
    if m and m.group(1) in _MON:
        return f"20{m.group(2)}-{_MON[m.group(1)]:02d}"
    return P.normalize(t)


def indeed_wages(body, value_col="posted_wage_growth_yoy_3moavg", period_col="month", group_col="jobcountry"):
    """``{jobcountry: obs}`` from ``posted-wage-growth-by-country.csv`` (values as published, a fraction)."""
    rows = csvdata.read_rows(body)
    if rows and (period_col not in rows[0] or value_col not in rows[0]):
        raise NationalParseError(f"Indeed wage tracker columns changed: {list(rows[0])}")
    for r in rows:
        r[period_col] = month_label(r[period_col])
    groups = {}
    for r in rows:
        groups.setdefault(r.get(group_col), []).append(r)
    return {g: csvdata._rows_to_obs(rs, period_col, value_col, "") for g, rs in groups.items()}
