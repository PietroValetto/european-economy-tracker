// PNG export: compose kicker, title, amber rule, subtitle, legend, the chart SVG(s), source
// line and the Popular Economics mark into one SVG, embed the brand fonts, rasterise at 2x.

import { esc, flagLabel } from './format.js';

const SVGNS = 'http://www.w3.org/2000/svg';
const FONT_CSS = 'https://fonts.googleapis.com/css2?family=Archivo:wght@700;800&family=Inter:wght@400;500;600;700&display=swap';
const BODY = "Inter, 'Helvetica Neue', Arial, sans-serif";
const DISPLAY = "Archivo, 'Helvetica Neue', Arial, sans-serif";
const C = { ink: '#1B1712', slate: '#6B655C', mute: '#A8A296', green: '#1F8A5B', amber: '#F0A93B', paper: '#FAF7F0', rule: 'rgba(27,23,18,.12)', ruleStrong: 'rgba(27,23,18,.22)' };

let fontsPromise;
function b64(buf) {
  const bytes = new Uint8Array(buf);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
/** @font-face rules with the latin woff2 files inlined, so the PNG uses the real faces. */
function embeddedFonts() {
  if (!fontsPromise) {
    fontsPromise = (async () => {
      try {
        const css = await (await fetch(FONT_CSS)).text();
        const files = new Map();
        const rules = [];
        for (const block of css.split('/* ').filter((b) => b.startsWith('latin */'))) {
          const m = /@font-face\s*{([^}]*)}/.exec(block);
          const u = m && /url\(([^)]+)\)/.exec(m[1]);
          if (!u) continue;
          if (!files.has(u[1])) files.set(u[1], fetch(u[1]).then((r) => r.arrayBuffer()).then(b64));
          rules.push({ body: m[1], url: u[0], src: u[1] });
        }
        const out = [];
        for (const r of rules) out.push(`@font-face{${r.body.replace(r.url, `url(data:font/woff2;base64,${await files.get(r.src)})`)}}`);
        return out.join('\n');
      } catch (e) {
        console.warn('[eet] could not embed fonts in PNG; falling back to system faces', e);
        return '';
      }
    })();
  }
  return fontsPromise;
}

const ctx = document.createElement('canvas').getContext('2d');
function wrap(text, font, maxW) {
  ctx.font = font;
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const w of words) {
    const t = line ? `${line} ${w}` : w;
    if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t;
  }
  if (line) lines.push(line);
  return lines;
}
const tw = (t, font) => { ctx.font = font; return ctx.measureText(t).width; };

function node(tag, attrs = {}, text) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  return n;
}

function markSVG(x, y, size) {
  const g = node('svg', { x, y, width: size, height: size, viewBox: '0 0 100 100' });
  g.innerHTML = '<g transform="translate(50,50) scale(0.75) translate(-50,-45)"><rect x="16" y="56" width="16" height="30" rx="8" fill="#1F8A5B"/><circle cx="24" cy="44" r="8" fill="#1F8A5B"/><rect x="42" y="40" width="16" height="46" rx="8" fill="#F0A93B"/><circle cx="50" cy="28" r="8" fill="#F0A93B"/><rect x="68" y="24" width="16" height="62" rx="8" fill="#1F8A5B"/><circle cx="76" cy="12" r="8" fill="#1F8A5B"/></g>';
  return g;
}

function cloneChart(svg, x, y) {
  const c = svg.cloneNode(true);
  c.querySelectorAll('.eet-hover').forEach((n) => n.remove());
  c.querySelectorAll('circle[fill="none"]').forEach((n) => n.remove());
  c.setAttribute('x', x);
  c.setAttribute('y', y);
  c.removeAttribute('style');
  c.setAttribute('font-family', BODY);
  c.setAttribute('font-size', '11');
  c.setAttribute('fill', C.slate);
  c.setAttribute('overflow', 'visible');
  c.style.color = C.slate;
  return c;
}

