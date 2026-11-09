// Periods, numbers and dates in the house style: true minus signs, tabular figures,
// British date order, sentence case.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
  'September', 'October', 'November', 'December'];

/** Parse a contract period (YYYY, YYYY-Qn, YYYY-MM, YYYY-MM-DD) into UTC start/end. */
export function periodBounds(p) {
  if (p == null) return null;
  const s = String(p);
  let m;
  if ((m = /^(\d{4})$/.exec(s))) {
    const y = +m[1];
    return { kind: 'A', start: Date.UTC(y, 0, 1), end: Date.UTC(y + 1, 0, 1) };
  }
  if ((m = /^(\d{4})-Q([1-4])$/.exec(s))) {
    const y = +m[1], q = +m[2];
    return { kind: 'Q', start: Date.UTC(y, (q - 1) * 3, 1), end: Date.UTC(y, q * 3, 1) };
  }
  if ((m = /^(\d{4})-(\d{2})$/.exec(s))) {
    const y = +m[1], mo = +m[2] - 1;
    return { kind: 'M', start: Date.UTC(y, mo, 1), end: Date.UTC(y, mo + 1, 1) };
  }
  if ((m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s))) {
    const t = Date.UTC(+m[1], +m[2] - 1, +m[3]);
    return { kind: 'D', start: t, end: t + 86400000 };
  }
  return null;
}

export const isPeriod = (p) => periodBounds(p) !== null;

/** Where a period sits on a time axis: the midpoint for M/Q/A, the day itself for D. */
export function periodX(p) {
  const b = periodBounds(p);
  if (!b) return null;
  return b.kind === 'D' ? b.start : (b.start + b.end) / 2;
}

/** "Oct 2026", "Q3 2026", "2026", "6 Nov 2026". */
export function periodLabel(p, { long = false } = {}) {
  const s = String(p);
  const b = periodBounds(s);
  if (!b) return s;
  const d = new Date(b.start);
  const y = d.getUTCFullYear();
  switch (b.kind) {
    case 'A': return String(y);
    case 'Q': return `Q${s.slice(-1)} ${y}`;
    case 'M': return `${(long ? MONTHS_LONG : MONTHS)[d.getUTCMonth()]} ${y}`;
    default: return `${d.getUTCDate()} ${(long ? MONTHS_LONG : MONTHS)[d.getUTCMonth()]} ${y}`;
  }
}

/** Compact label for heatmap columns: "Oct 25", "Q3 26", "2026". */
export function periodShort(p) {
  const s = String(p);
  const b = periodBounds(s);
  if (!b) return s;
  const d = new Date(b.start);
  const yy = String(d.getUTCFullYear()).slice(2);
  if (b.kind === 'A') return String(d.getUTCFullYear());
  if (b.kind === 'Q') return `Q${s.slice(-1)} ${yy}`;
  if (b.kind === 'M') return `${MONTHS[d.getUTCMonth()]} ${yy}`;
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

const MINUS = '−';

/** Fixed decimals, true minus, grouped thousands, no "-0.0". */
export function fmtNum(v, decimals = 1) {
  if (v == null || Number.isNaN(+v)) return '–';
  const n = +v;
  let s = Math.abs(n).toLocaleString('en-GB', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const zero = +s.replace(/,/g, '') === 0;
  return (n < 0 && !zero ? MINUS : '') + s;
}

/** Signed change: "+0.2", "−0.1", "0.0". */
export function fmtChange(v, decimals = 1) {
  if (v == null) return '–';
  const s = fmtNum(v, decimals);
  return +v > 0 && s.replace(/[^1-9]/g, '') !== '' ? '+' + s : s;
}

/** Unit suffix appended to values in labels and tooltips. */
export function unitSuffix(units) {
  if (!units) return '';
  const u = String(units).trim();
  if (u === '%' || u.startsWith('% ')) return '%';
  if (u === 'pp') return ' pp';
  return '';
}

export function decimalsOf(bundle) {
  return bundle && Number.isInteger(bundle.decimals) ? bundle.decimals : 1;
}

/** A value as it appears on a chart: "4.0%", "−0.3 pp", "96.9". */
export function fmtValue(v, bundle, { unit = true } = {}) {
  return fmtNum(v, decimalsOf(bundle)) + (unit && v != null ? unitSuffix(bundle && bundle.units) : '');
}

/** Infer decimals from a raw number when no decimals field is given (2.5 -> 1, 1.1165 -> 4). */
export function inferDecimals(v) {
  if (v == null || !Number.isFinite(+v)) return 1;
  const s = String(v);
  const i = s.indexOf('.');
  return i < 0 ? 1 : Math.min(4, Math.max(1, s.length - i - 1));
}

export const FLAG_LABELS = {
  e: 'estimate',
  p: 'provisional',
  f: 'forecast',
  b: 'break in series',
  r: 'revised',
  c: 'confidential',
  u: 'low reliability',
  d: 'definition differs',
};
export const flagLabel = (f) => (f ? FLAG_LABELS[f] || `flag ${f}` : '');

const TZ = 'Europe/Brussels';

/** "9 November 2026, 07:00 Brussels time" from an ISO timestamp. */
export function fmtStamp(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(+d)) return iso;
  const date = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, day: 'numeric', month: 'long', year: 'numeric' }).format(d);
  const time = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false }).format(d);
  return `${date}, ${time} Brussels time`;
}

/** "4 Nov 2026" from an ISO timestamp or date. */
export function fmtDay(iso) {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
  if (m) return `${+m[3]} ${MONTHS[+m[2] - 1]} ${m[1]}`;
  const d = new Date(iso);
  if (Number.isNaN(+d)) return String(iso);
  return new Intl.DateTimeFormat('en-GB', { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

/** Today's date (YYYY-MM-DD) in Brussels, for the calendar. */
export function todayBrussels() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const get = (t) => parts.find((x) => x.type === t).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export function weekdayLong(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return `${['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][dt.getUTCDay()]} ${d} ${MONTHS_LONG[m - 1]}`;
}

/** Escape text for innerHTML templates. */
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
