"""The registry: every series, chart, section and tile, declared in one module per section.

Section modules live next to this file and are discovered automatically (any ``*.py`` not
starting with ``_``). Read ``README.md`` in this folder before adding one.
"""
import importlib
import pkgutil
from dataclasses import dataclass, field

from ..spec import (CHART_TYPES, DIRECTIONS, FORMATS, FREQS, ROLES, SOURCES, Chart, Derived, Page,
                    Ref, Section, Series, Tile)
from .. import pages as _pages
from .. import transforms as _transforms

__all__ = ["Series", "Derived", "Ref", "Section", "Chart", "Tile", "Page", "Registry", "load"]


class RegistryError(ValueError):
    pass


@dataclass
class Registry:
    modules: list = field(default_factory=list)
    series: dict = field(default_factory=dict)      # id -> Series
    derived: dict = field(default_factory=dict)     # id -> Derived
    sections: dict = field(default_factory=dict)    # (page, id) -> Section
    charts: dict = field(default_factory=dict)      # id -> Chart
    tiles: list = field(default_factory=list)
    pages: dict = field(default_factory=dict)       # id -> Page override

    def spec(self, sid):
        if sid in self.series:
            return self.series[sid]
        if sid in self.derived:
            return self.derived[sid]
        if "__" in sid:
            parent = sid.split("__", 1)[0]
            if parent in self.series and self.series[parent].split is not None:
                return self.series[parent]
        return None

    def module_of(self, name):
        return {
            "series": [s for s in self.series.values() if s.module == name],
            "derived": [d for d in self.derived.values() if d.module == name],
            "charts": [c for c in self.charts.values() if c.module == name],
            "tiles": [t for t in self.tiles if t.module == name],
        }


def _same(a, b):
    """Two declarations of one series id are allowed only if identical (apart from module)."""
    da, db = dict(a.__dict__), dict(b.__dict__)
    da.pop("module", None)
    db.pop("module", None)
    return da == db


def discover():
    pkg = __name__
    names = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        names.append(info.name)
    return sorted(names), pkg


def load(only_modules=None):
    """Import every section module and return a validated Registry."""
    names, pkg = discover()
    reg = Registry()
    for name in names:
        mod = importlib.import_module(f"{pkg}.{name}")
        reg.modules.append(name)
        for s in getattr(mod, "SERIES", []):
            s.module = s.module or name
            if s.id in reg.series and not _same(reg.series[s.id], s):
                raise RegistryError(f"series {s.id!r} declared differently in {reg.series[s.id].module} and {name}")
            reg.series.setdefault(s.id, s)
        for d in getattr(mod, "DERIVED", []):
            d.module = d.module or name
            if d.id in reg.derived or d.id in reg.series:
                raise RegistryError(f"derived series {d.id!r} declared twice ({name})")
            reg.derived[d.id] = d
        for sec in getattr(mod, "SECTIONS", []):
            sec.module = sec.module or name
            k = (sec.page, sec.id)
            if k in reg.sections:
                raise RegistryError(f"section {sec.page}/{sec.id} declared twice ({reg.sections[k].module}, {name})")
            reg.sections[k] = sec
        for c in getattr(mod, "CHARTS", []):
            c.module = c.module or name
            if c.id in reg.charts:
                raise RegistryError(f"chart id {c.id!r} declared twice ({reg.charts[c.id].module}, {name})")
            reg.charts[c.id] = c
        for t in getattr(mod, "TILES", []):
            t.module = t.module or name
            reg.tiles.append(t)
        for p in getattr(mod, "PAGES", []):
            p.module = p.module or name
            reg.pages[p.id] = p
    reg.tiles.sort(key=lambda t: t.order)
    validate(reg)
    return reg


def validate(reg):
    errs = []
    for s in reg.series.values():
        if s.source not in SOURCES:
            errs.append(f"series {s.id}: unknown source {s.source!r}")
        if s.freq not in FREQS:
            errs.append(f"series {s.id}: unknown freq {s.freq!r}")
        if "__" in s.id:
            errs.append(f"series {s.id}: '__' is reserved for panel children")
        if s.source in ("eurostat", "ecfin") and not s.dataset:
            errs.append(f"series {s.id}: dataset required")
        if s.source in ("ecb", "bis", "oecd") and not (s.dataset and s.key):
            errs.append(f"series {s.id}: dataset (flow) and key required")
    for d in reg.derived.values():
        for i in d.inputs:
            base = i[:-3] if i.endswith("__*") else i
            if reg.spec(base) is None:
                errs.append(f"derived {d.id}: unknown input {i!r}")
    page_ids = set(_pages.PAGE_IDS)
    for c in reg.charts.values():
        if c.page not in page_ids:
            errs.append(f"chart {c.id}: unknown page {c.page!r}")
        if (c.page, c.section) not in reg.sections:
            errs.append(f"chart {c.id}: section {c.page}/{c.section} not declared in any SECTIONS")
        if c.type not in CHART_TYPES:
            errs.append(f"chart {c.id}: unknown type {c.type!r}")
        if c.format not in FORMATS:
            errs.append(f"chart {c.id}: unknown format {c.format!r}")
        if c.id != c.id.lower() or " " in c.id or "_" in c.id:
            errs.append(f"chart {c.id}: ids are kebab-case")
        stories = [r for r in c.series if r.role == "story"]
        if len(stories) > 1:
            errs.append(f"chart {c.id}: more than one story series")
        keys = set()
        for r in c.series:
            if r.role not in ROLES:
                errs.append(f"chart {c.id}: unknown role {r.role!r}")
            if reg.spec(r.series) is None:
                errs.append(f"chart {c.id}: unknown series {r.series!r}")
            k = r.key or r.series
            if k in keys:
                errs.append(f"chart {c.id}: duplicate series key {k!r}")
            keys.add(k)
            try:
                _transforms.validate_spec(r.transform)
            except ValueError as e:
                errs.append(f"chart {c.id}: {e}")
        if not c.series and c.build is None:
            errs.append(f"chart {c.id}: needs series or a build function")
    for t in reg.tiles:
        if reg.spec(t.series) is None:
            errs.append(f"tile {t.id}: unknown series {t.series!r}")
        if t.good_direction not in DIRECTIONS:
            errs.append(f"tile {t.id}: good_direction must be up, down or none")
        if t.page not in page_ids and t.page != "home":
            errs.append(f"tile {t.id}: unknown page {t.page!r}")
    if len({t.id for t in reg.tiles}) != len(reg.tiles):
        errs.append("tile ids must be unique")
    if errs:
        raise RegistryError("registry errors:\n  " + "\n  ".join(errs))
