"""Period strings as the publishers write them, and the arithmetic the transforms need.

Formats (CONTRACT section 3): ``YYYY`` annual, ``YYYY-Qn`` quarterly, ``YYYY-MM`` monthly,
``YYYY-MM-DD`` daily or weekly. ECB weekly periods (``2026-W44``) are converted to a date by
:func:`normalize` (the Friday of that ISO week, the reference day of the Eurosystem weekly
financial statement).
"""
import datetime
import re

_WEEK = re.compile(r"^(\d{4})-W(\d{2})$")
_Q = re.compile(r"^(\d{4})-Q([1-4])$")
_M = re.compile(r"^(\d{4})-(\d{2})$")
_D = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_A = re.compile(r"^(\d{4})$")


def normalize(p, week_day=5):
    """Return the contract form of a period string. Weekly ``YYYY-Www`` becomes a date."""
    p = p.strip()
    m = _WEEK.match(p)
    if m:
        d = datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), week_day)
        return d.isoformat()
    m = re.match(r"^(\d{4})M(\d{2})$", p)  # SDMX compact monthly, just in case
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{4})Q([1-4])$", p)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    return p


def freq_of(p):
    """'A', 'Q', 'M' or 'D' from the shape of the period string; None if unknown."""
    if _M.match(p):
        return "M"
    if _Q.match(p):
        return "Q"
    if _D.match(p):
        return "D"
    if _A.match(p):
        return "A"
    return None


PER_YEAR = {"A": 1, "Q": 4, "M": 12}


def shift(p, n):
    """Shift an A, Q or M period by n periods (n may be negative). Daily: n days."""
    f = freq_of(p)
    if f == "A":
        return str(int(p) + n)
    if f == "Q":
        y, q = int(p[:4]), int(p[-1])
        k = y * 4 + (q - 1) + n
        return f"{k // 4}-Q{k % 4 + 1}"
    if f == "M":
        y, m = int(p[:4]), int(p[5:7])
        k = y * 12 + (m - 1) + n
        return f"{k // 12:04d}-{k % 12 + 1:02d}"
    if f == "D":
        return (datetime.date.fromisoformat(p) + datetime.timedelta(days=n)).isoformat()
    raise ValueError(f"cannot shift period {p!r}")


def start_date(p):
    """First calendar day covered by a period."""
    f = freq_of(p)
    if f == "A":
        return datetime.date(int(p), 1, 1)
    if f == "Q":
        return datetime.date(int(p[:4]), 3 * int(p[-1]) - 2, 1)
    if f == "M":
        return datetime.date(int(p[:4]), int(p[5:7]), 1)
    if f == "D":
        return datetime.date.fromisoformat(p)
    raise ValueError(f"unknown period {p!r}")


def end_date(p):
    """Last calendar day covered by a period."""
    f = freq_of(p)
    if f == "D":
        return datetime.date.fromisoformat(p)
    nxt = start_date(shift(p, 1))
    return nxt - datetime.timedelta(days=1)


def to_freq(p, freq):
    """The period of frequency ``freq`` that contains period ``p`` (only to a lower frequency)."""
    d = start_date(p)
    if freq == "A":
        return f"{d.year}"
    if freq == "Q":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    if freq == "M":
        return f"{d.year}-{d.month:02d}"
    if freq == "D":
        return d.isoformat()
    raise ValueError(freq)


def period_range(first, last):
    """Every period from first to last inclusive (same frequency)."""
    out, p = [], first
    while p <= last:
        out.append(p)
        p = shift(p, 1)
    return out


def from_date(d, freq):
    """Period of frequency ``freq`` containing date ``d`` (a datetime.date or ISO string)."""
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d[:10])
    return to_freq(d.isoformat(), freq)


def compare_key(p):
    """Sort key that orders periods of any frequency by their start date."""
    return start_date(p)
