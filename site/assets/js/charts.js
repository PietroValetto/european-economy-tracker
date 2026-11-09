// Chart renderer. One bundle in, one figure out: kicker, title, subtitle, legend, window
// buttons, the chart, source line, actions, text alternative. Observable Plot draws the
// marks and axes; latest-value labels, the hover crosshair and the tooltip are drawn here
// so they follow the house style exactly.

import * as Plot from 'https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm';
import * as d3 from 'https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm';
import { href } from './config.js';
import {
  periodBounds, periodLabel, periodShort, fmtNum, fmtChange, fmtValue, unitSuffix, decimalsOf,
  flagLabel, FLAG_LABELS, fmtDay, esc, isPeriod,
} from './format.js';
import { exportPNG } from './export.js';

export const TYPES = ['line', 'bar', 'bar-line', 'stacked-bar', 'contrib', 'scatter', 'heatmap', 'table', 'country-strip'];
const WINDOWS = [['1y', 1], ['5y', 5], ['10y', 10], ['max', Infinity]];
const YEAR = 365.25 * 864e5;
const SVGNS = 'http://www.w3.org/2000/svg';

// ------------------------------------------------------------------ colours from tokens
let C;
export function colors() {
  if (C) return C;
  const cs = getComputedStyle(document.documentElement);
  const v = (n, f) => (cs.getPropertyValue(n).trim() || f);
  C = {
    ink: v('--pe-ink', '#1B1712'), slate: v('--pe-slate', '#6B655C'), mute: v('--pe-mute', '#A8A296'),
    green: v('--pe-green', '#1F8A5B'), deep: v('--pe-green-deep', '#12563A'), amber: v('--pe-amber', '#F0A93B'),
    paper: v('--pe-paper', '#FAF7F0'), card: v('--pe-card', '#FBF8F1'), canvas: v('--pe-canvas', '#E7E1D4'),
    ruleSoft: v('--pe-rule-soft', 'rgba(27,23,18,.08)'), rule: v('--pe-rule', 'rgba(27,23,18,.12)'),
    ruleStrong: v('--pe-rule-strong', 'rgba(27,23,18,.22)'),
  };
  return C;
}
const FONT_BODY = "Inter, 'Helvetica Neue', Arial, sans-serif";
const FONT_DISPLAY = "Archivo, 'Helvetica Neue', Arial, sans-serif";

/** Series colours by role. Amber only on the (single) story series. */
function styleSeries(series) {
  const c = colors();
  const basePal = [c.green, c.deep, c.slate, c.mute, c.canvas];
  const ctxPal = [c.slate, c.mute];
  let b = 0, k = 0, storySeen = false;
  return series.map((s) => {
    let role = s.role || 'base';
    if (role === 'story' && storySeen) {
      console.warn(`[eet] more than one story series; "${s.key}" drawn as base`);
      role = 'base';
    }
    if (role === 'story') { storySeen = true; return { ...s, role, color: c.amber, text: c.ink, width: 2.5 }; }
    if (role === 'band') return { ...s, role, color: c.green, text: c.green, width: 0 };
    if (role === 'context') { const col = ctxPal[k++ % 2]; return { ...s, role, color: col, text: c.slate, width: 1.5 }; }
    const col = basePal[b++ % basePal.length];
    return { ...s, role, color: col, text: col === c.mute || col === c.canvas ? c.slate : col, width: 2 };
  });
}

// ------------------------------------------------------------------ data prep
const num = (v) => (v == null || v === '' || Number.isNaN(+v) ? null : +v);

function prepTime(series) {
  return series.map((s) => {
    const rows = [];
    for (const pt of s.points || []) {
      const b = periodBounds(pt[0]);
      if (!b) continue;
      const x = b.kind === 'D' ? b.start : (b.start + b.end) / 2;
      const r = { key: s.key, period: pt[0], kind: b.kind, x, x1: b.start, x2: b.end, flag: (s.flags && s.flags[pt[0]]) || null };
      if (s.role === 'band') { r.low = num(pt[1]); r.high = num(pt[2]); r.value = r.high; }
      else r.value = num(pt[1]);
      rows.push(r);
    }
    rows.sort((a, z) => a.x - z.x);
    return { ...s, rows };
  });
}

function timeExtent(series) {
  let lo = Infinity, hi = -Infinity;
  for (const s of series) for (const r of s.rows) { if (r.x < lo) lo = r.x; if (r.x > hi) hi = r.x; }
  return [lo, hi];
}

/** Window options that make sense for this much data. */
function windowOptions(series) {
  const [lo, hi] = timeExtent(series);
  if (!Number.isFinite(lo)) return ['max'];
  const span = hi - lo;
  return WINDOWS.filter(([, y]) => y === Infinity || y * YEAR < span * 0.98).map(([k]) => k);
}

function applyWindow(series, win) {
  const yrs = (WINDOWS.find(([k]) => k === win) || WINDOWS[3])[1];
  if (yrs === Infinity) return { series, start: null };
  const [, hi] = timeExtent(series);
  const start = hi - yrs * YEAR;
  return {
    start,
    series: series.map((s) => {
      // Keep the last step before the window for step curves so the line starts at the edge.
      let rows = s.rows.filter((r) => r.x >= start);
      if (s.curve && String(s.curve).startsWith('step')) {
        const prev = s.rows.filter((r) => r.x < start).pop();
        if (prev) rows = [{ ...prev, x: start, x1: start }, ...rows];
      }
      return { ...s, rows };
    }),
  };
}

const lastValid = (rows) => { for (let i = rows.length - 1; i >= 0; i--) if (rows[i].value != null) return rows[i]; return null; };

// ------------------------------------------------------------------ sizing helpers
const measureCtx = document.createElement('canvas').getContext('2d');
function textWidth(t, font = `400 11px ${FONT_BODY}`) { measureCtx.font = font; return measureCtx.measureText(String(t)).width; }

function chartHeight(width, compact) {
  const h = Math.round(width * (compact ? 0.52 : 0.58));
  return Math.max(compact ? 200 : 220, Math.min(compact ? 300 : 380, h));
}

function niceYDomain(values, { includeZero = false, fixed = null, refs = [] } = {}) {
  if (fixed && fixed.length === 2 && fixed.every((v) => v != null)) return [+fixed[0], +fixed[1]];
  let lo = d3.min(values), hi = d3.max(values);
  if (lo == null) return [0, 1];
  for (const r of refs) {
    const span = hi - lo || Math.abs(hi) || 1;
    if (r >= lo - span * 0.25 && r <= hi + span * 0.25) { lo = Math.min(lo, r); hi = Math.max(hi, r); }
  }
  if (includeZero) { lo = Math.min(0, lo); hi = Math.max(0, hi); }
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.04;
  return d3.scaleLinear().domain([lo === 0 ? 0 : lo - pad, hi === 0 ? 0 : hi + pad]).nice(5).domain();
}

function tickDecimals(ticks) {
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1;
  return step >= 1 ? 0 : step >= 0.1 ? 1 : 2;
}

function timeTicks(d0, d1, innerWidth) {
  const years = (d1 - d0) / YEAR;
  const maxTicks = Math.max(2, Math.floor(innerWidth / 62));
  if (years > 2.2) {
    const step = [1, 2, 5, 10, 20].find((s) => years / s <= maxTicks) || 25;
    const ticks = d3.utcYear.every(step).range(new Date(d0), new Date(d1 + 1));
    return { ticks, format: d3.utcFormat('%Y') };
  }
  const months = years * 12;
  const step = [1, 2, 3, 6, 12].find((s) => months / s <= maxTicks) || 12;
  const ticks = d3.utcMonth.every(step).range(new Date(d0), new Date(d1 + 1));
  const fy = d3.utcFormat('%Y'), fm = d3.utcFormat('%b'), fmy = d3.utcFormat('%b %Y');
  return { ticks, format: (d, i) => (d.getUTCMonth() === 0 ? fy(d) : i === 0 ? fmy(d) : fm(d)) };
}

