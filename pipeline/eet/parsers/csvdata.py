"""CSV observations: ECB ``csvdata``, BIS ``format=csv``, OECD ``csvfile``, Eurostat SDMX-CSV and
plain CSV files (Indeed Hiring Lab). All share one shape: a period column and a value column.

``parse`` returns an observation list; ``parse_multi`` groups by a column (or a callable on the
row) for panels such as an ECB query with a wildcard in one key position.
"""
import csv
import io

from .. import periods as P

MISSING = {"", "NaN", "nan", "NA", "N/A", ":", "-"}


def read_rows(body):
    if isinstance(body, bytes):
        body = body.decode("utf-8-sig")
    elif body.startswith("﻿"):
        body = body[1:]
    return list(csv.DictReader(io.StringIO(body)))


def _rows_to_obs(rows, period_col, value_col, flag_col, normal=()):
    """``normal``: flag codes meaning "normal value" (BIS and OECD ``A``), stored as no flag."""
    out = {}
    for r in rows:
        raw = (r.get(value_col) or "").strip()
        if raw in MISSING:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        p = P.normalize(r[period_col])
        flag = (r.get(flag_col) or "").strip() if flag_col else ""
        out[p] = (p, v, "" if flag in normal else flag)
    return [out[p] for p in sorted(out)]


def parse_multi(body, group_by, period_col="TIME_PERIOD", value_col="OBS_VALUE", flag_col="OBS_STATUS",
                where=None, normal=()):
    """Return ``{group: obs}``. ``group_by`` is a column name or a callable(row) -> code."""
    rows = read_rows(body)
    if rows and period_col not in rows[0]:
        raise ValueError(f"column {period_col!r} not in CSV header {list(rows[0])[:12]}")
    if where:
        rows = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
    key = group_by if callable(group_by) else (lambda r: r.get(group_by))
    groups = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    return {g: _rows_to_obs(rs, period_col, value_col, flag_col, normal) for g, rs in groups.items()}


def parse(body, period_col="TIME_PERIOD", value_col="OBS_VALUE", flag_col="OBS_STATUS", where=None, normal=()):
    """Single-series parse. Raises if the rows hold more than one ``KEY`` (an ambiguous query)."""
    rows = read_rows(body)
    if rows and period_col not in rows[0]:
        raise ValueError(f"column {period_col!r} not in CSV header {list(rows[0])[:12]}")
    if where:
        rows = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
    if rows and "KEY" in rows[0]:
        keys = {r["KEY"] for r in rows}
        if len(keys) > 1:
            raise ValueError(f"query returned {len(keys)} series; expected one")
    return _rows_to_obs(rows, period_col, value_col, flag_col, normal)


def ecb_key_part(position):
    """Group-by function: the code at ``position`` (0-based, after the flow) of the ECB KEY column.

    ``HICP.M.U2.N.XEF000.4F0.ANR`` -> position 3 is ``XEF000``.
    """
    def f(row):
        return row["KEY"].split(".")[1 + position]
    return f
