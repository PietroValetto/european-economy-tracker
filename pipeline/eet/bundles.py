"""Write ``site/data/``: chart bundles, index.json, methods.json and snapshot.csv (CONTRACT 3 to 5).

Rounding for display happens here and only here: points, latest/previous values, table and
heatmap cells are rounded to the chart's (or series') ``decimals``.
"""
import csv
import io
import json
import os

from . import geo, pages
from . import periods as P
from . import sources
from .builders import last_point, series_entry
from .context import Missing, latest_stamp
from .spec import Derived

SCHEMA = 1


class ChartError(RuntimeError):
    pass


def rnd(v, d):
    if v is None:
        return None
    x = round(float(v), d)
    if x == 0:
        x = 0.0
    if d == 0:
        return int(x)
    return x


def _freq_label(spec, sample_period):
    if spec is not None and getattr(spec, "freq", None):
        return spec.freq
    f = P.freq_of(sample_period) if sample_period else None
    return f or "M"


def _primary(series):
    for s in series:
        if s.get("role") == "story":
            return s
    for s in series:
        if s.get("role") != "band":
            return s
    return series[0] if series else None


def _last_two(points, step=False):
    """Last point and the one before. For step series the 'previous' point is the last one with a
    different value (the rate before the latest change), not the step's own corner points."""
    vals = [pt for pt in points if pt[1] is not None]
    if not vals:
        return None, None
    if step:
        for pt in reversed(vals):
            if pt[1] != vals[-1][1]:
                return vals[-1], pt
        return vals[-1], None
    return vals[-1], (vals[-2] if len(vals) > 1 else None)


def latest_previous(series, decimals_for, flag_of):
    """Contract ``latest`` / ``previous`` from bundle series (values rounded).

    ``latest.period`` is the most recent period across series; ``values`` holds each series' last
    value. When series end on different periods, ``periods`` maps key -> its own last period.
    """
    usable = [s for s in series if s.get("role") != "band" and s.get("points")]
    if not usable:
        return None, None
    prim = _primary(usable)
    lasts = {s["key"]: _last_two(s["points"], s.get("curve") == "step-after") for s in usable}
    lp = [v[0] for v in lasts.values() if v[0]]
    if not lp:
        return None, None
    period = max((x[0] for x in lp), key=P.compare_key)
    values, pers, prev_vals = {}, {}, {}
    for s in usable:
        last, prev = lasts[s["key"]]
        if last:
            values[s["key"]] = rnd(last[1], decimals_for(s["key"]))
            pers[s["key"]] = last[0]
        if prev:
            prev_vals[s["key"]] = rnd(prev[1], decimals_for(s["key"]))
    latest = {"period": period, "values": values, "flag": flag_of(prim, lasts[prim["key"]][0][0])
              if lasts[prim["key"]][0] else None}
    if len(set(pers.values())) > 1:
        latest["periods"] = pers
    p_last, p_prev = lasts[prim["key"]]
    previous = {"period": p_prev[0], "values": prev_vals} if p_prev else None
    return latest, previous


def _decimals(ctx, chart, ref_or_none, sid):
    if ref_or_none is not None and ref_or_none.decimals is not None:
        return ref_or_none.decimals
    if chart.decimals is not None:
        return chart.decimals
    return ctx.decimals(sid) if sid else 1