function baseStyle() {
  const c = colors();
  return { fontFamily: FONT_BODY, fontSize: '11px', color: c.slate, background: 'transparent', overflow: 'visible', fontVariantNumeric: 'tabular-nums' };
}

function el(tag, attrs = {}, text) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  return n;
}

// ------------------------------------------------------------------ labels and hover
function latestLabelValue(bundle, s, last) {
  const L = bundle.latest;
  if (L && L.values && L.period === last.period && L.values[s.key] != null) {
    return { v: L.values[s.key], flag: last.flag || L.flag || null };
  }
  return { v: last.value, flag: last.flag };
}

/** Place end labels with simple vertical dodging. items: {x, y, text, flag, color, dot}. */
function drawEndLabels(svg, items, top, bottom) {
  const gap = 14;
  items.sort((a, b) => a.y - b.y);
  for (let i = 0; i < items.length; i++) items[i].ly = Math.max(items[i].y, i ? items[i - 1].ly + gap : top);
  for (let i = items.length - 1; i >= 0; i--) {
    const max = i === items.length - 1 ? bottom : items[i + 1].ly - gap;
    if (items[i].ly > max) items[i].ly = max;
  }
  const g = el('g', { class: 'eet-end-labels' });
  for (const it of items) {
    if (it.dot) g.appendChild(el('circle', { cx: it.dotX ?? it.x, cy: it.y, r: 3.5, fill: it.dot, stroke: colors().paper, 'stroke-width': 1 }));
    const t = el('text', {
      x: it.x + 7, y: it.ly, dy: '0.35em', fill: it.color, 'text-anchor': 'start',
      'font-family': FONT_DISPLAY, 'font-weight': 700, 'font-size': 12, style: 'font-variant-numeric: tabular-nums',
    }, it.text);
    if (it.flag) {
      const f = el('tspan', { 'font-family': FONT_BODY, 'font-weight': 600, 'font-size': 10, fill: colors().slate, dx: 2 }, it.flag);
      t.appendChild(f);
    }
    g.appendChild(t);
  }
  svg.appendChild(g);
}

function tipHTML(title, entries) {
  return `<div class="tip-period">${esc(title)}</div><ul>${entries.map((e) => `
    <li><span class="tip-sw" style="background:${e.color}"></span><span class="tip-label">${esc(e.label)}</span>
    <span class="tip-val">${esc(e.value)}${e.flag ? `<span class="tip-flag"> ${esc(flagLabel(e.flag))}</span>` : ''}</span></li>`).join('')}</ul>`;
}

/**
 * Crosshair + tooltip for column-based charts. cols: [{px, title, entries, dots:[{py,color}]}]
 * sorted by px. Works with pointer, touch and arrow keys.
 */
function attachHover(host, svg, cols, { top, bottom, axis = 'x' }) {
  if (!cols.length) return;
  const c = colors();
  const g = el('g', { class: 'eet-hover', 'pointer-events': 'none', style: 'display:none' });
  const line = axis === 'x'
    ? el('line', { y1: top, y2: bottom, stroke: c.ink, 'stroke-opacity': 0.35, 'stroke-width': 1 })
    : null;
  if (line) g.appendChild(line);
  const dotsG = el('g');
  g.appendChild(dotsG);
  svg.appendChild(g);
  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  tip.hidden = true;
  host.appendChild(tip);
  const pxs = cols.map((d) => (axis === 'x' ? d.px : d.py));
  let cur = -1;

  function show(i) {
    if (i < 0 || i >= cols.length) return;
    cur = i;
    const d = cols[i];
    g.style.display = '';
    if (line) { line.setAttribute('x1', d.px); line.setAttribute('x2', d.px); }
    dotsG.replaceChildren(...(d.dots || []).filter((p) => p.py != null).map((p) => el('circle', { cx: p.px ?? d.px, cy: p.py, r: 4, fill: p.color, stroke: c.paper, 'stroke-width': 1.5 })));
    tip.innerHTML = tipHTML(d.title, d.entries);
    tip.hidden = false;
    const scale = svg.getBoundingClientRect().width / (+svg.getAttribute('width') || 1);
    const hostW = host.clientWidth;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    const ax = (d.px ?? 0) * scale, ay = (d.tipY ?? top) * scale;
    let left = ax + 14;
    if (left + tw > hostW) left = ax - tw - 14;
    if (left < 0) left = Math.max(0, Math.min(hostW - tw, ax - tw / 2));
    let topPx = axis === 'x' ? Math.max(0, top * scale) : Math.max(0, ay - th - 8);
    tip.style.left = `${left}px`;
    tip.style.top = `${topPx}px`;
  }
  function hide() { g.style.display = 'none'; tip.hidden = true; cur = -1; }
  function fromEvent(ev) {
    const r = svg.getBoundingClientRect();
    const scale = r.width / (+svg.getAttribute('width') || 1);
    const p = axis === 'x' ? (ev.clientX - r.left) / scale : (ev.clientY - r.top) / scale;
    return d3.bisectCenter(pxs, p);
  }
  svg.addEventListener('pointermove', (ev) => show(fromEvent(ev)));
  svg.addEventListener('pointerdown', (ev) => show(fromEvent(ev)));
  svg.addEventListener('pointerleave', (ev) => { if (ev.pointerType === 'mouse') hide(); });
  host.addEventListener('keydown', (ev) => {
    if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') { show(cur < 0 ? cols.length - 1 : Math.min(cols.length - 1, cur + 1)); ev.preventDefault(); }
    else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') { show(cur < 0 ? cols.length - 1 : Math.max(0, cur - 1)); ev.preventDefault(); }
    else if (ev.key === 'Home') { show(0); ev.preventDefault(); }
    else if (ev.key === 'End') { show(cols.length - 1); ev.preventDefault(); }
    else if (ev.key === 'Escape') hide();
  });
  host.addEventListener('blur', hide);
}

