"""Validate every generated file in ``site/data/`` against CONTRACT.md.

    python3 -m eet.check [--data DIR] [--quiet]

Errors make the exit status 1. Warnings (for example a home tile linking to a chart another
section has not built yet) are printed but do not fail the check.
"""
import argparse
import csv
import json
import os
import re
import sys

from . import pages, paths
from . import periods as P
from .spec import CHART_TYPES, COLUMN_FORMATS, CURVES, DIRECTIONS, FORMATS, MARKS, ROLES, WINDOWS

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FREQ_OK = {"A", "Q", "M", "W", "D"}

REQUIRED = {"id": str, "page": str, "section": str, "order": (int, float), "title": str, "kicker": str,
            "subtitle": str, "type": str, "units": str, "frequency": str, "geo": str, "series": list,
            "reference_lines": list, "markers": list, "default_window": str, "source": str,
            "source_url": str, "notes": str, "methods_id": str, "original": bool, "built_at": str}


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check_bundle(b, fname, rep):
    w = fname
    if not isinstance(b, dict):
        rep.err(w, "bundle is not an object")
        return
    for k, t in REQUIRED.items():
        if k not in b:
            rep.err(w, f"missing field {k!r}")
        elif not isinstance(b[k], t):
            rep.err(w, f"field {k!r} has type {type(b[k]).__name__}")
    for k in ("latest", "previous", "y_domain", "data_updated"):
        if k not in b:
            rep.err(w, f"missing field {k!r}")
    if rep.errors and rep.errors[-1].startswith(w + ": missing field 'series'"):
        return
    if b.get("id") and b["id"] + ".json" != os.path.basename(fname):
        rep.err(w, f"id {b['id']!r} does not match file name")
    if b.get("id") and not KEBAB.match(b["id"]):
        rep.err(w, "id is not kebab-case")
    if b.get("page") not in pages.PAGE_IDS:
        rep.err(w, f"unknown page {b.get('page')!r}")
    typ = b.get("type")
    if typ not in CHART_TYPES:
        rep.err(w, f"unknown type {typ!r}")
    if b.get("frequency") not in FREQ_OK:
        rep.err(w, f"frequency {b.get('frequency')!r} not one of {sorted(FREQ_OK)}")
    if b.get("default_window") not in WINDOWS:
        rep.err(w, f"default_window {b.get('default_window')!r} not one of {WINDOWS}")
    if "format" in b and b["format"] not in FORMATS:
        rep.err(w, f"format {b['format']!r} not one of {FORMATS}")
    if "decimals" in b and not isinstance(b["decimals"], int):
        rep.err(w, "decimals must be an integer")
    if not ISO_Z.match(str(b.get("built_at", ""))):
        rep.err(w, "built_at must be an ISO timestamp in UTC ending in Z")
    if b.get("data_updated") is not None and not isinstance(b["data_updated"], str):
        rep.err(w, "data_updated must be a string or null")
    if b.get("y_domain") is not None and not (isinstance(b["y_domain"], list) and len(b["y_domain"]) == 2):
        rep.err(w, "y_domain must be null or [min, max]")
    series = b.get("series") or []
    keys, stories = set(), 0
    for i, s in enumerate(series):
        sw = f"{w} series[{i}]"
        if not isinstance(s, dict):
            rep.err(sw, "not an object")
            continue
        for k in ("key", "label", "role", "points"):
            if k not in s:
                rep.err(sw, f"missing {k!r}")
        if s.get("key") in keys:
            rep.err(sw, f"duplicate key {s.get('key')!r}")
        keys.add(s.get("key"))
        if "mark" in s and s["mark"] not in MARKS:
            rep.err(sw, f"mark {s['mark']!r} not one of {MARKS}")
        if "curve" in s and s["curve"] not in CURVES:
            rep.err(sw, f"curve {s['curve']!r} not one of {CURVES}")
        role = s.get("role")
        if role not in ROLES:
            rep.err(sw, f"unknown role {role!r}")
        if role == "story":
            stories += 1
        pts = s.get("points") or []
        if not pts:
            rep.err(sw, "no points")
        width = 3 if (role == "band" or typ == "scatter") else 2
        categorical = typ == "bar" and pts and isinstance(pts[0], list) and pts[0] \
            and isinstance(pts[0][0], str) and P.freq_of(pts[0][0]) is None
        freqs = set()
        prev = None
        for pt in pts:
            if not isinstance(pt, list) or len(pt) != width:
                rep.err(sw, f"point {pt!r} should be a list of {width}")
                break
            p = pt[0]
            if not isinstance(p, str):
                rep.err(sw, f"period {p!r} is not a string")
                break
            for v in pt[1:]:
                if v is not None and not _num(v):
                    rep.err(sw, f"value {v!r} at {p} is not a number or null")
            if categorical:
                continue
            freqs.add(P.freq_of(p))
            if prev is not None and p <= prev:
                rep.err(sw, f"periods not strictly increasing at {p}")
                break
            prev = p
        if None in freqs:
            rep.err(sw, "unrecognised period format")
        if len(freqs) > 1:
            rep.err(sw, f"mixed period formats {sorted(f for f in freqs if f)}")
        fl = s.get("flags")
        if fl is not None and not isinstance(fl, dict):
            rep.err(sw, "flags must be an object {period: flag}")
    if stories > 1:
        rep.err(w, f"{stories} story series (at most one)")
    if "highlight" in b and b["highlight"] is not None and not isinstance(b["highlight"], str):
        rep.err(w, "highlight must be a string")
    if typ in ("stacked-bar", "contrib"):
        tk = b.get("total_key")
        if not tk:
            rep.err(w, "stacked-bar/contrib needs total_key")
        elif tk not in keys:
            rep.err(w, f"total_key {tk!r} is not a series key")
    if typ == "scatter":
        for k in ("x_label", "y_label"):
            if not isinstance(b.get(k), str):
                rep.err(w, f"scatter needs {k}")
    if typ == "heatmap":
        rows, cols, cells = b.get("rows"), b.get("columns"), b.get("cells")
        if not isinstance(rows, list) or not isinstance(cols, list) or not isinstance(cells, list):
            rep.err(w, "heatmap needs rows, columns and cells lists")
        else:
            for c in cells:
                if not (isinstance(c, list) and len(c) == 3 and isinstance(c[0], int) and isinstance(c[1], int)
                        and 0 <= c[0] < len(rows) and 0 <= c[1] < len(cols) and (c[2] is None or _num(c[2]))):
                    rep.err(w, f"bad heatmap cell {c!r}")
                    break
        if b.get("scale") not in ("diverging", "sequential"):
            rep.err(w, "heatmap scale must be diverging or sequential")
        if not cells:
            rep.err(w, "heatmap has no cells")
    if typ == "table":
        cols, rows = b.get("columns"), b.get("rows")
        if not isinstance(cols, list) or not cols:
            rep.err(w, "table needs columns")
        else:
            for c in cols:
                if not (isinstance(c, dict) and {"key", "label", "format"} <= set(c)):
                    rep.err(w, f"table column {c!r} needs key, label, format")
                elif c["format"] not in COLUMN_FORMATS:
                    rep.err(w, f"table column {c['key']!r} format {c['format']!r} not one of {COLUMN_FORMATS}")
        if not isinstance(rows, list) or not rows:
            rep.err(w, "table needs rows")
        else:
            ckeys = {c.get("key") for c in cols or [] if isinstance(c, dict)}
            for r in rows:
                if not (isinstance(r, dict) and "label" in r and isinstance(r.get("values"), dict) and "flag" in r):
                    rep.err(w, f"table row {r!r} needs label, values, flag")
                    break
                if "decimals" in r and not isinstance(r["decimals"], int):
                    rep.err(w, f"table row {r['label']!r} decimals must be an integer")
                for k, v in r["values"].items():
                    if v is not None and not _num(v):
                        rep.err(w, f"table row {r['label']!r} value {k}={v!r} is not a number or null")
                extra = set(r["values"]) - ckeys
                if extra:
                    rep.err(w, f"table row {r['label']!r} has values for unknown columns {sorted(extra)}")
    if typ == "country-strip" and not series:
        rep.err(w, "country-strip needs one series per country")
    if typ not in ("table", "heatmap") and not series:
        rep.err(w, "no series")
    lat = b.get("latest")
    if typ not in ("table", "heatmap"):
        if not isinstance(lat, dict) or "period" not in lat or not isinstance(lat.get("values"), dict):
            rep.err(w, "latest must be {period, values, flag}")
        else:
            for k in lat["values"]:
                if k not in keys:
                    rep.err(w, f"latest.values has unknown key {k!r}")
    elif lat is not None and not isinstance(lat, dict):
        rep.err(w, "latest must be an object or null")
    prv = b.get("previous")
    if prv is not None and not (isinstance(prv, dict) and "period" in prv and isinstance(prv.get("values"), dict)):
        rep.err(w, "previous must be null or {period, values}")
    for rl in b.get("reference_lines") or []:
        if not (isinstance(rl, dict) and rl.get("axis") in ("x", "y") and "value" in rl):
            rep.err(w, f"bad reference line {rl!r}")
    for m in b.get("markers") or []:
        if not (isinstance(m, dict) and "x" in m and "label" in m):
            rep.err(w, f"bad marker {m!r}")