def build_chart(ctx, chart):
    """Return ``(bundle, used_series_ids, dropped_refs)``. Raises ChartError if nothing to draw."""
    with ctx.track() as used:
        series, dropped, dec_by_key, freq_spec = [], [], {}, None
        for ref in chart.series:
            key = ref.key or ref.series
            try:
                obs = ctx.apply(ctx.obs(ref.series), ref.transform)
            except Missing as e:
                dropped.append((ref.series, str(e)))
                continue
            except (ValueError, ZeroDivisionError) as e:
                dropped.append((ref.series, f"transform failed: {e}"))
                continue
            start = ref.start or chart.start
            if start or ref.end:
                obs = [o for o in obs if (not start or o[0] >= start) and (not ref.end or o[0] <= ref.end)]
            while obs and obs[-1][1] is None:
                obs = obs[:-1]
            while obs and obs[0][1] is None:
                obs = obs[1:]
            if not obs:
                dropped.append((ref.series, "no observations in the chart window"))
                continue
            d = _decimals(ctx, chart, ref, ref.series)
            dec_by_key[key] = d
            curve = ref.curve or ("step-after" if isinstance(ref.transform, str) and "step" in ref.transform.split("|")
                                  else None)
            e = series_entry(key, ref.label or ctx.label(ref.series), ref.role, obs, mark=ref.mark, curve=curve)
            e["points"] = [[p, rnd(v, d)] for p, v in e["points"]]
            series.append(e)
            if freq_spec is None:
                freq_spec = ctx.spec(ref.series)
        extra = {}
        if chart.build is not None:
            try:
                extra = chart.build(ctx, chart) or {}
            except Missing as e:
                raise ChartError(f"build hook: {e}")
        built_series = extra.pop("series", [])
        default_dec = chart.decimals if chart.decimals is not None else 1
        for e in built_series:
            d = e.pop("decimals", None)
            d = default_dec if d is None else d
            dec_by_key[e["key"]] = d
            e["points"] = [[pt[0]] + [rnd(x, d) for x in pt[1:]] for pt in e["points"]]
        series += built_series
    if not series and chart.type not in ("table", "heatmap"):
        raise ChartError("no series could be built: " + "; ".join(f"{s} ({m})" for s, m in dropped))

    def flag_of(s, period):
        return (s.get("flags") or {}).get(period) or None

    latest, previous = latest_previous(series, lambda k: dec_by_key.get(k, default_dec), flag_of)
    ok_used = set(used) - {sid for sid, _ in dropped}
    fetched = []
    for sid in sorted(ok_used):
        sp = ctx.spec(sid)
        if sp is not None and not isinstance(sp, Derived):
            fetched.append((sid, sp))
    src_texts, seen = [], set()
    for _, sp in fetched:
        t = sources.source_text(sp)
        if t and t not in seen:
            seen.add(t)
            src_texts.append(t)
    prim_spec = None
    if chart.series:
        for r in chart.series:
            if r.role == "story":
                prim_spec = ctx.spec(r.series)
        prim_spec = prim_spec or ctx.spec(chart.series[0].series)
    if isinstance(prim_spec, Derived) or prim_spec is None:
        prim_spec = fetched[0][1] if fetched else None
    first_point = series[0]["points"][0][0] if series and series[0]["points"] else None
    bundle = {
        "id": chart.id,
        "page": chart.page,
        "section": chart.section,
        "order": chart.order,
        "title": chart.title,
        "kicker": chart.kicker,
        "subtitle": chart.subtitle,
        "type": chart.type,
        "units": chart.units,
        "frequency": chart.frequency or _freq_label(freq_spec, first_point),
        "geo": chart.geo,
        "series": series,
        "latest": latest,
        "previous": previous,
        "reference_lines": chart.reference_lines,
        "markers": chart.markers,
        "y_domain": chart.y_domain,
        "default_window": chart.default_window,
        "source": chart.source or "; ".join(src_texts),
        "source_url": chart.source_url or (sources.display_url(prim_spec) if prim_spec else ""),
        "notes": chart.notes,
        "methods_id": chart.id,
        "original": bool(chart.original),
        "data_updated": latest_stamp(ctx.updated(sid) for sid in ok_used),
        "built_at": ctx.built_at,
        "decimals": chart.decimals if chart.decimals is not None else (dec_by_key.get(_primary(series)["key"], 1)
                                                                        if series else 1),
        "format": chart.format,
    }
    if chart.total_key:
        bundle["total_key"] = chart.total_key
    if chart.highlight:
        bundle["highlight"] = chart.highlight
    if chart.x_label:
        bundle["x_label"] = chart.x_label
    if chart.y_label:
        bundle["y_label"] = chart.y_label
    bundle.update(chart.extra)
    # tables and heatmaps from the build hook
    if chart.type == "table":
        cols = extra.pop("columns", [])
        rows = extra.pop("rows", [])
        col_dec = {c["key"]: c.get("decimals") for c in cols}
        for r in rows:
            rd = r.get("decimals")
            for k, v in list(r["values"].items()):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    d = rd if rd is not None else (col_dec.get(k) if col_dec.get(k) is not None else default_dec)
                    r["values"][k] = rnd(v, d)
        bundle["columns"] = cols
        bundle["rows"] = rows
        if bundle["latest"] is None:
            periods = [r["values"].get("period") for r in rows if isinstance(r["values"].get("period"), str)]
            bundle["latest"] = {"period": max(periods, key=P.compare_key) if periods else None, "values": {},
                                "flag": None}
    if chart.type == "heatmap":
        cells = extra.pop("cells", [])
        bundle["rows"] = extra.pop("rows", [])
        bundle["columns"] = extra.pop("columns", [])
        bundle["cells"] = [[ri, ci, rnd(v, default_dec)] for ri, ci, v in cells]
        if bundle["latest"] is None:
            bundle["latest"] = {"period": bundle["columns"][-1] if bundle["columns"] else None, "values": {},
                                "flag": None}
    bundle.update(extra)
    return bundle, used, dropped


