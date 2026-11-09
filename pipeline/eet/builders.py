"""Reusable ``build`` hooks for tables, heatmaps and other bundles that are not plain line charts.

Use them from a section module::

    from eet import builders
    Chart(id="hicp-bank", type="table", ..., build=builders.transform_table(
        columns=[("m1", "1m ann.", "pct"), ("m12", "12m", "pct")],
        rows=[("Headline", {"m12": ("hicp_headline", None)})]))

Each factory returns a function ``build(ctx, chart) -> dict`` of bundle fields. Values are raw;
the bundle writer rounds them (column ``decimals`` or the chart's ``decimals``).
"""
from . import geo
from . import periods as P
from .context import Missing


def last_point(obs):
    """(period, value, flag) of the last non-null observation, or None."""
    for p, v, f in reversed(obs):
        if v is not None:
            return p, v, f
    return None


def value_at(obs, period):
    for p, v, _ in obs:
        if p == period:
            return v
    return None


def series_entry(key, label, role, obs, flags=True, mark=None, curve=None):
    """A bundle ``series[]`` item from an observation list."""
    e = {"key": key, "label": label, "role": role, "points": [[p, v] for p, v, _ in obs]}
    if mark:
        e["mark"] = mark
    if curve:
        e["curve"] = curve
    fl = {p: f for p, v, f in obs if f}
    if flags and fl:
        e["flags"] = fl
    return e


def _columns(cols):
    out = []
    for c in cols:
        if isinstance(c, dict):
            out.append(c)
        else:
            key, label, fmt, *rest = c
            d = {"key": key, "label": label, "format": fmt}
            if rest:
                d["decimals"] = rest[0]
            out.append(d)
    return out


def period_label(p):
    """Short human label for a period: 'Sep 2026', 'Q3 2026', '6 Nov 2026', '2026'."""
    f = P.freq_of(p)
    if f == "M":
        return P.start_date(p).strftime("%b %Y")
    if f == "Q":
        return f"Q{p[-1]} {p[:4]}"
    if f == "D":
        d = P.start_date(p)
        return f"{d.day} {d.strftime('%b %Y')}"
    return p


def _finish_rows(out_rows, reference="max"):
    """Tables have no text columns (CONTRACT column formats are numeric), so a row whose latest
    period differs from the table's latest period gets it appended to its label ("Supercore (Sep 2026)").
    Every row also carries its own ``period``."""
    periods = [r["period"] for r in out_rows if r.get("period")]
    if not periods:
        latest = None
    elif reference == "mode":  # the date most rows share (markets: one row may already have today)
        latest = max(set(periods), key=lambda p: (periods.count(p), P.compare_key(p)))
    else:
        latest = max(periods, key=P.compare_key)
    for r in out_rows:
        if r.get("period") and r["period"] != latest:
            r["label"] = f"{r['label']} ({period_label(r['period'])})"
    return latest


def transform_table(columns, rows, period_from=None):
    """Table whose cells are the latest value of (series, transform).

    columns: [(key, label, format[, decimals]), ...]; format from pct, pp, index, level, eur_bn, change
    rows:    [(label, {column_key: (series_id, transform), ...}), ...]
    The row period is the latest period of the ``period_from`` cell (default: the first cell that has
    data). A row whose series are all missing is dropped; a missing cell is ``null``.
    """
    def build(ctx, chart):
        out_rows = []
        for label, cells in rows:
            values, period, flag, any_ok = {}, None, None, False
            for key, (sid, tr) in cells.items():
                try:
                    obs = ctx.apply(ctx.obs(sid), tr)
                except Missing:
                    values[key] = None
                    continue
                lp = last_point(obs) if obs else None
                values[key] = lp[1] if lp else None
                if lp:
                    any_ok = True
                    if period is None or (period_from == key):
                        period, flag = lp[0], (lp[2] or None)
            if not any_ok:
                continue
            for c in columns:
                k = c["key"] if isinstance(c, dict) else c[0]
                values.setdefault(k, None)
            out_rows.append({"label": label, "values": values, "flag": flag, "period": period})
        if not out_rows:
            raise Missing("table has no rows")
        latest = _finish_rows(out_rows)
        return {"columns": _columns(columns), "rows": out_rows,
                "latest": {"period": latest, "values": {}, "flag": None}}
    return build