def check_index(idx, bundles, rep):
    w = "index.json"
    if idx.get("schema") != 1:
        rep.err(w, "schema must be 1")
    if not ISO_Z.match(str(idx.get("built_at", ""))):
        rep.err(w, "built_at must end in Z")
    ids = [p.get("id") for p in idx.get("pages", [])]
    if ids != pages.PAGE_IDS:
        rep.err(w, f"pages must be exactly {pages.PAGE_IDS} in order, got {ids}")
    seen = set()
    for p in idx.get("pages", []):
        for k in ("id", "title", "path", "description", "sections"):
            if k not in p:
                rep.err(w, f"page {p.get('id')} missing {k}")
        if str(p.get("path", "")).startswith("/"):
            rep.err(w, f"page {p.get('id')} path must be relative")
        for s in p.get("sections", []):
            for k in ("id", "title", "intro", "charts", "tables"):
                if k not in s:
                    rep.err(w, f"section {p.get('id')}/{s.get('id')} missing {k}")
            for cid in list(s.get("charts", [])) + list(s.get("tables", [])):
                if cid in seen:
                    rep.err(w, f"chart {cid} listed twice")
                seen.add(cid)
                if cid not in bundles:
                    rep.err(w, f"section {p['id']}/{s.get('id')} references missing bundle {cid}")
                elif bundles[cid].get("page") != p["id"]:
                    rep.err(w, f"chart {cid} listed under {p['id']} but its bundle says {bundles[cid].get('page')}")
                elif (bundles[cid].get("type") == "table") != (cid in s.get("tables", [])):
                    rep.err(w, f"chart {cid}: tables go in 'tables', charts in 'charts'")
    strip = idx.get("strip")
    if not isinstance(strip, list):
        rep.err(w, "strip must be a list")
        strip = []
    if len(strip) != 12:
        rep.warn(w, f"strip has {len(strip)} tiles (expected 12)")
    tids = set()
    for t in strip:
        tw = f"{w} strip[{t.get('id')}]"
        for k in ("id", "label", "value", "unit", "period", "previous", "good_direction", "chart_id", "page", "flag"):
            if k not in t:
                rep.err(tw, f"missing {k}")
        if t.get("id") in tids:
            rep.err(tw, "duplicate tile id")
        tids.add(t.get("id"))
        if t.get("good_direction") not in DIRECTIONS:
            rep.err(tw, "good_direction must be up, down or none")
        if "decimals" in t and not isinstance(t["decimals"], int):
            rep.err(tw, "decimals must be an integer")
        if t.get("value") is not None and not _num(t.get("value")):
            rep.err(tw, "value must be a number")
        if t.get("page") not in pages.PAGE_IDS:
            rep.err(tw, f"unknown page {t.get('page')!r}")
        if t.get("chart_id") not in bundles:
            rep.warn(tw, f"links to chart {t.get('chart_id')!r} which is not built yet")
        elif bundles[t["chart_id"]].get("page") != t.get("page"):
            rep.err(tw, f"chart {t['chart_id']} is on page {bundles[t['chart_id']].get('page')}, not {t.get('page')}")
    if not isinstance(idx.get("countries"), list):
        rep.err(w, "countries must be a list")
    failed = idx.get("failed")
    if not isinstance(failed, list) or any(not (isinstance(f, dict) and "id" in f and "error" in f) for f in failed):
        rep.err(w, "failed must be a list of {id, error, chart_ids}")
    else:
        for f in failed:
            if "chart_ids" in f and not (isinstance(f["chart_ids"], list)
                                         and all(isinstance(x, str) for x in f["chart_ids"])):
                rep.err(w, f"failed {f['id']}: chart_ids must be a list of chart ids")
    unlisted = set(bundles) - seen
    for cid in sorted(unlisted):
        rep.warn(w, f"bundle {cid} is not listed in any section")