// ------------------------------------------------------------------ reference lines, markers
function refMarks(bundle, yDomain, xDomain, { horizontal = false } = {}) {
  const c = colors();
  const marks = [];
  for (const r of bundle.reference_lines || []) {
    const v = +r.value;
    if (!Number.isFinite(v)) continue;
    const axis = r.axis || 'y';
    if ((axis === 'y' && !horizontal) || (axis === 'x' && horizontal)) {
      const dom = horizontal ? xDomain : yDomain;
      if (v < dom[0] || v > dom[1]) continue;
      if (!horizontal) {
        marks.push(Plot.ruleY([v], { stroke: c.slate, strokeWidth: 1, strokeDasharray: '4,3' }));
        if (r.label) marks.push(Plot.text([v], { y: (d) => d, frameAnchor: 'left', textAnchor: 'start', dx: 4, dy: -7, text: () => r.label, fill: c.slate, fontSize: 10.5, fontWeight: 600, stroke: c.paper, strokeWidth: 3, paintOrder: 'stroke' }));
      } else {
        marks.push(Plot.ruleX([v], { stroke: c.slate, strokeWidth: 1, strokeDasharray: '4,3' }));
        if (r.label) marks.push(Plot.text([v], { x: (d) => d, frameAnchor: 'bottom', textAnchor: 'start', dx: 4, dy: -4, text: () => r.label, fill: c.slate, fontSize: 10.5, fontWeight: 600, stroke: c.paper, strokeWidth: 3, paintOrder: 'stroke' }));
      }
    } else if (axis === 'x' && !horizontal && xDomain) {
      const x = periodBounds(r.value) ? periodX(r.value) : v;
      if (x < xDomain[0] || x > xDomain[1]) continue;
      marks.push(Plot.ruleX([new Date(x)], { stroke: c.slate, strokeDasharray: '4,3' }));
    }
  }
  if (!horizontal && xDomain) {
    for (const m of bundle.markers || []) {
      const x = periodX(m.x);
      if (x == null || x < xDomain[0] || x > xDomain[1]) continue;
      marks.push(Plot.ruleX([new Date(x)], { stroke: c.ruleStrong, strokeWidth: 1 }));
      // Labels in the right half hang to the left of their line so they never leave the frame.
      const right = (x - xDomain[0]) / ((xDomain[1] - xDomain[0]) || 1) > 0.55;
      if (m.label) marks.push(Plot.text([new Date(x)], { x: (d) => d, frameAnchor: 'top', textAnchor: right ? 'end' : 'start', dx: right ? -4 : 4, dy: -2, lineAnchor: 'bottom', text: () => m.label, fill: c.slate, fontSize: 10.5, stroke: c.paper, strokeWidth: 3, paintOrder: 'stroke' }));
    }
  }
  return marks;
}

function periodX(p) {
  const b = periodBounds(p);
  if (!b) return null;
  return b.kind === 'D' ? b.start : (b.start + b.end) / 2;
}

// ------------------------------------------------------------------ time charts
/** Stack totals: dots on quarterly or annual contributions, a line on monthly or denser data. */
function totalAsDots(bundle) {
  const f = String(bundle.frequency || '').toUpperCase()[0];
  return bundle.type === 'contrib' && (f === 'Q' || f === 'A' || f === 'Y');
}

/**
 * line, bar, bar-line, stacked-bar, contrib (and each country-strip panel).
 * Returns {svg, width, height}.
 */
function drawTime(host, bundle, state, { width, height, compact = false, endLabels = true, yDomainOverride = null, panel = false }) {
  const c = colors();
  const type = bundle.type;
  const styled = styleSeries(prepTime(bundle.series || []));
  const { series, start } = applyWindow(styled, state.window);
  const dec = decimalsOf(bundle);
  const suffix = unitSuffix(bundle.units);

  // Which series are bars, lines, bands, stacks.
  let bars = [], lines = [], bands = series.filter((s) => s.role === 'band'), stack = [], total = null;
  const rest = series.filter((s) => s.role !== 'band');
  if (type === 'stacked-bar' || type === 'contrib') {
    total = rest.find((s) => s.key === bundle.total_key) || null;
    stack = rest.filter((s) => s !== total);
    if (total) total = { ...total, color: c.ink, text: c.ink, width: 1.75 };
  } else if (type === 'bar') {
    bars = rest.filter((s) => s.mark !== 'line');
    lines = rest.filter((s) => s.mark === 'line');
  } else if (type === 'bar-line') {
    const anyMark = rest.some((s) => s.mark);
    bars = anyMark ? rest.filter((s) => s.mark === 'bar') : rest.slice(0, 1);
    lines = rest.filter((s) => !bars.includes(s));
  } else {
    lines = rest;
  }

  // Bars as explicit rects (grouped when several bar series share a period).
  const rects = [];
  bars.forEach((s, i) => {
    for (const r of s.rows) {
      if (r.value == null) continue;
      const w = (r.x2 - r.x1) / bars.length;
      rects.push({ ...r, x1: r.x1 + w * i, x2: r.x1 + w * (i + 1), y1: 0, y2: r.value, color: s.color, label: s.label });
    }
  });
  // Stacks computed here, positives up and negatives down.
  const acc = new Map();
  for (const s of stack) {
    for (const r of s.rows) {
      if (r.value == null) continue;
      const a = acc.get(r.period) || { pos: 0, neg: 0 };
      let y1, y2;
      if (r.value >= 0) { y1 = a.pos; a.pos += r.value; y2 = a.pos; } else { y1 = a.neg; a.neg += r.value; y2 = a.neg; }
      acc.set(r.period, a);
      rects.push({ ...r, y1, y2, color: s.color, label: s.label });
    }
  }
  const lineLike = total ? [...lines, total] : lines;

  // Domains.
  const ys = [];
  for (const r of rects) ys.push(r.y1, r.y2);
  for (const s of lineLike) for (const r of s.rows) if (r.value != null) ys.push(r.value);
  for (const s of bands) for (const r of s.rows) { if (r.low != null) ys.push(r.low); if (r.high != null) ys.push(r.high); }
  const refs = (bundle.reference_lines || []).filter((r) => (r.axis || 'y') === 'y').map((r) => +r.value);
  const yDomain = niceYDomain(ys, { includeZero: rects.length > 0, fixed: yDomainOverride || bundle.y_domain, refs });
  const clip = !!(yDomainOverride || bundle.y_domain);

  let x0 = Infinity, x1 = -Infinity;
  for (const r of rects) { x0 = Math.min(x0, r.x1); x1 = Math.max(x1, r.x2); }
  for (const s of [...lineLike, ...bands]) for (const r of s.rows) { x0 = Math.min(x0, r.x); x1 = Math.max(x1, r.x); }
  if (start != null && rects.length === 0) x0 = Math.max(Math.min(x0, x1), start);
  if (!Number.isFinite(x0)) { x0 = Date.now() - YEAR; x1 = Date.now(); }
  if (x0 === x1) { x0 -= 15 * 864e5; x1 += 15 * 864e5; }

  // End labels: last valid point per line (and per bar series).
  const labelSeries = endLabels ? [...lineLike, ...bars] : [];
  const labelTexts = labelSeries.map((s) => {
    const last = lastValid(s.rows);
    if (!last) return null;
    const { v, flag } = latestLabelValue(bundle, s, last);
    return { s, last, text: fmtNum(v, dec) + suffix, flag };
  }).filter(Boolean);

  const yt = d3.scaleLinear().domain(yDomain).ticks(height < 200 ? 3 : height < 260 ? 4 : 5);
  const td = tickDecimals(yt);
  const yFmt = (d) => fmtNum(d, td);
  const marginLeft = Math.ceil(d3.max(yt, (t) => textWidth(yFmt(t))) || 10) + 10;
  const marginRight = labelTexts.length
    ? Math.ceil(d3.max(labelTexts, (l) => textWidth(l.text, `700 12px ${FONT_DISPLAY}`) + (l.flag ? 10 : 0))) + 14
    : 12;
  const hasMarkers = (bundle.markers || []).length > 0 && !panel;
  const marginTop = hasMarkers ? 20 : 10;
  const marginBottom = 22;
  const innerW = width - marginLeft - marginRight;
  const { ticks: xt, format: xFmt } = timeTicks(x0, x1, innerW);

  const barPx = rects.length ? innerW * d3.median(rects, (r) => r.x2 - r.x1) / (x1 - x0) : 0;
  const inset = barPx >= 4 ? Math.min(2, barPx * 0.14) : 0;

  const marks = [
    Plot.gridY(yt, { stroke: c.ruleSoft, strokeOpacity: 1 }),
    Plot.axisY(yt, { label: null, tickSize: 0, tickPadding: 6, tickFormat: yFmt, fill: c.slate }),
    Plot.axisX(xt, { label: null, tickSize: 3, tickPadding: 4, tickFormat: xFmt, stroke: c.ruleStrong, fill: c.slate }),
    ...bands.map((s) => Plot.areaY(s.rows, { x: (d) => new Date(d.x), y1: 'low', y2: 'high', fill: s.color, fillOpacity: 0.14, curve: s.curve || 'linear', clip })),
    Plot.ruleY([yDomain[0] <= 0 && yDomain[1] >= 0 ? 0 : yDomain[0]], { stroke: c.ruleStrong }),
    ...refMarks(bundle, yDomain, [x0, x1]),
  ];
  if (rects.length) {
    marks.push(Plot.rect(rects, {
      x1: (d) => new Date(d.x1), x2: (d) => new Date(d.x2), y1: 'y1', y2: 'y2', fill: (d) => d.color,
      insetLeft: inset, insetRight: inset, clip,
    }));
  }
  for (const s of lines) {
    marks.push(Plot.line(s.rows, { x: (d) => new Date(d.x), y: 'value', stroke: s.color, strokeWidth: s.width, curve: s.curve || 'linear', strokeLinejoin: 'round', strokeLinecap: 'round', clip }));
  }
  if (total) {
    if (totalAsDots(bundle)) {
      marks.push(Plot.dot(total.rows.filter((r) => r.value != null), { x: (d) => new Date(d.x), y: 'value', r: Math.min(4, barPx * 0.28), fill: c.ink, stroke: c.paper, strokeWidth: 1, clip }));
    } else {
      marks.push(Plot.line(total.rows, { x: (d) => new Date(d.x), y: 'value', stroke: c.ink, strokeWidth: 1.5, clip }));
    }
  }

  const svg = Plot.plot({
    width, height, marginLeft, marginRight, marginTop, marginBottom,
    style: baseStyle(),
    color: { type: 'identity' },
    x: { type: 'utc', domain: [new Date(x0), new Date(x1)], axis: null },
    y: { domain: yDomain, axis: null },
    marks,
  });
  svg.removeAttribute('viewBox');
  const xs = svg.scale('x'), ysc = svg.scale('y');
  const top = marginTop, bottom = height - marginBottom;
  const clampY = (v) => Math.max(top, Math.min(bottom, ysc.apply(v)));

  if (labelTexts.length) {
    drawEndLabels(svg, labelTexts.map((l) => {
      const isBar = bars.includes(l.s) || l.s === total;
      const dotX = xs.apply(new Date(l.last.x));
      // With bars on the chart, labels start at the right edge of the plot so they clear the last bar.
      const px = rects.length ? width - marginRight : dotX;
      return { x: px, dotX, y: clampY(l.last.value), text: l.text, flag: l.flag, color: l.s.text, dot: isBar ? null : l.s.color };
    }), top + 4, bottom - 4);
  }

  // Hover columns: one per period, across all series.
  const colMap = new Map();
  const add = (s, r, value, kind) => {
    if (!colMap.has(r.period)) colMap.set(r.period, { x: r.x, period: r.period, entries: [], dots: [] });
    const col = colMap.get(r.period);
    col.entries.push({ label: s.label || s.key, color: s.color, value, flag: r.flag });
    if (kind === 'line' && r.value != null) col.dots.push({ py: clampY(r.value), color: s.color });
  };
  for (const s of bands) for (const r of s.rows) add(s, r, r.low == null ? '–' : `${fmtNum(r.low, dec)} to ${fmtNum(r.high, dec)}${suffix}`, 'band');
  for (const s of bars) for (const r of s.rows) add(s, r, r.value == null ? '–' : fmtNum(r.value, dec) + suffix, 'bar');
  for (const s of stack) for (const r of s.rows) add(s, r, r.value == null ? '–' : fmtNum(r.value, dec) + suffix, 'bar');
  for (const s of lineLike) for (const r of s.rows) add(s, r, r.value == null ? '–' : fmtNum(r.value, dec) + suffix, 'line');
  // Step series (e.g. policy rates) have sparse points: carry them to every hover column.
  const cols = [...colMap.values()].sort((a, b) => a.x - b.x);
  for (const s of lineLike.filter((s) => s.curve && String(s.curve).startsWith('step'))) {
    let lastR = null, j = 0;
    const rows = s.rows;
    for (const col of cols) {
      while (j < rows.length && rows[j].x <= col.x) lastR = rows[j++];
      if (lastR && !col.entries.some((e) => e.label === (s.label || s.key))) {
        col.entries.push({ label: s.label || s.key, color: s.color, value: fmtNum(lastR.value, dec) + suffix, flag: null });
        col.dots.push({ py: clampY(lastR.value), color: s.color });
      }
    }
  }
  // Keep series order stable in the tooltip (as in the bundle).
  const order = new Map((bundle.series || []).map((s, i) => [s.label || s.key, i]));
  for (const col of cols) {
    col.entries.sort((a, b) => (order.get(a.label) ?? 0) - (order.get(b.label) ?? 0));
    col.px = xs.apply(new Date(col.x));
    col.title = periodLabel(col.period);
  }
  // Daily data: thin the hover columns to one per pixel to keep it light.
  host.appendChild(svg);
  attachHover(host, svg, cols, { top, bottom });
  return { svg, width, height };
}