def markets_table(rows, lags=(("w1", "1 week ago", 7), ("m1", "1 month ago", 30))):
    """Latest value of daily (or other) series against their values n days ago, and the changes.

    rows: [(label, series_id, decimals, kind)] where kind is "level" (change in the series' units,
    e.g. percentage points for yields) or "pct" (percentage change, for exchange rates). Change
    columns use format ``change`` (shown signed); each row says its unit in ``change_unit``.
    """
    import datetime

    def build(ctx, chart):
        cols = [{"key": "latest", "label": "Latest", "format": "level"}]
        for k, lab, _ in lags:
            cols.append({"key": k, "label": lab.capitalize(), "format": "level"})
        for k, lab, _ in lags:
            cols.append({"key": f"chg_{k}", "label": f"{lab.replace(' ago', '').replace(' ', '-')} change", "format": "change"})
        out = []
        for label, sid, dec, kind in rows:
            try:
                obs = ctx.obs(sid)
            except Missing:
                continue
            lp = last_point(obs)
            if not lp:
                continue
            p, v, f = lp
            vals = {"latest": v}
            freq = P.freq_of(p)
            for k, _, days in lags:
                if freq == "D":
                    ref = (datetime.date.fromisoformat(p) - datetime.timedelta(days=days)).isoformat()
                else:
                    ref = P.shift(p, -1)
                b = None
                for q, w, _ in obs:
                    if q <= ref and w is not None:
                        b = w
                    elif q > ref:
                        break
                vals[k] = b
                if b is None:
                    vals[f"chg_{k}"] = None
                elif kind == "pct":  # pre-rounded: the row's decimals are for the level
                    vals[f"chg_{k}"] = round((v / b - 1) * 100, 2) if b else None
                else:
                    vals[f"chg_{k}"] = v - b
            out.append({"label": label, "values": vals, "flag": f or None, "decimals": dec, "period": p,
                        "change_unit": "%" if kind == "pct" else "pp"})
        if not out:
            raise Missing("markets table has no rows")
        latest = _finish_rows(out, reference="mode")
        return {"columns": cols, "rows": out, "latest": {"period": latest, "values": {}, "flag": None}}
    return build


def heatmap(series_ids, last_n=24, scale="diverging", midpoint=None, sort="latest_desc", pin_first=None,
            transform=None, labels=None):
    """Heatmap: one row per series (country), one column per period, cells = values.

    series_ids may contain a panel wildcard ``"<panel>__*"`` (all children). Columns are the last
    ``last_n`` periods of the pinned row (or the union). ``sort``: latest_desc | name | given.
    """
    def build(ctx, chart):
        items = []
        for sid in series_ids:
            if sid.endswith("__*"):
                for code, obs in ctx.panel(sid[:-3]).items():
                    items.append((f"{sid[:-3]}__{code}", code, obs))
            else:
                try:
                    items.append((sid, sid.split("__")[-1], ctx.obs(sid)))
                except Missing:
                    continue
        items = [(sid, code, ctx.apply(obs, transform) if transform else obs) for sid, code, obs in items]
        items = [x for x in items if x[2]]
        if not items:
            raise Missing("heatmap has no data")
        pinned = [x for x in items if pin_first and x[1] == pin_first]
        anchor = pinned[0][2] if pinned else max(items, key=lambda x: x[2][-1][0])[2]
        cols = [p for p, v, _ in anchor if v is not None][-last_n:]
        rest = [x for x in items if x not in pinned]
        if sort == "latest_desc":
            def lv(x):
                d = {p: v for p, v, _ in x[2]}
                for c in reversed(cols):
                    if d.get(c) is not None:
                        return d[c]
                return float("-inf")
            rest.sort(key=lv, reverse=True)
        elif sort == "name":
            rest.sort(key=lambda x: geo.name(x[1]))
        ordered = pinned + rest
        rows, cells = [], []
        for ri, (sid, code, obs) in enumerate(ordered):
            rows.append((labels or {}).get(code) or ctx.label(sid))
            d = {p: v for p, v, _ in obs}
            for ci, c in enumerate(cols):
                if d.get(c) is not None:
                    cells.append([ri, ci, d[c]])
        out = {"rows": rows, "columns": cols, "cells": cells, "scale": scale,
               "row_keys": [x[1] for x in ordered]}
        if midpoint is not None:
            out["midpoint"] = midpoint
        return out
    return build
