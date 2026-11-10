"""BuildContext: what a chart's ``build`` hook (and the core bundle writer) can read.

    ctx.obs("hicp_headline")          -> [(period, value, flag), ...]  (raises Missing)
    ctx.has("hicp_headline")          -> bool
    ctx.panel("hicp_cty")             -> {"DE": obs, "FR": obs, ...}   (children of a panel)
    ctx.apply(obs, "ann3m")           -> transformed obs (see eet.transforms)
    ctx.label("hicp_cty__DE")         -> "Germany" (series label, panel label or country name)
    ctx.spec("hicp_headline")         -> the Series or Derived declaration
    ctx.today                         -> "2026-11-09" (UTC date of the run)

Every series read through the context is recorded, so the bundle's ``source`` line,
``data_updated`` stamp and methods entry cover exactly the data the chart used. A derived series
records the inputs it was computed from, and a later read from the cache records them again, so a
chart is credited with a derived series' inputs whichever chart computed it first.
"""
import contextlib

from . import geo, transforms
from .spec import Derived


class Missing(KeyError):
    """A series has no data (failed fetch and nothing stored)."""


class BuildContext:
    def __init__(self, registry, loader, children, updated, today, built_at):
        self.reg = registry
        self._loader = loader          # sid -> obs list ([] if none)
        self._children = children      # parent id -> list of child ids
        self._updated = updated        # sid -> publisher stamp or None
        self.today = today
        self.built_at = built_at
        self._cache = {}
        self._deps = {}                # derived id -> every series id read to compute it
        self._tracks = []

    # -------------------------------------------------------------- tracking
    @contextlib.contextmanager
    def track(self):
        used = set()
        self._tracks.append(used)
        try:
            yield used
        finally:
            self._tracks.pop()

    def _note(self, sid):
        for t in self._tracks:
            t.add(sid)

    # -------------------------------------------------------------- data
    def spec(self, sid):
        return self.reg.spec(sid)

    def obs(self, sid):
        self._note(sid)
        if sid in self._cache:
            out = self._cache[sid]
            for dep in self._deps.get(sid, ()):  # a cached derived series still credits its inputs
                self._note(dep)
        else:
            spec = self.reg.spec(sid)
            if spec is None:
                raise Missing(f"{sid}: not in the registry")
            if isinstance(spec, Derived):
                with self.track() as deps:
                    args = []
                    for i in spec.inputs:
                        args.append(self.panel(i[:-3]) if i.endswith("__*") else self.obs(i))
                    out = spec.fn(*args) or []
                self._deps[sid] = frozenset(deps)
            else:
                out = self._loader(sid) or []
            self._cache[sid] = out
        if not out:
            raise Missing(f"{sid}: no data")
        return out

    def has(self, sid):
        try:
            self.obs(sid)
            return True
        except Missing:
            return False

    def panel(self, parent):
        out = {}
        for cid in self._children(parent):
            try:
                out[cid.split("__", 1)[1]] = self.obs(cid)
            except Missing:
                pass
        if not out:
            raise Missing(f"{parent}: panel has no data")
        return out

    def apply(self, obs, spec):
        return transforms.apply(obs, spec, today=self.today)

    def label(self, sid):
        spec = self.reg.spec(sid)
        if spec is None:
            return sid
        if "__" in sid and getattr(spec, "split", None) is not None:
            code = sid.split("__", 1)[1]
            return spec.labels.get(code) or geo.name(code)
        return spec.label or sid

    def decimals(self, sid):
        spec = self.reg.spec(sid)
        return getattr(spec, "decimals", 1) if spec else 1

    def updated(self, sid):
        spec = self.reg.spec(sid)
        if isinstance(spec, Derived):
            stamps = [self.updated(i[:-3] if i.endswith("__*") else i) for i in spec.inputs]
            return latest_stamp(stamps)
        if spec is not None and spec.split is not None and "__" not in sid:
            return latest_stamp(self._updated(c) for c in self._children(sid))
        return self._updated(sid)


def _parse_stamp(s):
    import datetime
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=datetime.timezone.utc)
            return d
        except (TypeError, ValueError):
            continue
    return None


def latest_stamp(stamps):
    """The most recent of several publisher stamps (strings), keeping its original text."""
    best, best_d = None, None
    for s in stamps:
        if not s:
            continue
        d = _parse_stamp(s)
        if d is None:
            continue
        if best_d is None or d > best_d:
            best, best_d = s, d
    return best