// ------------------------------------------------------------------ categorical bars
function drawCategoryBars(host, bundle, state, { width }) {
  const c = colors();
  const dec = decimalsOf(bundle);
  const suffix = unitSuffix(bundle.units);
  const s0 = styleSeries(bundle.series || [])[0];
  if (!s0) return null;
  const hl = bundle.highlight || null;
  const rows = (s0.points || []).map(([label, v]) => ({
    label: String(label), value: num(v),
    color: (hl ? String(label) === hl : /^(euro area|ea\d*|eu\d*)$/i.test(String(label)))
      ? c.amber : s0.role === 'story' ? c.amber : c.green,
  }));
  const labelW = Math.ceil(d3.max(rows, (r) => textWidth(r.label, `500 12px ${FONT_BODY}`)) || 40);
  const marginLeft = Math.min(width * 0.42, labelW + 10);
  const valW = Math.ceil(d3.max(rows, (r) => textWidth(fmtNum(r.value, dec) + suffix, `700 12px ${FONT_DISPLAY}`)) || 20) + 10;
  const height = rows.length * 26 + 30;
  const xs = rows.map((r) => r.value).filter((v) => v != null);
  const refs = (bundle.reference_lines || []).filter((r) => r.axis === 'x').map((r) => +r.value);
  const xDomain = niceYDomain(xs, { includeZero: true, refs, fixed: bundle.y_domain });
  const xt = d3.scaleLinear().domain(xDomain).ticks(Math.max(2, Math.floor((width - marginLeft) / 80)));
  const td = tickDecimals(xt);
  const svg = Plot.plot({
    width, height, marginLeft, marginRight: valW, marginTop: 6, marginBottom: 22,
    style: baseStyle(), color: { type: 'identity' },
    x: { domain: xDomain, axis: null },
    y: { domain: rows.map((r) => r.label), padding: 0.3, axis: null },
    marks: [
      Plot.gridX(xt, { stroke: c.ruleSoft, strokeOpacity: 1 }),
      Plot.axisX(xt, { label: null, tickSize: 0, tickFormat: (d) => fmtNum(d, td), fill: c.slate }),
      Plot.axisY({ label: null, tickSize: 0, tickPadding: 8, fill: c.ink, fontSize: 12, textAnchor: 'end' }),
      Plot.barX(rows, { y: 'label', x: 'value', fill: (d) => d.color }),
      Plot.ruleX([0], { stroke: c.ruleStrong }),
      ...refMarks(bundle, null, xDomain, { horizontal: true }),
      Plot.text(rows, { y: 'label', x: 'value', text: (d) => fmtNum(d.value, dec) + suffix, dx: 5, textAnchor: 'start', fill: (d) => (d.color === c.amber ? c.ink : c.green), fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 12 }),
    ],
  });
  svg.removeAttribute('viewBox');
  host.appendChild(svg);
  const ysc = svg.scale('y');
  const bw = ysc.bandwidth || 18;
  const cols = rows.map((r) => ({
    py: ysc.apply(r.label) + bw / 2, px: marginLeft, tipY: ysc.apply(r.label),
    title: r.label, entries: [{ label: s0.label || bundle.subtitle || '', color: r.color, value: fmtNum(r.value, dec) + suffix }],
  }));
  attachHover(host, svg, cols, { top: 6, bottom: height - 22, axis: 'y' });
  return { svg, width, height };
}

