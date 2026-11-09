"""Tidy vintage store: one CSV per series in ``store/<series_id>.csv``.

Columns: ``period,value,flag,first_seen,last_seen``.

* A row is appended only when a period is new or its value or flag changed, so revisions stay
  visible (flash vs final HICP, GDP revisions) and files stay small and diff cleanly in git.
* ``first_seen`` is the date (UTC, ``YYYY-MM-DD``) the pipeline first saw that vintage.
* ``last_seen`` is empty while the vintage is current. When a later fetch brings a different
  value or flag, the old row gets ``last_seen`` = the date of the last fetch that still showed it.
* Periods missing from a later fetch are kept as they are (a shorter request window is not a
  deletion).

``store/_meta.json`` records, per series id, the last fetch date, the publisher update stamp, the
request URL and a hash of the series definition. If the definition changes (different dataset,
filters, key, scale), that series' file is started afresh.
"""
import csv
import datetime
import hashlib
import json
import os

from . import paths

FIELDS = ["period", "value", "flag", "first_seen", "last_seen"]
META = "_meta.json"


def _dir(root=None):
    return root or paths.STORE


def fmt_value(v):
    """Canonical text for a value: 10 significant digits, no trailing noise."""
    if v is None:
        return ""
    x = float(f"{float(v):.10g}")
    if x.is_integer() and abs(x) < 1e15:
        return str(int(x))
    return repr(x)


def spec_hash(s):
    keep = getattr(s, "keep", None)
    payload = json.dumps({"source": s.source, "dataset": s.dataset, "key": s.key, "filters": s.filters,
                          "split": s.split, "scale": s.scale, "keep": getattr(keep, "__name__", None)},
                         sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def path_for(sid, root=None):
    return os.path.join(_dir(root), f"{sid}.csv")


def read_rows(sid, root=None):
    p = path_for(sid, root)
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_rows(sid, rows, root=None):
    os.makedirs(_dir(root), exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["period"], r["first_seen"], r["last_seen"] == ""))
    tmp = path_for(sid, root) + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path_for(sid, root))


def current(rows):
    """{period: row} for the current vintage of each period."""
    cur = {}
    for r in rows:
        if r["last_seen"] == "":
            cur[r["period"]] = r
    return cur


def load(sid, root=None):
    """Current vintage as an observation list, or [] if the series has never been stored."""
    cur = current(read_rows(sid, root))
    out = []
    for p in sorted(cur):
        v = cur[p]["value"]
        out.append((p, float(v) if v != "" else None, cur[p]["flag"]))
    return out


def vintages(sid, root=None):
    """Every stored row (all vintages) as dicts, sorted by period then first_seen."""
    return read_rows(sid, root)


def update(sid, obs, today=None, prev_fetch=None, root=None):
    """Merge a fresh fetch into the store. Returns ``{"new": n, "revised": n, "total": n}``.

    ``today`` and ``prev_fetch`` are ISO dates; ``prev_fetch`` (the last fetch date before this
    one) closes superseded vintages. Pure apart from the file write.
    """
    today = today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    rows = read_rows(sid, root)
    cur = current(rows)
    new = revised = 0
    for p, v, f in obs:
        val, flag = fmt_value(v), f or ""
        old = cur.get(p)
        if old is None:
            rows.append({"period": p, "value": val, "flag": flag, "first_seen": today, "last_seen": ""})
            new += 1
        elif old["value"] != val or old["flag"] != flag:
            old["last_seen"] = prev_fetch or today
            rows.append({"period": p, "value": val, "flag": flag, "first_seen": today, "last_seen": ""})
            revised += 1
    if new or revised or not os.path.exists(path_for(sid, root)):
        write_rows(sid, rows, root)
    return {"new": new, "revised": revised, "total": len(cur) + new}


def reset(sid, root=None):
    p = path_for(sid, root)
    if os.path.exists(p):
        os.remove(p)


def load_meta(root=None):
    p = os.path.join(_dir(root), META)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_meta(meta, root=None):
    os.makedirs(_dir(root), exist_ok=True)
    p = os.path.join(_dir(root), META)
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(p + ".tmp", p)


def children(parent, root=None):
    """Stored child ids of a panel series (``<parent>__<code>``)."""
    d = _dir(root)
    if not os.path.isdir(d):
        return []
    pre = parent + "__"
    return sorted(f[:-4] for f in os.listdir(d) if f.startswith(pre) and f.endswith(".csv"))