def check_methods(m, bundles, rep):
    w = "methods.json"
    entries = m.get("entries")
    if not isinstance(entries, list):
        rep.err(w, "entries must be a list")
        return
    ids = set()
    for e in entries:
        for k in ("id", "title", "what", "transform", "sources", "frequency", "caveats", "original", "updated"):
            if k not in e:
                rep.err(w, f"entry {e.get('id')} missing {k}")
        if e.get("id") in ids:
            rep.err(w, f"duplicate entry {e.get('id')}")
        ids.add(e.get("id"))
        for s in e.get("sources") or []:
            if not (isinstance(s, dict) and {"name", "dataset", "url"} <= set(s)):
                rep.err(w, f"entry {e.get('id')}: source needs name, dataset, url")
    for cid, b in bundles.items():
        if b.get("methods_id") not in ids:
            rep.err(w, f"bundle {cid} methods_id {b.get('methods_id')!r} has no entry")


def check_snapshot(path, idx, rep):
    w = "snapshot.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows and idx.get("strip"):
        rep.err(w, "empty but strip has tiles")
    want = {t.get("id") for t in idx.get("strip", [])}
    got = {r.get("id") for r in rows}
    if want != got:
        rep.err(w, f"ids differ from strip: missing {sorted(want - got)}, extra {sorted(got - want)}")