// ------------------------------------------------------------------ scatter (Beveridge curve)
function drawScatter(host, bundle, state, { width, compact }) {
  const c = colors();
  const dec = decimalsOf(bundle);
  const styled = styleSeries(bundle.series || []).map((s) => ({
    ...s,
    rows: (s.points || []).map((p) => ({ period: p[0], x: periodX(p[0]), xv: num(p[1]), yv: num(p[2]) }))
      .filter((r) => r.xv != null && r.yv != null),
  }));
  const { series } = applyWindow(styled, state.window);
  const all = series.flatMap((s) => s.rows.map((r) => ({ ...r, s })));
  if (!all.length) return null;
  const height = chartHeight(width, compact) + 10;
  const pad = (lo, hi) => { const p = (hi - lo) * 0.08 || 0.5; return [lo - p, hi + p]; };
  const xD = d3.scaleLinear().domain(pad(d3.min(all, (d) => d.xv), d3.max(all, (d) => d.xv))).nice(5).domain();
  const yD = d3.scaleLinear().domain(pad(d3.min(all, (d) => d.yv), d3.max(all, (d) => d.yv))).nice(5).domain();
  const xt = d3.scaleLinear().domain(xD).ticks(Math.max(3, Math.floor(width / 90)));
  const yt = d3.scaleLinear().domain(yD).ticks(5);
  const yFmt = (d) => fmtNum(d, tickDecimals(yt));
  const marginLeft = Math.ceil(d3.max(yt, (t) => textWidth(yFmt(t)))) + 10;
  const end = all.reduce((a, b) => (b.x > a.x ? b : a));
  const first = all.reduce((a, b) => (b.x < a.x ? b : a));
  const endLabel = periodLabel(end.period);
  const marginRight = Math.ceil(textWidth(endLabel, `700 12px ${FONT_DISPLAY}`)) + 18;
  const marks = [
    Plot.gridY(yt, { stroke: c.ruleSoft, strokeOpacity: 1 }),
    Plot.gridX(xt, { stroke: c.ruleSoft, strokeOpacity: 1 }),
    Plot.axisY(yt, { label: null, tickSize: 0, tickPadding: 6, tickFormat: yFmt, fill: c.slate }),
    Plot.axisX(xt, { label: null, tickSize: 3, tickFormat: (d) => fmtNum(d, tickDecimals(xt)), stroke: c.ruleStrong, fill: c.slate }),
    Plot.frame({ anchor: 'bottom', stroke: c.ruleStrong }),
  ];
  for (const s of series) {
    marks.push(Plot.line(s.rows, { x: 'xv', y: 'yv', stroke: s.color, strokeWidth: s.role === 'story' ? 2 : 1.5, strokeOpacity: 0.9, curve: 'linear' }));
    marks.push(Plot.dot(s.rows, { x: 'xv', y: 'yv', r: 2.6, fill: s.color }));
  }
  const endColor = end.s.color;
  marks.push(Plot.dot([end], { x: 'xv', y: 'yv', r: 6, fill: endColor, stroke: c.paper, strokeWidth: 1.5 }));
  marks.push(Plot.text([end], { x: 'xv', y: 'yv', text: () => endLabel, dx: 10, textAnchor: 'start', fill: c.ink, fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 12, stroke: c.paper, strokeWidth: 3, paintOrder: 'stroke' }));
  marks.push(Plot.text([first], { x: 'xv', y: 'yv', text: () => periodLabel(first.period), dy: -10, textAnchor: 'middle', fill: c.slate, fontSize: 10.5, stroke: c.paper, strokeWidth: 3, paintOrder: 'stroke' }));
  if (bundle.y_label) marks.push(Plot.text([bundle.y_label], { frameAnchor: 'top-left', dy: -16, dx: -marginLeft + 2, textAnchor: 'start', fill: c.slate, fontSize: 11, fontWeight: 600 }));
  if (bundle.x_label) marks.push(Plot.text([bundle.x_label], { frameAnchor: 'bottom-right', dy: 34, textAnchor: 'end', fill: c.slate, fontSize: 11, fontWeight: 600 }));
  const svg = Plot.plot({
    width, height, marginLeft, marginRight, marginTop: 24, marginBottom: 42,
    style: baseStyle(), color: { type: 'identity' },
    x: { domain: xD, axis: null }, y: { domain: yD, axis: null }, marks,
  });
  svg.removeAttribute('viewBox');
  host.appendChild(svg);
  const xs = svg.scale('x'), ys = svg.scale('y');
  // 2-D nearest point: sort by px and let the crosshair follow x; dots mark the point.
  const pts = all.map((d) => ({
    px: xs.apply(d.xv), py: ys.apply(d.yv), tipY: ys.apply(d.yv), title: periodLabel(d.period),
    entries: [
      { label: bundle.x_label || 'x', color: d.s.color, value: fmtNum(d.xv, dec) + unitSuffix(bundle.units) },
      { label: bundle.y_label || 'y', color: d.s.color, value: fmtNum(d.yv, dec) + unitSuffix(bundle.units) },
    ],
  }));
  attachNearest(host, svg, pts);
  return { svg, width, height };
}

/** Nearest-point hover for scatter charts. */
function attachNearest(host, svg, pts) {
  const c = colors();
  const ring = el('circle', { r: 7, fill: 'none', stroke: c.ink, 'stroke-width': 1.5, 'pointer-events': 'none', style: 'display:none' });
  svg.appendChild(ring);
  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  tip.hidden = true;
  host.appendChild(tip);
  const order = pts.map((p, i) => i);
  let cur = -1;
  function show(i) {
    if (i < 0) return;
    cur = i;
    const p = pts[i];
    ring.setAttribute('cx', p.px); ring.setAttribute('cy', p.py); ring.style.display = '';
    tip.innerHTML = tipHTML(p.title, p.entries);
    tip.hidden = false;
    const scale = svg.getBoundingClientRect().width / (+svg.getAttribute('width') || 1);
    let left = p.px * scale + 14;
    if (left + tip.offsetWidth > host.clientWidth) left = p.px * scale - tip.offsetWidth - 14;
    tip.style.left = `${Math.max(0, left)}px`;
    tip.style.top = `${Math.max(0, p.py * scale - tip.offsetHeight / 2)}px`;
  }
  function hide() { ring.style.display = 'none'; tip.hidden = true; }
  const near = (ev) => {
    const r = svg.getBoundingClientRect();
    const scale = r.width / (+svg.getAttribute('width') || 1);
    const x = (ev.clientX - r.left) / scale, y = (ev.clientY - r.top) / scale;
    let best = -1, bd = 40 * 40;
    pts.forEach((p, i) => { const d = (p.px - x) ** 2 + (p.py - y) ** 2; if (d < bd) { bd = d; best = i; } });
    return best;
  };
  svg.addEventListener('pointermove', (ev) => { const i = near(ev); if (i < 0) hide(); else show(i); });
  svg.addEventListener('pointerleave', (ev) => { if (ev.pointerType === 'mouse') hide(); });
  host.addEventListener('keydown', (ev) => {
    if (['ArrowRight', 'ArrowDown'].includes(ev.key)) { show(cur < 0 ? pts.length - 1 : Math.min(pts.length - 1, cur + 1)); ev.preventDefault(); }
    else if (['ArrowLeft', 'ArrowUp'].includes(ev.key)) { show(cur < 0 ? pts.length - 1 : Math.max(0, cur - 1)); ev.preventDefault(); }
    else if (ev.key === 'Escape') hide();
  });
  host.addEventListener('blur', hide);
  void order;
}