/** Draw a booktabs table as SVG text for the PNG. */
function tableSVG(bundle, model, width) {
  const g = node('g');
  const f = `400 13px ${BODY}`, fh = `600 12px ${BODY}`;
  const colW = model.head.slice(1).map((h, i) => Math.max(tw(h, fh), ...model.rows.map((r) => tw(r.cells[i], f))) + 22);
  const labelW = Math.max(160, width - colW.reduce((a, b) => a + b, 0));
  let y = 0;
  const rowH = 30;
  g.appendChild(node('line', { x1: 0, x2: width, y1: y, y2: y, stroke: C.ruleStrong }));
  y += 20;
  let x = labelW;
  model.head.slice(1).forEach((h, i) => { x += colW[i]; g.appendChild(node('text', { x: x - 4, y, 'text-anchor': 'end', 'font-family': BODY, 'font-weight': 600, 'font-size': 12, fill: C.slate }, h)); });
  y += 10;
  g.appendChild(node('line', { x1: 0, x2: width, y1: y, y2: y, stroke: C.ruleStrong }));
  for (const r of model.rows) {
    y += rowH;
    const label = wrap(r.label + (r.flag ? ` (${r.flag})` : ''), f, labelW - 12)[0];
    g.appendChild(node('text', { x: 0, y: y - 10, 'font-family': BODY, 'font-size': 13, fill: C.ink }, label));
    let cx = labelW;
    r.cells.forEach((cell, i) => { cx += colW[i]; g.appendChild(node('text', { x: cx - 4, y: y - 10, 'text-anchor': model.numeric[i] ? 'end' : 'end', 'font-family': BODY, 'font-size': 13, fill: C.ink, style: 'font-variant-numeric: tabular-nums' }, cell)); });
    g.appendChild(node('line', { x1: 0, x2: width, y1: y, y2: y, stroke: C.rule }));
  }
  return { g, height: y + 4 };
}

/**
 * bundle: the chart bundle. layout: what the renderer returned ({svg,width,height} or
 * {multi} or {table}). opts.dryRun returns {width,height,bytes} instead of saving.
 */
