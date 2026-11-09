"""Pure transforms on observation lists.

An observation list is a list of ``(period, value, flag)`` tuples sorted by period, all periods
of one frequency. ``value`` may be ``None`` (a known gap). Every function returns a new list and
never mutates its input. Flags are carried from the observation at the same period.

Monthly, quarterly and annual transforms look up the comparison period by calendar
(``2026-10`` vs ``2025-10``), so a missing month gives a gap rather than a wrong comparison.
Daily series use position (``n`` observations back) except where a calendar window is stated.

Registry strings (used in ``Ref(transform=...)`` and ``Tile(transform=...)``), chained with ``|``:

    level            identity
    yoy              % change on a year earlier (index -> rate). Daily: as-of 365 days back
    mom, qoq         % change on the previous period
    pct:n            % change on n periods earlier
    ann3m, ann6m     3- and 6-month change, annualised (monthly index)
    ann1q            quarter-on-quarter change, annualised (quarterly index)
    ann:n            n-period change annualised
    diff:n           difference vs n periods earlier (e.g. diff:12 = 12-month change of a rate)
    chg12m           diff:12 on monthly, diff:4 on quarterly
    roll:n           rolling mean over n periods
    rebase:P         index rebased so that period P (or the average of year P) = 100
    z:START:END      z-score against the mean and standard deviation of START..END
    trim:START       drop observations before START (also trim:START:END)
    scale:k          multiply by k
    step             event series (change dates) -> step-shaped daily points, extended to today
    resample:F:how   to frequency F (A/Q/M) taking last/mean/first; event series are forward-filled
    dropna           drop None values
"""
import datetime
import math
import statistics

from . import periods as P

Obs = list  # list[tuple[str, float | None, str]]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _drop_leading_none(out):
    i = 0
    while i < len(out) and out[i][1] is None:
        i += 1
    return out[i:]


def _freq(obs):
    return P.freq_of(obs[0][0]) if obs else None


def _base_lookup(obs, n):
    """Return a function i -> value n periods earlier (calendar for A/Q/M, position for D)."""
    freq = _freq(obs)
    if freq in ("A", "Q", "M"):
        vals = {p: v for p, v, _ in obs}
        return lambda i: vals.get(P.shift(obs[i][0], -n))
    return lambda i: obs[i - n][1] if i - n >= 0 else None


def asof(obs, date):
    """Last value at or before ``date`` (ISO string or period of the same frequency)."""
    best = None
    for p, v, _ in obs:
        if p <= date:
            if v is not None:
                best = v
        else:
            break
    return best


def level(obs):
    return list(obs)


def pct_change(obs, n=1):
    """Percentage change on n periods earlier."""
    base = _base_lookup(obs, n)
    out = []
    for i, (p, v, f) in enumerate(obs):
        b = base(i)
        val = None if v is None or b in (None, 0) else (v / b - 1.0) * 100.0
        out.append((p, _clean(val), f))
    return _drop_leading_none(out)


def yoy(obs):
    """Percentage change on the same period a year earlier (from an index or level)."""
    freq = _freq(obs)
    if freq in P.PER_YEAR:
        return pct_change(obs, P.PER_YEAR[freq])
    out = []
    for p, v, f in obs:
        ref = (datetime.date.fromisoformat(p) - datetime.timedelta(days=365)).isoformat()
        b = asof(obs, ref) if ref >= obs[0][0] else None
        val = None if v is None or b in (None, 0) else (v / b - 1.0) * 100.0
        out.append((p, _clean(val), f))
    return _drop_leading_none(out)


def mom(obs):
    return pct_change(obs, 1)


qoq = mom


def annualised(obs, n=3):
    """n-period change annualised: ((x_t / x_{t-n}) ** (periods_per_year / n) - 1) * 100."""
    freq = _freq(obs)
    if freq not in P.PER_YEAR:
        raise ValueError("annualised needs annual, quarterly or monthly data")
    k = P.PER_YEAR[freq] / n
    base = _base_lookup(obs, n)
    out = []
    for i, (p, v, f) in enumerate(obs):
        b = base(i)
        if v is None or b in (None, 0) or (v / b) <= 0:
            val = None
        else:
            val = ((v / b) ** k - 1.0) * 100.0
        out.append((p, _clean(val), f))
    return _drop_leading_none(out)


def ann3m(obs):
    return annualised(obs, 3)


def ann6m(obs):
    return annualised(obs, 6)


def ann1q(obs):
    return annualised(obs, 1)


def diff(obs, n=1):
    """Difference vs n periods earlier, in the series' own units."""
    base = _base_lookup(obs, n)
    out = []
    for i, (p, v, f) in enumerate(obs):
        b = base(i)
        out.append((p, None if v is None or b is None else v - b, f))
    return _drop_leading_none(out)


def change_12m(obs):
    """12-month change (monthly) or 4-quarter change (quarterly) of a rate, in points."""
    freq = _freq(obs)
    return diff(obs, P.PER_YEAR.get(freq, 12))


def rolling_mean(obs, n=3):
    """Mean of the last n observations (None if any is missing)."""
    out = []
    for i, (p, v, f) in enumerate(obs):
        window = [x[1] for x in obs[max(0, i - n + 1): i + 1]]
        ok = len(window) == n and all(w is not None for w in window)
        out.append((p, sum(window) / n if ok else None, f))
    return _drop_leading_none(out)


def rebase(obs, base):
    """Rebase to 100 at period ``base``; a year (``2019``) on M/Q data uses that year's mean."""
    vals = [v for p, v, _ in obs if v is not None and (p == base or (len(base) == 4 and p[:4] == base))]
    if not vals:
        raise ValueError(f"rebase period {base} not in series")
    b = sum(vals) / len(vals) if (len(base) == 4 and _freq(obs) != "A") else vals[0]
    return [(p, None if v is None else v / b * 100.0, f) for p, v, f in obs]