// ------------------------------------------------------------------ heatmap
export function heatColor(bundle, values) {
  const c = colors();
  const lo = d3.min(values), hi = d3.max(values);
  if (bundle.scale === 'diverging') {
    const mid = bundle.midpoint != null ? +bundle.midpoint : 0;
    const ext = Math.max(Math.abs(lo - mid), Math.abs(hi - mid)) || 1;
    const neg = d3.interpolateRgb(c.paper, c.green), pos = d3.interpolateRgb(c.paper, c.amber);
    return { fn: (v) => (v == null ? c.card : v < mid ? neg(Math.min(1, (mid - v) / ext)) : pos(Math.min(1, (v - mid) / ext))), lo: mid - ext, hi: mid + ext, mid };
  }
  const seq = d3.piecewise(d3.interpolateRgb, [c.paper, c.green, c.deep]);
  return { fn: (v) => (v == null ? c.card : seq((v - lo) / ((hi - lo) || 1))), lo, hi, mid: null };
}

function textOn(bg) {
  const { r, g, b } = d3.rgb(bg);
  const L = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return L < 0.5 ? '#FFFFFF' : colors().ink;
}

function drawHeatmap(host, bundle, state, { width }) {
  const c = colors();
  const dec = decimalsOf(bundle);
  const rows = bundle.rows || [], cols = bundle.columns || [];
  const cells = (bundle.cells || []).map(([ri, ci, v]) => ({ ri, ci, v: num(v) }));
  const { fn } = heatColor(bundle, cells.map((d) => d.v).filter((v) => v != null));
  const labelW = Math.ceil(d3.max(rows, (r) => textWidth(r, `500 12px ${FONT_BODY}`)) || 40) + 10;
  const marginLeft = Math.min(width * 0.4, labelW);
  const innerW = width - marginLeft - 4;
  const cw = innerW / Math.max(1, cols.length);
  const ch = 24;
  const colLabels = cols.map((p) => (isPeriod(p) ? periodShort(p) : String(p)));
  const maxColLabel = d3.max(colLabels, (l) => textWidth(l)) || 20;
  const every = Math.max(1, Math.ceil((maxColLabel + 8) / cw));
  const height = rows.length * ch + 30;
  const svg = Plot.plot({
    width, height, marginLeft, marginRight: 4, marginTop: 26, marginBottom: 4,
    style: baseStyle(), color: { type: 'identity' },
    x: { domain: d3.range(cols.length), axis: null, padding: 0 },
    y: { domain: d3.range(rows.length), axis: null, padding: 0 },
    marks: [
      Plot.axisX({ label: null, anchor: 'top', tickSize: 0, tickPadding: 6, tickFormat: (i) => ((cols.length - 1 - i) % every === 0 ? colLabels[i] : ''), fill: c.slate }),
      Plot.axisY({ label: null, tickSize: 0, tickPadding: 8, tickFormat: (i) => rows[i], fill: c.ink, fontSize: 12 }),
      Plot.cell(cells, { x: 'ci', y: 'ri', fill: (d) => fn(d.v), inset: 0.5 }),
      ...(cw >= 30 ? [Plot.text(cells, { x: 'ci', y: 'ri', text: (d) => (d.v == null ? '' : fmtNum(d.v, dec)), fill: (d) => textOn(fn(d.v)), fontSize: 10.5 })] : []),
    ],
  });
  svg.removeAttribute('viewBox');
  host.appendChild(svg);
  const xs = svg.scale('x'), ys = svg.scale('y');
  const bw = xs.bandwidth, bh = ys.bandwidth;
  // Hover: nearest cell.
  const pts = cells.map((d) => ({
    px: xs.apply(d.ci) + bw / 2, py: ys.apply(d.ri) + bh / 2,
    title: `${rows[d.ri]}, ${isPeriod(cols[d.ci]) ? periodLabel(cols[d.ci]) : cols[d.ci]}`,
    entries: [{ label: bundle.subtitle ? bundle.subtitle.split(',')[0] : 'Value', color: fn(d.v), value: d.v == null ? '–' : fmtValue(d.v, bundle) }],
  }));
  attachNearest(host, svg, pts);
  return { svg, width, height };
}

// ------------------------------------------------------------------ country strip
function drawCountryStrip(host, bundle, state, { width, compact }) {
  const styled = styleSeries(prepTime(bundle.series || []));
  const { series } = applyWindow(styled, state.window);
  const ys = series.flatMap((s) => s.rows.map((r) => r.value)).filter((v) => v != null);
  const refs = (bundle.reference_lines || []).filter((r) => (r.axis || 'y') === 'y').map((r) => +r.value);
  const shared = niceYDomain(ys, { fixed: bundle.y_domain, refs });
  const n = series.length;
  const colsN = width >= 900 ? Math.min(4, n) : width >= 520 ? Math.min(3, n) : Math.min(2, n);
  const gap = 18;
  const pw = Math.floor((width - gap * (colsN - 1)) / colsN);
  const ph = compact ? 130 : Math.max(130, Math.min(170, Math.round(pw * 0.62)));
  const grid = document.createElement('div');
  grid.className = 'cs-grid';
  grid.style.gridTemplateColumns = `repeat(${colsN}, minmax(0, 1fr))`;
  grid.style.columnGap = `${gap}px`;
  host.appendChild(grid);
  const dec = decimalsOf(bundle);
  const parts = [];
  styled.forEach((s, i) => {
    const panel = document.createElement('div');
    panel.className = 'cs-panel' + (s.role === 'story' ? ' is-story' : '');
    const last = lastValid(s.rows);
    const lv = last ? latestLabelValue(bundle, s, last) : null;
    panel.innerHTML = `<div class="cs-head"><span class="cs-name">${esc(s.label || s.key)}</span>${lv ? `<span class="cs-val" style="color:${s.text}">${esc(fmtNum(lv.v, dec) + unitSuffix(bundle.units))}${lv.flag ? `<sup class="flag" title="${esc(flagLabel(lv.flag))}">${esc(lv.flag)}</sup>` : ''}</span>` : ''}</div><div class="cs-plot" tabindex="0" role="img" aria-label="${esc(`${s.label}: ${lv ? fmtNum(lv.v, dec) + unitSuffix(bundle.units) : 'no data'}`)}"></div>`;
    grid.appendChild(panel);
    const plotHost = panel.querySelector('.cs-plot');
    const sub = { ...bundle, type: 'line', series: [{ ...bundle.series[i], role: s.role === 'story' ? 'story' : 'base' }], markers: [] };
    const r = drawTime(plotHost, sub, state, { width: pw, height: ph, compact: true, endLabels: false, yDomainOverride: shared, panel: true });
    parts.push({ svg: r.svg, label: s.label || s.key, value: lv ? fmtNum(lv.v, dec) + unitSuffix(bundle.units) : '', color: s.text, col: i % colsN, row: Math.floor(i / colsN) });
  });
  return { multi: { parts, pw, ph, gap, colsN }, width, height: Math.ceil(n / colsN) * (ph + 28) };
}