export async function exportPNG(bundle, layout, { legend = [], pageUrl = '', dryRun = false } = {}) {
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  const fontCSS = await embeddedFonts();
  const pad = 36;
  const chartW = layout && layout.width ? layout.width : 760;
  const W = Math.max(680, Math.min(1200, chartW + pad * 2));
  const inner = W - pad * 2;
  const root = node('svg', { xmlns: SVGNS, width: W, viewBox: null });
  const style = node('style');
  style.textContent = fontCSS;
  root.appendChild(style);
  const bg = node('rect', { x: 0, y: 0, width: W, fill: C.paper });
  root.appendChild(bg);

  let y = pad;
  if (bundle.kicker) {
    y += 11;
    root.appendChild(node('text', { x: pad, y, 'font-family': BODY, 'font-weight': 700, 'font-size': 11, 'letter-spacing': '2.2', fill: C.slate }, String(bundle.kicker).toUpperCase()));
    y += 12;
  }
  root.appendChild(markSVG(W - pad - 30, pad - 6, 30));
  const tFont = `800 28px ${DISPLAY}`;
  for (const line of wrap(bundle.title, tFont, inner - 48)) {
    y += 32;
    root.appendChild(node('text', { x: pad, y, 'font-family': DISPLAY, 'font-weight': 800, 'font-size': 28, 'letter-spacing': '-0.8', fill: C.ink }, line));
  }
  y += 16;
  root.appendChild(node('rect', { x: pad, y, width: 52, height: 5, rx: 2.5, fill: C.amber }));
  y += 5 + 8;
  if (bundle.subtitle) {
    for (const line of wrap(bundle.subtitle, `400 15px ${BODY}`, inner)) {
      y += 21;
      root.appendChild(node('text', { x: pad, y, 'font-family': BODY, 'font-size': 15, fill: C.slate }, line));
    }
  }
  if (legend.length) {
    y += 14;
    let x = pad;
    const lf = `600 12px ${BODY}`;
    y += 14;
    for (const l of legend) {
      const w = 18 + tw(l.label, lf) + 18;
      if (x + w > W - pad && x > pad) { x = pad; y += 20; }
      const sw = l.shape === 'bar' ? node('rect', { x, y: y - 9, width: 10, height: 10, rx: 2, fill: l.color })
        : l.shape === 'band' ? node('rect', { x, y: y - 9, width: 14, height: 10, fill: l.color, 'fill-opacity': 0.18 })
          : l.shape === 'dot' ? node('circle', { cx: x + 5, cy: y - 4, r: 4, fill: l.color })
            : node('rect', { x, y: y - 6, width: 14, height: 4, rx: 2, fill: l.color });
      root.appendChild(sw);
      root.appendChild(node('text', { x: x + (l.shape === 'line' || l.shape === 'band' ? 20 : 16), y, 'font-family': BODY, 'font-weight': 600, 'font-size': 12, fill: C.ink }, l.label));
      x += w;
    }
  }
  y += 18;

  // The chart itself.
  const cx = pad + Math.max(0, (inner - chartW) / 2);
  if (layout && layout.svg) {
    root.appendChild(cloneChart(layout.svg, cx, y));
    y += layout.height;
  } else if (layout && layout.multi) {
    const { parts, pw, ph, gap } = layout.multi;
    for (const p of parts) {
      const px = cx + p.col * (pw + gap);
      const py = y + p.row * (ph + 30);
      root.appendChild(node('text', { x: px, y: py + 13, 'font-family': DISPLAY, 'font-weight': 700, 'font-size': 13, fill: C.ink }, p.label));
      root.appendChild(node('text', { x: px + pw, y: py + 13, 'text-anchor': 'end', 'font-family': DISPLAY, 'font-weight': 700, 'font-size': 13, fill: p.color }, p.value));
      root.appendChild(cloneChart(p.svg, px, py + 22));
    }
    const rows = Math.max(...parts.map((p) => p.row)) + 1;
    y += rows * (ph + 30);
  } else if (layout && layout.table) {
    const { tableModel } = await import('./charts.js');
    const t = tableSVG(bundle, tableModel(bundle), inner);
    t.g.setAttribute('transform', `translate(${pad},${y})`);
    root.appendChild(t.g);
    y += t.height;
  }

  // Source and credit.
  y += 22;
  root.appendChild(node('line', { x1: pad, x2: W - pad, y1: y - 12, y2: y - 12, stroke: C.rule }));
  const flags = new Set();
  for (const s of bundle.series || []) for (const f of Object.values(s.flags || {})) if (f) flags.add(f);
  if (bundle.latest && bundle.latest.flag) flags.add(bundle.latest.flag);
  const srcText = `Source: ${bundle.source || 'not stated'}.${bundle.notes ? ' ' + bundle.notes : ''}${flags.size ? ' ' + [...flags].map((f) => `${f} = ${flagLabel(f)}`).join(', ') + '.' : ''}`;
  for (const line of wrap(srcText, `400 12px ${BODY}`, inner)) {
    y += 4;
    root.appendChild(node('text', { x: pad, y, 'font-family': BODY, 'font-size': 12, fill: C.mute }, line));
    y += 13;
  }
  y += 8;
  root.appendChild(node('text', { x: pad, y, 'font-family': DISPLAY, 'font-weight': 700, 'font-size': 13, fill: C.ink }, 'European Economy Tracker'));
  const by = tw('European Economy Tracker', `700 13px ${DISPLAY}`);
  root.appendChild(node('text', { x: pad + by + 6, y, 'font-family': BODY, 'font-size': 12, fill: C.slate }, 'by Popular Economics'));
  if (pageUrl) {
    const u = pageUrl.replace(/^https?:\/\//, '').replace(/\?.*$/, '');
    root.appendChild(node('text', { x: W - pad, y, 'text-anchor': 'end', 'font-family': BODY, 'font-size': 12, fill: C.mute }, u));
  }
  const H = Math.ceil(y + pad - 8);
  root.setAttribute('height', H);
  root.setAttribute('viewBox', `0 0 ${W} ${H}`);
  bg.setAttribute('height', H);

  const str = new XMLSerializer().serializeToString(root);
  const url = URL.createObjectURL(new Blob([str], { type: 'image/svg+xml;charset=utf-8' }));
  try {
    const img = new Image();
    img.decoding = 'sync';
    await new Promise((res, rej) => { img.onload = res; img.onerror = () => rej(new Error('SVG did not load as an image')); img.src = url; });
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = W * scale;
    canvas.height = H * scale;
    const c2 = canvas.getContext('2d');
    c2.scale(scale, scale);
    c2.drawImage(img, 0, 0, W, H);
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
    if (!blob) throw new Error('canvas produced no PNG');
    if (dryRun) return { width: W * scale, height: H * scale, bytes: blob.size, svgBytes: str.length, dataURL: canvas.toDataURL('image/png') };
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${bundle.id}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    return { width: W * scale, height: H * scale, bytes: blob.size };
  } finally {
    URL.revokeObjectURL(url);
  }
}

export { esc };
