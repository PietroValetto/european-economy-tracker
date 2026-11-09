"""Fetch every registered series, update the vintage store, write site/data, validate it.

    cd pipeline
    python3 -m eet.build                 # full live build
    python3 -m eet.build --only inflation   # one registry module (others read from store/)
    python3 -m eet.build --offline       # no network: build from store/ (and the raw cache)

Exit status is non-zero only if more than 20% of the attempted series fail or if the contract
check fails (CONTRACT section 7). Failed series are listed in index.json ``failed``.
"""
import argparse
import datetime
import json
import os
import sys
import time

from . import bundles, check, http, paths, sources, store
from .context import BuildContext, Missing, latest_stamp
from .registry import load
from .spec import Derived, Series

FAIL_SHARE = 0.20
EUROSTAT_PAUSE = 0.3  # seconds between Eurostat requests


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def _closure(reg, names):
    """Series ids (registry Series only) a set of modules needs, including other modules' inputs."""
    need = set()

    def add(sid):
        spec = reg.spec(sid)
        if spec is None:
            return
        if isinstance(spec, Series):
            need.add(spec.id)
        else:
            for i in spec.inputs:
                add(i[:-3] if i.endswith("__*") else i)

    for name in names:
        m = reg.module_of(name)
        for s in m["series"]:
            need.add(s.id)
        for d in m["derived"]:
            add(d.id)
        for c in m["charts"]:
            for r in c.series:
                add(r.series)
        for t in m["tiles"]:
            add(t.series)
    return need


def fetch_all(reg, ids, today, meta, offline=False, log=print):
    """Fetch the given series ids sequentially. Returns (results rows, failed list, memory obs)."""
    rows, failed, memory = [], [], {}
    ordered = sorted(ids, key=lambda i: (reg.series[i].source, reg.series[i].module, i))
    last_source = None
    for sid in ordered:
        s = reg.series[sid]
        if s.source == "eurostat" and last_source == "eurostat" and not offline:
            time.sleep(EUROSTAT_PAUSE)
        last_source = s.source
        t0 = time.time()
        row = {"id": sid, "source": s.source, "module": s.module, "status": "ok", "latest": "", "value": "",
               "new": 0, "revised": 0, "secs": 0.0, "error": ""}
        try:
            res = sources.fetch(s, offline=offline)
            h = store.spec_hash(s)
            for cid, obs in sorted(res.obs.items()):
                m = meta.get(cid, {})
                if not offline:
                    if m.get("spec") and m["spec"] != h:
                        store.reset(cid)
                        m = {}
                    stats = store.update(cid, obs, today=today, prev_fetch=m.get("last_fetched"))
                    row["new"] += stats["new"]
                    row["revised"] += stats["revised"]
                    meta[cid] = {"spec": h, "last_fetched": today, "updated": res.updated, "url": res.url}
                else:
                    memory[cid] = obs
            for cid in res.empty:
                failed.append({"id": cid, "error": "no observations returned"})
            last = max(res.obs.values(), key=lambda o: o[-1][0] if o else "")
            row["latest"], row["value"] = last[-1][0], last[-1][1]
            if s.split is not None:
                row["latest"] += f" ({len(res.obs)} series)"
        except Exception as e:  # noqa: BLE001 - every failure is reported, none stops the build
            row["status"] = "FAILED"
            row["error"] = f"{type(e).__name__}: {e}"[:300]
            failed.append({"id": sid, "error": row["error"]})
        row["secs"] = round(time.time() - t0, 1)
        rows.append(row)
        log(f"  {row['status']:6} {sid:34} {row['secs']:5.1f}s {row['latest']} {row['error'][:90]}")
    return rows, failed, memory


def _static_uses(reg, chart):
    """Series ids a chart refers to through its refs (derived inputs expanded)."""
    out = set()

    def add(sid):
        out.add(sid)
        spec = reg.spec(sid)
        if spec is not None and hasattr(spec, "inputs"):
            for i in spec.inputs:
                add(i[:-3] if i.endswith("__*") else i)

    for r in chart.series:
        add(r.series)
    return out


def _uses(failed_id, used):
    for u in used:
        if u == failed_id or u.startswith(failed_id + "__") or failed_id.startswith(u + "__"):
            return True
    return False


