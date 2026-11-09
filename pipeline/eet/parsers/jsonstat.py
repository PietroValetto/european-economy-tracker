"""JSON-stat 2.0 (Eurostat dissemination API and DG ECFIN Redisstat, same engine).

``value`` and ``status`` may be sparse objects keyed by flat index or dense arrays. The flat
index is row-major over ``id``/``size``. Eurostat never errors on a bad code: it returns HTTP 200
with that dimension empty, so :func:`parse` raises when a filtered dimension is empty or when a
non-split dimension has more than one code.
"""
import json

from .. import periods as P


class JsonStatError(ValueError):
    pass


def load(body):
    d = json.loads(body) if isinstance(body, (bytes, str)) else body
    if isinstance(d, dict) and "error" in d:
        err = d["error"]
        if isinstance(err, list) and err:
            err = err[0]
        raise JsonStatError(f"publisher error: {err}")
    for k in ("id", "size", "dimension"):
        if k not in d:
            raise JsonStatError(f"not a JSON-stat dataset (missing {k!r})")
    return d


def _codes(dim):
    idx = dim["category"]["index"]
    if isinstance(idx, dict):
        return sorted(idx, key=idx.get)
    return list(idx)


def _time_dim(d):
    for name in ("time", "TIME_PERIOD", "TIME"):
        if name in d["id"]:
            return name
    raise JsonStatError("no time dimension")


def parse_multi(body, split=None):
    """Return ``{code_of_split_dim: obs}`` (or ``{None: obs}`` without ``split``) and ``updated``.

    Every non-time, non-split dimension must have exactly one code.
    """
    d = load(body)
    ids, sizes = d["id"], d["size"]
    tname = _time_dim(d)
    for name, size in zip(ids, sizes):
        if name in (tname, split):
            continue
        if size != 1:
            raise JsonStatError(f"dimension {name} has {size} codes; filter it to one "
                                f"(sizes: {dict(zip(ids, sizes))})")
    if split is not None and split not in ids:
        raise JsonStatError(f"split dimension {split!r} not in dataset dimensions {ids}")
    codes = {name: _codes(d["dimension"][name]) for name in ids}
    strides, acc = [], 1
    for size in reversed(sizes):
        strides.append(acc)
        acc *= size
    strides.reverse()
    vals = d.get("value", {})
    stat = d.get("status", {}) or {}
    if isinstance(vals, list):
        vals = {str(i): v for i, v in enumerate(vals) if v is not None}
    if isinstance(stat, list):
        stat = {str(i): s for i, s in enumerate(stat) if s}
    ti, si = ids.index(tname), (ids.index(split) if split else None)
    out = {}
    for k, v in vals.items():
        if v is None:
            continue
        flat = int(k)
        coord = []
        for size, stride in zip(sizes, strides):
            coord.append((flat // stride) % size)
        period = P.normalize(codes[tname][coord[ti]])
        key = codes[split][coord[si]] if split else None
        out.setdefault(key, []).append((period, float(v), str(stat.get(k, "") or "")))
    for key in out:
        out[key].sort(key=lambda o: o[0])
    if split:
        for code in codes[split]:
            out.setdefault(code, [])
    return out, d.get("updated")


def parse(body):
    """Single-series parse: returns ``(obs, updated)``. Raises if the selection is not unique."""
    out, updated = parse_multi(body)
    return out.get(None, []), updated


def labels(body, dim):
    """``{code: label}`` for one dimension (useful for country or item names)."""
    d = load(body)
    cat = d["dimension"][dim]["category"]
    return dict(cat.get("label", {}))