def spread(a, b):
    """a minus b on the periods both have (flag from a)."""
    bv = {p: v for p, v, _ in b}
    out = []
    for p, v, f in a:
        if p in bv:
            w = bv[p]
            out.append((p, None if v is None or w is None else v - w, f))
    return out


def zscore(obs, start, end):
    """(x - mean) / sd, with mean and sample sd taken over the window start..end inclusive."""
    window = [v for p, v, _ in obs if start <= p <= end and v is not None]
    if len(window) < 2:
        raise ValueError("z-score window needs at least two observations")
    mu, sd = statistics.fmean(window), statistics.stdev(window)
    if sd == 0:
        raise ValueError("z-score window has zero variance")
    return [(p, None if v is None else (v - mu) / sd, f) for p, v, f in obs]


def trim(obs, start=None, end=None):
    """Keep observations with start <= period <= end (string comparison within one frequency)."""
    return [o for o in obs if (start is None or o[0] >= start) and (end is None or o[0] <= end)]


def scale(obs, k):
    return [(p, None if v is None else v * k, f) for p, v, f in obs]


def dropna(obs):
    return [o for o in obs if o[1] is not None]


def step(obs, end=None):
    """Turn an event series (value effective from each change date) into step-shaped points.

    Each change becomes two points, the old value on the day before and the new value on the day,
    so any line renderer draws vertical steps. The last value is extended to ``end`` (ISO date).
    """
    out = []
    prev = None
    for p, v, f in obs:
        if prev is not None:
            day_before = P.shift(p, -1)
            if not out or out[-1][0] < day_before:
                out.append((day_before, prev, ""))
        out.append((p, v, f))
        prev = v
    if end and out and end > out[-1][0]:
        out.append((end, prev, ""))
    return out


def resample(obs, freq, how="last", ffill=False, end=None):
    """Aggregate to a lower frequency. ``ffill`` carries the last value into empty periods up to
    ``end`` (needed for event series such as policy rates)."""
    buckets = {}
    order = []
    for p, v, f in obs:
        if v is None:
            continue
        q = P.to_freq(p, freq)
        if q not in buckets:
            buckets[q] = []
            order.append(q)
        buckets[q].append((v, f))
    out = []
    for q in order:
        vs = buckets[q]
        if how == "last":
            v, f = vs[-1]
        elif how == "first":
            v, f = vs[0]
        elif how == "mean":
            v, f = sum(x[0] for x in vs) / len(vs), vs[-1][1]
        else:
            raise ValueError(how)
        out.append((q, v, f))
    if ffill and out:
        last = P.to_freq(end, freq) if end else out[-1][0]
        have = {p: (v, f) for p, v, f in out}
        filled, cur = [], None
        for q in P.period_range(out[0][0], last):
            if q in have:
                cur = have[q]
                filled.append((q, cur[0], cur[1]))
            else:
                filled.append((q, cur[0], ""))
        out = filled
    return out


# ------------------------------------------------------------------ registry string interface

def _num(x):
    return int(x) if x.lstrip("-").isdigit() else float(x)


def apply(obs, spec, today=None):
    """Apply a transform given as None, a callable(obs) or a registry string (see module doc)."""
    if spec is None:
        return list(obs)
    if callable(spec):
        return spec(obs)
    if isinstance(spec, (list, tuple)):
        for s in spec:
            obs = apply(obs, s, today=today)
        return obs
    for part in str(spec).split("|"):
        part = part.strip()
        if not part:
            continue
        name, *args = part.split(":")
        if name == "level":
            obs = level(obs)
        elif name == "yoy":
            obs = yoy(obs)
        elif name in ("mom", "qoq"):
            obs = pct_change(obs, 1)
        elif name == "pct":
            obs = pct_change(obs, _num(args[0]))
        elif name == "ann3m":
            obs = ann3m(obs)
        elif name == "ann6m":
            obs = ann6m(obs)
        elif name == "ann1q":
            obs = ann1q(obs)
        elif name == "ann":
            obs = annualised(obs, _num(args[0]))
        elif name == "diff":
            obs = diff(obs, _num(args[0]) if args else 1)
        elif name == "chg12m":
            obs = change_12m(obs)
        elif name == "roll":
            obs = rolling_mean(obs, _num(args[0]))
        elif name == "rebase":
            obs = rebase(obs, args[0])
        elif name == "z":
            obs = zscore(obs, args[0], args[1])
        elif name == "trim":
            obs = trim(obs, args[0] or None, args[1] if len(args) > 1 else None)
        elif name == "scale":
            obs = scale(obs, float(args[0]))
        elif name == "dropna":
            obs = dropna(obs)
        elif name == "step":
            obs = step(obs, end=args[0] if args else today)
        elif name == "resample":
            obs = resample(obs, args[0], args[1] if len(args) > 1 else "last",
                           ffill=len(args) > 2 and args[2] == "ffill", end=today)
        else:
            raise ValueError(f"unknown transform {name!r} in {spec!r}")
    return obs


def validate_spec(spec):
    """Raise ValueError if a registry transform string uses an unknown name."""
    if spec is None or callable(spec):
        return
    known = {"level", "yoy", "mom", "qoq", "pct", "ann3m", "ann6m", "ann1q", "ann", "diff", "chg12m",
             "roll", "rebase", "z", "trim", "scale", "dropna", "step", "resample"}
    specs = spec if isinstance(spec, (list, tuple)) else [spec]
    for s in specs:
        if callable(s):
            continue
        for part in str(s).split("|"):
            name = part.strip().split(":")[0]
            if name and name not in known:
                raise ValueError(f"unknown transform {name!r}")