def attach_chart_ids(reg, failed, used_by_chart):
    """Add ``chart_ids`` (charts that use the failed series) to every ``failed`` entry."""
    for f in failed:
        ids = []
        for cid, chart in sorted(reg.charts.items()):
            used = set(used_by_chart.get(cid, set())) | _static_uses(reg, chart)
            if _uses(f["id"], used):
                ids.append(cid)
        f["chart_ids"] = ids
    return failed


def make_context(reg, today, built_at, meta, memory):
    def loader(sid):
        if sid in memory:
            return memory[sid]
        return store.load(sid)

    def children(parent):
        ids = set(store.children(parent)) | {k for k in memory if k.startswith(parent + "__")}
        return sorted(ids)

    def updated(sid):
        return (meta.get(sid) or {}).get("updated")

    return BuildContext(reg, loader, children, updated, today, built_at)


def _existing_bundles():
    out = {}
    if os.path.isdir(paths.CHARTS):
        for f in os.listdir(paths.CHARTS):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(paths.CHARTS, f), encoding="utf-8") as fh:
                        out[f[:-5]] = json.load(fh)
                except ValueError:
                    pass
    return out


def build_site(reg, ctx, chart_ids, failed, full, log=print):
    """Write chart bundles for ``chart_ids``, then index/methods/snapshot for the whole registry."""
    os.makedirs(paths.CHARTS, exist_ok=True)
    chart_errors, used_by_chart, built = [], {}, {}
    for cid in chart_ids:
        chart = reg.charts[cid]
        try:
            b, used, dropped = bundles.build_chart(ctx, chart)
        except (bundles.ChartError, Missing, ValueError, ZeroDivisionError, KeyError, IndexError) as e:
            chart_errors.append((cid, f"{type(e).__name__}: {e}"))
            continue
        for sid, msg in dropped:
            chart_errors.append((cid, f"dropped {sid}: {msg}"))
        bundles.write_json(os.path.join(paths.CHARTS, f"{cid}.json"), b)
        used_by_chart[cid] = used
        built[cid] = b
    attach_chart_ids(reg, failed, used_by_chart)
    existing = _existing_bundles()
    if full:  # remove bundles of charts no longer in the registry
        for cid in list(existing):
            if cid not in reg.charts:
                os.remove(os.path.join(paths.CHARTS, f"{cid}.json"))
                existing.pop(cid)
    # strip: rebuild every tile; fall back to the last good tile if a series is missing
    prev_idx = {}
    ipath = os.path.join(paths.SITE_DATA, "index.json")
    if os.path.exists(ipath):
        try:
            with open(ipath, encoding="utf-8") as fh:
                prev_idx = {t["id"]: t for t in json.load(fh).get("strip", [])}
        except (ValueError, KeyError, TypeError):
            prev_idx = {}
    strip, snap_extra = [], {}
    for t in reg.tiles:
        try:
            with ctx.track() as used:
                entry = bundles.tile_entry(ctx, t)
            spec = ctx.spec(t.series)
            src = ""
            if spec is not None and not isinstance(spec, Derived):
                src = sources.source_text(spec)
            snap_extra[t.id] = {"series": t.series, "source": src,
                                "data_updated": latest_stamp(ctx.updated(s) for s in used)}
        except (Missing, ValueError) as e:
            chart_errors.append((f"tile:{t.id}", str(e)))
            entry = prev_idx.get(t.id)
            if entry is None:
                continue
        strip.append(entry)
    index = bundles.build_index(reg, ctx.built_at, {k: v.get("type") for k, v in existing.items()}, strip, failed)
    bundles.write_json(os.path.join(paths.SITE_DATA, "index.json"), index, compact=False)
    # methods: fresh entries for charts built now, previous entries for others still on disk
    prev_methods = {}
    mpath = os.path.join(paths.SITE_DATA, "methods.json")
    if os.path.exists(mpath):
        try:
            with open(mpath, encoding="utf-8") as fh:
                prev_methods = {e["id"]: e for e in json.load(fh).get("entries", [])}
        except (ValueError, KeyError, TypeError):
            prev_methods = {}
    entries = []
    for cid in sorted(existing):
        if cid in built:
            entries.append(bundles.methods_entry(ctx, reg.charts[cid], used_by_chart[cid], built[cid]))
        elif cid in prev_methods:
            entries.append(prev_methods[cid])
        elif cid in reg.charts:
            c = reg.charts[cid]
            entries.append({"id": cid, "title": c.title, "what": c.what or c.subtitle,
                            "transform": c.transform_text or "", "sources": [], "frequency": existing[cid].get("frequency"),
                            "caveats": c.caveats, "original": bool(c.original),
                            "updated": existing[cid].get("data_updated")})
    bundles.write_json(mpath, {"entries": entries}, compact=False)
    with open(os.path.join(paths.SITE_DATA, "snapshot.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write(bundles.snapshot_csv(strip, snap_extra, ctx.built_at))
    return built, chart_errors, strip


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the European Economy Tracker data.")
    ap.add_argument("--only", action="append", default=[], help="registry module to build (repeatable)")
    ap.add_argument("--offline", action="store_true", help="no network: build from store/ and the cache")
    ap.add_argument("--no-check", action="store_true", help="skip the contract check")
    a = ap.parse_args(argv)
    t_start = time.time()
    now = utc_now()
    today = now.date().isoformat()
    built_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    reg = load()
    for name in a.only:
        if name not in reg.modules:
            print(f"unknown module {name!r}; modules: {', '.join(reg.modules)}")
            return 2
    names = a.only or reg.modules
    ids = sorted(_closure(reg, names) if a.only else set(reg.series))
    meta = store.load_meta()
    http.reset()
    print(f"European Economy Tracker build {built_at}  ({'offline' if a.offline else 'live'}; "
          f"modules: {', '.join(names)}; {len(ids)} series)")
    memory = {}
    rows, failed = [], []
    if a.offline:
        # keep the last live run's failures; use the raw cache only for series never stored
        try:
            with open(os.path.join(paths.SITE_DATA, "index.json"), encoding="utf-8") as fh:
                failed = [f for f in json.load(fh).get("failed", []) if f.get("id") in ids
                          or f.get("id", "").split("__")[0] in ids]
        except (OSError, ValueError):
            failed = []
        missing = [i for i in ids if not store.load(i) and not store.children(i)]
        if missing:
            rows, failed2, memory = fetch_all(reg, missing, today, meta, offline=True)
            failed += failed2
    else:
        rows, failed, memory = fetch_all(reg, ids, today, meta)
        store.save_meta(meta)
        if a.only:  # keep earlier failures of series this partial run did not attempt
            try:
                with open(os.path.join(paths.SITE_DATA, "index.json"), encoding="utf-8") as fh:
                    failed += [f for f in json.load(fh).get("failed", [])
                               if f.get("id", "").split("__")[0] not in ids and f.get("id") in reg.series
                               or f.get("id", "").split("__")[0] in reg.series
                               and f.get("id", "").split("__")[0] not in ids]
            except (OSError, ValueError):
                pass
    ctx = make_context(reg, today, built_at, meta, memory)
    chart_ids = sorted(c.id for c in reg.charts.values() if c.module in names)
    built, chart_errors, strip = build_site(reg, ctx, chart_ids, failed, full=not a.only)
    # summary
    print()
    print(f"{'series':36} {'source':9} {'status':7} {'latest':24} {'value':>12} {'new':>5} {'rev':>4} {'secs':>5}")
    print("-" * 108)
    for r in rows:
        val = r["value"]
        val = f"{val:.4g}" if isinstance(val, float) else str(val)
        print(f"{r['id'][:36]:36} {r['source']:9} {r['status']:7} {str(r['latest'])[:24]:24} {val:>12} "
              f"{r['new']:>5} {r['revised']:>4} {r['secs']:>5}")
    for r in rows:
        if r["error"]:
            print(f"  FAILED {r['id']}: {r['error']}")
    for cid, msg in chart_errors:
        print(f"  chart {cid}: {msg}")
    n_attempt = len(rows)
    n_fail = sum(1 for r in rows if r["status"] != "ok")
    print(f"\nseries: {n_attempt - n_fail}/{n_attempt} ok; charts built: {len(built)}/{len(chart_ids)}; "
          f"tiles: {len(strip)}; time {time.time() - t_start:.0f}s")
    code = 0
    if n_attempt and n_fail / n_attempt > FAIL_SHARE:
        print(f"FAIL: {n_fail}/{n_attempt} series failed (> {FAIL_SHARE:.0%})")
        code = 1
    if not a.no_check:
        rep, n = check.run()
        for x in rep.errors:
            print("ERROR:", x)
        print(f"contract check: {n} bundles, {len(rep.errors)} errors, {len(rep.warnings)} warnings")
        if rep.errors:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