def run(data_dir=None):
    data_dir = data_dir or paths.SITE_DATA
    rep = Report()
    charts_dir = os.path.join(data_dir, "charts")
    bundles = {}
    if os.path.isdir(charts_dir):
        for f in sorted(os.listdir(charts_dir)):
            if not f.endswith(".json"):
                continue
            path = os.path.join(charts_dir, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    b = json.load(fh)
            except ValueError as e:
                rep.err(f, f"invalid JSON: {e}")
                continue
            check_bundle(b, f, rep)
            if isinstance(b, dict) and b.get("id"):
                if b["id"] in bundles:
                    rep.err(f, f"duplicate chart id {b['id']}")
                bundles[b["id"]] = b
    idx_path = os.path.join(data_dir, "index.json")
    idx = {}
    if not os.path.exists(idx_path):
        rep.err("index.json", "missing")
    else:
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        check_index(idx, bundles, rep)
    mpath = os.path.join(data_dir, "methods.json")
    if not os.path.exists(mpath):
        rep.err("methods.json", "missing")
    else:
        with open(mpath, encoding="utf-8") as fh:
            check_methods(json.load(fh), bundles, rep)
    spath = os.path.join(data_dir, "snapshot.csv")
    if not os.path.exists(spath):
        rep.err("snapshot.csv", "missing")
    else:
        check_snapshot(spath, idx, rep)
    return rep, len(bundles)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=None, help="data directory (default site/data)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    rep, n = run(a.data)
    if not a.quiet:
        for x in rep.warnings:
            print("warning:", x)
    for x in rep.errors:
        print("ERROR:", x)
    print(f"check: {n} bundles, {len(rep.errors)} errors, {len(rep.warnings)} warnings")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