def write_json(path, obj, compact=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        if compact:
            json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def methods_entry(ctx, chart, used, bundle):
    srcs, seen = [], set()
    for sid in sorted(used):
        sp = ctx.spec(sid)
        if sp is None or isinstance(sp, Derived):
            continue
        k = (sp.source, sp.dataset)
        if k in seen:
            continue
        seen.add(k)
        srcs.append({"name": sources.source_text(sp), "dataset": sp.dataset if sp.source != "csv" else "",
                     "url": sources.display_url(sp)})
    transform = chart.transform_text
    if not transform:
        parts = []
        for r in chart.series:
            if r.transform and isinstance(r.transform, str):
                parts.append(f"{r.label or ctx.label(r.series)}: {r.transform}")
        transform = "; ".join(parts) or "As published."
    return {"id": chart.id, "title": chart.title, "what": chart.what or chart.subtitle, "transform": transform,
            "sources": srcs, "frequency": bundle.get("frequency"), "caveats": chart.caveats,
            "original": bool(chart.original), "updated": bundle.get("data_updated")}


def tile_entry(ctx, tile):
    obs = ctx.apply(ctx.obs(tile.series), tile.transform)
    vals = [o for o in obs if o[1] is not None]
    if not vals:
        raise Missing(f"{tile.series}: no data")
    d = tile.decimals if tile.decimals is not None else ctx.decimals(tile.series)
    p, v, f = vals[-1]
    prev = vals[-2][1] if len(vals) > 1 else None
    return {"id": tile.id, "label": tile.label, "value": rnd(v, d), "unit": tile.unit, "period": p,
            "previous": rnd(prev, d), "decimals": d, "good_direction": tile.good_direction, "chart_id": tile.chart_id,
            "page": tile.page, "flag": f or None}


def build_index(reg, built_at, existing_bundles, strip, failed):
    page_over = reg.pages
    out_pages = []
    for pid, title, desc in pages.PAGES:
        ov = page_over.get(pid)
        secs = sorted((s for s in reg.sections.values() if s.page == pid), key=lambda s: (s.order, s.id))
        sec_out = []
        for s in secs:
            charts = sorted((c for c in reg.charts.values() if c.page == pid and c.section == s.id
                             and c.id in existing_bundles), key=lambda c: (c.order, c.id))
            ch = [c.id for c in charts if existing_bundles[c.id] != "table"]
            tb = [c.id for c in charts if existing_bundles[c.id] == "table"]
            if ch or tb:
                sec_out.append({"id": s.id, "title": s.title, "intro": s.intro, "charts": ch, "tables": tb})
        out_pages.append({"id": pid, "title": (ov.title if ov and ov.title else title), "path": f"{pid}/",
                          "description": (ov.description if ov and ov.description else desc),
                          "sections": sec_out})
    return {"schema": SCHEMA, "built_at": built_at, "pages": out_pages, "strip": strip,
            "countries": list(geo.STRIP), "failed": failed}


SNAPSHOT_FIELDS = ["id", "label", "value", "unit", "period", "previous", "decimals", "good_direction", "flag", "chart_id",
                   "page", "series", "source", "data_updated", "built_at"]


def snapshot_csv(strip, extra_by_id, built_at):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SNAPSHOT_FIELDS, lineterminator="\n")
    w.writeheader()
    for t in strip:
        row = {k: t.get(k) for k in SNAPSHOT_FIELDS if k in t}
        row.update(extra_by_id.get(t["id"], {}))
        row["built_at"] = built_at
        row = {k: ("" if row.get(k) is None else row.get(k)) for k in SNAPSHOT_FIELDS}
        w.writerow(row)
    return buf.getvalue()