// ------------------------------------------------------------------ table
// Column formats: text, level, pct, index, eur_bn (plain numbers); pp, change (signed changes).
function fmtCell(v, col, bundle, row) {
  if (v == null || v === '') return '–';
  const f = col.format || (typeof v === 'number' ? 'level' : 'text');
  if (f === 'text' || typeof v !== 'number') return String(v);
  const d = Number.isInteger(col.decimals) ? col.decimals
    : row && Number.isInteger(row.decimals) ? row.decimals
      : f === 'eur_bn' ? 0 : decimalsOf(bundle);
  if (f === 'pp' || f === 'change' || f === 'pp_change') return fmtChange(v, d);
  return fmtNum(v, d);
}

export function tableModel(bundle) {
  const cols = bundle.columns || [];
  return {
    head: ['', ...cols.map((c) => c.label || c.key)],
    rows: (bundle.rows || []).map((r) => ({
      label: r.label, flag: r.flag || null,
      cells: cols.map((c) => fmtCell(r.values ? r.values[c.key] : null, c, bundle, r)),
      numeric: cols.map((c) => (c.format || '') !== 'text'),
    })),
    numeric: cols.map((c) => (c.format || '') !== 'text'),
  };
}

function drawTable(host, bundle) {
  const m = tableModel(bundle);
  host.innerHTML = `<div class="table-wrap" tabindex="0"><table class="booktabs">
    <caption class="sr-only">${esc(bundle.title)}</caption>
    <thead><tr><th scope="col"><span class="sr-only">Measure</span></th>${m.head.slice(1).map((h, i) => `<th scope="col" class="${m.numeric[i] ? 'num' : 'txt'}">${esc(h)}</th>`).join('')}</tr></thead>
    <tbody>${m.rows.map((r) => `<tr><th scope="row">${esc(r.label)}${r.flag ? ` <sup class="flag" title="${esc(flagLabel(r.flag))}">${esc(r.flag)}</sup>` : ''}</th>${r.cells.map((c, i) => `<td class="${m.numeric[i] ? 'num' : 'txt'}">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody>
  </table></div>`;
  return { table: true };
}

// ------------------------------------------------------------------ text alternative
export function describe(b) {
  const labelOf = (k) => {
    if (b.type === 'scatter') return k === 'x' ? (b.x_label || 'x') : k === 'y' ? (b.y_label || 'y') : k;
    const s = (b.series || []).find((x) => x.key === k);
    return s ? s.label : k === 'EA21' ? 'Euro area' : k;
  };
  const out = [`${b.title}.`];
  if (b.subtitle) out.push(`${b.subtitle}.`);
  const vals = (o) => Object.entries(o.values || {}).filter(([, v]) => v != null).map(([k, v]) => `${labelOf(k)} ${fmtValue(v, b)}`).join('; ');
  if (b.latest && b.latest.values && Object.keys(b.latest.values).length) {
    out.push(`Latest, ${periodLabel(b.latest.period)}${b.latest.flag ? ` (${flagLabel(b.latest.flag)})` : ''}: ${vals(b.latest)}.`);
  }
  if (b.previous && b.previous.values && Object.keys(b.previous.values).length) {
    out.push(`Previous, ${periodLabel(b.previous.period)}: ${vals(b.previous)}.`);
  }
  if (b.type === 'heatmap' && b.rows && b.columns) {
    const lastCol = b.columns.length - 1;
    const lastCells = (b.cells || []).filter((c) => c[1] === lastCol && c[2] != null).sort((a, z) => z[2] - a[2]);
    out.push(`Grid of ${b.rows.length} rows by ${b.columns.length} columns, ${periodLabel(b.columns[0])} to ${periodLabel(b.columns[lastCol])}.`);
    if (lastCells.length > 1) {
      const hi = lastCells[0], lo = lastCells[lastCells.length - 1];
      out.push(`In ${periodLabel(b.columns[lastCol])} the highest is ${b.rows[hi[0]]} at ${fmtValue(hi[2], b)} and the lowest ${b.rows[lo[0]]} at ${fmtValue(lo[2], b)}.`);
    }
  }
  if (b.type === 'bar' && (b.series || [])[0] && !isPeriod(((b.series[0].points || [])[0] || [])[0])) {
    const pts = b.series[0].points;
    out.push(pts.map(([l, v]) => `${l} ${fmtValue(v, b)}`).join('; ') + '.');
  }
  if (b.source) out.push(`Source: ${b.source}.`);
  return out.join(' ');
}

// ------------------------------------------------------------------ figure furniture
function legendItems(bundle) {
  const t = bundle.type;
  if (['table', 'country-strip', 'heatmap'].includes(t)) return [];
  if (t === 'bar' && !isPeriod(((bundle.series?.[0]?.points || [])[0] || [])[0])) return [];
  const styled = styleSeries(bundle.series || []);
  if (styled.length < 2) return [];
  const c = colors();
  return styled.map((s) => {
    const isTotal = s.key === bundle.total_key;
    let shape = 'line';
    if (s.role === 'band') shape = 'band';
    else if ((t === 'stacked-bar' || t === 'contrib') && !isTotal) shape = 'bar';
    else if (t === 'bar' && s.mark !== 'line') shape = 'bar';
    else if (t === 'bar-line' && (s.mark === 'bar' || (!bundle.series.some((x) => x.mark) && s === styled[0]))) shape = 'bar';
    else if ((t === 'contrib' || t === 'stacked-bar') && isTotal) shape = totalAsDots(bundle) ? 'dot' : 'line';
    return { label: s.label || s.key, color: isTotal ? c.ink : s.color, shape };
  });
}

function heatLegend(bundle) {
  const vals = (bundle.cells || []).map((d) => num(d[2])).filter((v) => v != null);
  if (!vals.length) return '';
  const h = heatColor(bundle, vals);
  const steps = 7;
  const sw = d3.range(steps).map((i) => h.fn(h.lo + (h.hi - h.lo) * (i / (steps - 1))));
  const dec = decimalsOf(bundle);
  const mid = h.mid != null ? `<span class="hl-mid">${esc(fmtValue(h.mid, bundle))}</span>` : '';
  return `<div class="heat-legend" aria-hidden="true"><span>${esc(fmtNum(h.lo, dec))}</span><span class="hl-sw">${sw.map((col) => `<i style="background:${col}"></i>`).join('')}</span><span>${esc(fmtNum(h.hi, dec))}</span>${mid ? `<span class="hl-note">centred on ${mid}</span>` : ''}</div>`;
}

function flagsUsed(bundle) {
  const set = new Set();
  for (const s of bundle.series || []) for (const f of Object.values(s.flags || {})) if (f) set.add(f);
  if (bundle.latest && bundle.latest.flag) set.add(bundle.latest.flag);
  for (const r of bundle.rows || []) if (r && r.flag) set.add(r.flag);
  return [...set].filter((f) => FLAG_LABELS[f] || f);
}

function isTimeType(b) {
  if (b.type === 'bar') return isPeriod(((b.series?.[0]?.points || [])[0] || [])[0]);
  return ['line', 'bar-line', 'stacked-bar', 'contrib', 'country-strip', 'scatter'].includes(b.type);
}

/** Skeleton shown while a bundle is loading. */
export function skeletonFigure(fig, { compact = false } = {}) {
  fig.classList.add('chart', 'is-loading');
  fig.innerHTML = `<div class="skel skel-kicker"></div><div class="skel skel-title"></div><div class="skel skel-sub"></div><div class="skel skel-plot" style="height:${compact ? 220 : 280}px"></div><div class="skel skel-source"></div>`;
}

export function unavailableFigure(fig, id, err) {
  fig.classList.remove('is-loading');
  fig.classList.add('chart', 'is-missing');
  fig.innerHTML = `<p class="chart-missing">This chart is not available right now.</p>`;
  fig.title = `${id}: ${err && err.message ? err.message : 'missing'}`;
}

/**
 * Render a chart bundle into a <figure>. opts: {compact, failed: {error}|null, pageHref}
 */
export function renderChart(fig, bundle, opts = {}) {
  const { compact = false, failed = null } = opts;
  if (!TYPES.includes(bundle.type)) {
    unavailableFigure(fig, bundle.id, new Error(`unknown chart type "${bundle.type}"`));
    return;
  }
  fig.classList.remove('is-loading');
  fig.classList.add('chart', `chart--${bundle.type}`);
  if (['heatmap', 'country-strip'].includes(bundle.type) && !compact) fig.classList.add('chart--wide');
  fig.id = bundle.id;
  fig.dataset.type = bundle.type;

  const state = { window: bundle.default_window || 'max' };
  const time = isTimeType(bundle);
  let wins = [];
  if (time) {
    const prepped = bundle.type === 'scatter'
      ? [{ rows: (bundle.series || []).flatMap((s) => (s.points || []).map((p) => ({ x: periodX(p[0]) })).filter((r) => r.x != null)) }]
      : prepTime(bundle.series || []);
    wins = windowOptions(prepped);
    if (!wins.includes(state.window)) state.window = 'max';
    if (wins.length < 2) wins = [];
  }

  const legend = legendItems(bundle);
  const flags = flagsUsed(bundle);
  const altId = `${bundle.id}-alt`;
  const updated = bundle.data_updated ? ` · Updated ${fmtDay(bundle.data_updated)}` : '';
  const methodsLink = bundle.methods_id ? href('methods', bundle.methods_id) : href('methods');
  const tags = [
    bundle.original ? `<a class="tag-original" href="${methodsLink}" title="Computed by the tracker itself. See how in Methods">Original</a>` : '',
    failed ? `<span class="tag-stale" title="${esc(failed.error || 'Not updated on the latest run')}">Not updated</span>` : '',
  ].join('');

  fig.innerHTML = `
    <div class="chart-head">
      <div class="chart-meta">${bundle.kicker ? `<span class="kicker">${esc(bundle.kicker)}</span>` : ''}${tags}</div>
      <h3 class="chart-title">${esc(bundle.title)}</h3>
      ${bundle.subtitle ? `<p class="chart-sub">${esc(bundle.subtitle)}</p>` : ''}
    </div>
    ${legend.length || wins.length || bundle.type === 'heatmap' ? `<div class="chart-controls">
      ${legend.length ? `<ul class="legend">${legend.map((l) => `<li><span class="sw sw-${l.shape}" style="--sw:${l.color}"></span>${esc(l.label)}</li>`).join('')}</ul>` : bundle.type === 'heatmap' ? heatLegend(bundle) : '<span></span>'}
      ${wins.length ? `<div class="windows" role="group" aria-label="Time window">${wins.map((w) => `<button type="button" data-win="${w}" aria-pressed="${w === state.window}">${w === 'max' ? 'Max' : w}</button>`).join('')}</div>` : ''}
    </div>` : ''}
    <div class="chart-plot" ${bundle.type === 'table' ? '' : `role="img" tabindex="0" aria-label="${esc(bundle.title)}" aria-describedby="${altId}"`}></div>
    <p class="sr-only" id="${altId}">${esc(describe(bundle))}</p>
    <figcaption class="chart-foot">
      <p class="chart-source">Source: ${bundle.source_url ? `<a href="${esc(bundle.source_url)}" rel="noopener">${esc(bundle.source || 'see link')}</a>` : esc(bundle.source || 'not stated')}${esc(updated)}</p>
      ${bundle.notes || flags.length ? `<p class="chart-note">${bundle.notes ? esc(bundle.notes) : ''}${flags.length ? `${bundle.notes ? ' ' : ''}<span class="flag-key">${flags.map((f) => `<b>${esc(f)}</b> ${esc(flagLabel(f))}`).join(' · ')}</span>` : ''}</p>` : ''}
      ${compact ? '' : `<div class="chart-actions"><button type="button" data-act="png">Download PNG</button><button type="button" data-act="link">Copy link</button></div>`}
    </figcaption>`;

  const host = fig.querySelector('.chart-plot');
  let last = null;
  let lastW = 0;

  function draw() {
    const w = Math.floor(host.clientWidth);
    if (!w) return;
    lastW = w;
    host.querySelectorAll('svg, .chart-tip, .cs-grid, .table-wrap').forEach((n) => n.remove());
    const o = { width: w, height: chartHeight(w, compact), compact };
    try {
      switch (bundle.type) {
        case 'line': case 'bar-line': case 'stacked-bar': case 'contrib':
          last = drawTime(host, bundle, state, o); break;
        case 'bar':
          last = time ? drawTime(host, bundle, state, o) : drawCategoryBars(host, bundle, state, o); break;
        case 'scatter': last = drawScatter(host, bundle, state, o); break;
        case 'heatmap': last = drawHeatmap(host, bundle, state, o); break;
        case 'country-strip': last = drawCountryStrip(host, bundle, state, o); break;
        case 'table': last = drawTable(host, bundle); break;
        default: break;
      }
    } catch (e) {
      console.error(`[eet] could not draw ${bundle.id}`, e);
      host.innerHTML = '<p class="chart-missing">This chart could not be drawn.</p>';
    }
  }

  draw();
  if (bundle.type !== 'table') {
    let raf = 0;
    new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => { if (Math.abs(host.clientWidth - lastW) > 1) draw(); });
    }).observe(host);
  }

  fig.querySelectorAll('.windows button').forEach((b) => b.addEventListener('click', () => {
    state.window = b.dataset.win;
    fig.querySelectorAll('.windows button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    draw();
  }));

  const pngBtn = fig.querySelector('[data-act="png"]');
  if (pngBtn) pngBtn.addEventListener('click', async () => {
    const label = pngBtn.textContent;
    pngBtn.disabled = true;
    pngBtn.textContent = 'Preparing…';
    try { await exportPNG(bundle, last, { legend, pageUrl: location.href.split('#')[0] }); }
    catch (e) { console.error('[eet] PNG export failed', e); pngBtn.textContent = 'Export failed'; await new Promise((r) => setTimeout(r, 1500)); }
    pngBtn.textContent = label;
    pngBtn.disabled = false;
  });
  const linkBtn = fig.querySelector('[data-act="link"]');
  if (linkBtn) linkBtn.addEventListener('click', async () => {
    const url = new URL(location.href);
    url.hash = bundle.id;
    url.searchParams.delete('fixtures');
    const text = url.toString();
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { ok = document.execCommand('copy'); } catch { ok = false; }
      ta.remove();
    }
    history.replaceState(null, '', `#${bundle.id}`);
    linkBtn.textContent = ok ? 'Link copied' : 'Copy failed';
    setTimeout(() => { linkBtn.textContent = 'Copy link'; }, 1600);
  });

  // Exposed for testing the PNG pipeline without saving a file.
  fig.__eet = { bundle, state, get layout() { return last; }, exportPNG: (o) => exportPNG(bundle, last, { legend, pageUrl: location.href.split('#')[0], ...o }) };
}
