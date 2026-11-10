// Section pages, driven entirely by index.json: page header, section blocks (one grid of
// charts and tables per section), "Coming soon" for empty pages and sections, "Not updated" for
// anything listed in index.failed.

import { loadIndex, loadChart, PAGES, href } from './config.js';
import { esc } from './format.js';
import { setStamp } from './chrome.js';

const chartsModule = () => import('./charts.js');

export function pageHeader(main, { kicker, title, lede, sections = [] }) {
  const head = document.createElement('header');
  head.className = 'page-head wrap';
  head.innerHTML = `
    <p class="kicker">${esc(kicker)}</p>
    <h1>${esc(title)}</h1>
    <div class="amber-rule" aria-hidden="true"></div>
    ${lede ? `<p class="lede">${esc(lede)}</p>` : ''}
    <p class="stamp" data-eet="stamp"></p>
    ${sections.length > 1 ? `<nav class="section-jump" aria-label="On this page"><ul>${sections.map((s) => `<li><a href="#${esc(s.id)}">${esc(s.title)}</a></li>`).join('')}</ul></nav>` : ''}`;
  main.appendChild(head);
  return head;
}

export function failedLookup(index) {
  const map = new Map();
  for (const f of (index && index.failed) || []) {
    if (!f) continue;
    if (f.id) map.set(f.id, f);
    for (const c of f.chart_ids || []) map.set(c, f);
  }
  return (bundle) => map.get(bundle.id) || (bundle.methods_id && map.get(bundle.methods_id)) || null;
}

export function comingSoon(main, text = 'This page is coming soon. The charts are being built and will appear here after a future update.') {
  const p = document.createElement('div');
  p.className = 'wrap coming-soon';
  p.innerHTML = `<p class="kicker">Coming soon</p><p>${esc(text)}</p>`;
  main.appendChild(p);
}

export function indexError(main, err) {
  const box = document.createElement('div');
  box.className = 'wrap coming-soon';
  const missing = err && err.status === 404;
  box.innerHTML = missing
    ? `<p class="kicker">No data yet</p><p>The data for this site have not been built yet. They appear here after the next automatic run.</p>`
    : `<p class="kicker">Something went wrong</p><p>The data could not be loaded. Try again in a minute.</p>`;
  main.appendChild(box);
  (missing ? console.warn : console.error)('[eet] index.json:', err && err.message);
}

/** Render one chart id into a figure, with skeleton, failure and missing states. */
export async function mountChart(fig, id, index, isFailed, opts = {}) {
  const charts = await chartsModule();
  charts.skeletonFigure(fig, opts);
  fig.id = id;
  try {
    const bundle = await loadChart(id, index);
    charts.renderChart(fig, bundle, { ...opts, failed: isFailed(bundle) });
    return bundle;
  } catch (e) {
    charts.unavailableFigure(fig, id, e);
    console.warn(`[eet] chart ${id}:`, e.message || e);
    return null;
  }
}

export async function renderPage(pageId, main) {
  const fallback = PAGES.find((p) => p.id === pageId) || { title: pageId };
  let index;
  try {
    index = await loadIndex();
  } catch (e) {
    pageHeader(main, { kicker: 'European Economy Tracker', title: fallback.title });
    indexError(main, e);
    return;
  }
  setStamp(index.built_at);
  const page = (index.pages || []).find((p) => p.id === pageId);
  const sections = (page && page.sections) || [];
  const hasContent = sections.some((s) => (s.charts || []).length || (s.tables || []).length);
  document.title = `${page ? page.title : fallback.title} · European Economy Tracker`;
  pageHeader(main, {
    kicker: 'European Economy Tracker',
    title: page ? page.title : fallback.title,
    lede: page && page.description,
    sections: hasContent ? sections : [],
  });
  setStamp(index.built_at);
  if (!hasContent) { comingSoon(main); return; }

  const isFailed = failedLookup(index);
  const jobs = [];
  for (const sec of sections) {
    const block = document.createElement('section');
    block.className = 'block wrap';
    block.id = sec.id;
    block.setAttribute('aria-labelledby', `${sec.id}-h`);
    const charts = sec.charts || [];
    const tables = sec.tables || [];
    block.innerHTML = `
      <header class="block-head">
        <h2 id="${esc(sec.id)}-h">${esc(sec.title)} <a class="anchor" href="#${esc(sec.id)}" aria-label="Link to ${esc(sec.title)}">#</a></h2>
        ${sec.intro ? `<p class="intro">${esc(sec.intro)}</p>` : ''}
      </header>`;
    main.appendChild(block);
    if (!charts.length && !tables.length) {
      const p = document.createElement('p');
      p.className = 'section-soon';
      p.textContent = 'Charts for this section are coming soon.';
      block.appendChild(p);
      continue;
    }
    // One grid per section: charts and tables flow together in two columns on wide screens.
    // Order: the lead chart, the tables, then the other charts. Long tables, heatmaps and
    // country strips span both columns; once everything is drawn, arrangeGrid() pairs the
    // half-width items so no column is left with a hole beside a tall neighbour.
    const grid = document.createElement('div');
    grid.className = 'chart-grid';
    block.appendChild(grid);
    const order = charts.length ? [charts[0], ...tables, ...charts.slice(1)] : tables;
    const secJobs = order.map((id) => {
      const fig = document.createElement('figure');
      grid.appendChild(fig);
      return mountChart(fig, id, index, isFailed).then((b) => {
        if (b && b.type === 'table' && isWideTable(b)) fig.classList.add('chart--wide');
        return b;
      });
    });
    jobs.push(Promise.all(secJobs).then(() => arrangeGrid(grid)));
  }
  await Promise.all(jobs);
  scrollToHash();
}

/** A table too long or too wide to sit beside a chart gets the full row. */
export function isWideTable(b) {
  return (b.rows || []).length > 12 || (b.columns || []).length > 6;
}

/**
 * Reorder a section grid so half-width items come in pairs: a full-width item met while one
 * half-width item waits for a partner is held back until the pair is complete. A half-width
 * item left without a partner takes the full row (.is-solo). Order is preserved otherwise.
 */
export function arrangeGrid(grid) {
  const items = [...grid.children];
  const wide = (n) => n.classList.contains('chart--wide');
  const out = [];
  let pending = null;
  let held = [];
  for (const n of items) {
    n.classList.remove('is-solo');
    if (wide(n)) {
      if (pending) held.push(n); else out.push(n);
    } else if (pending) {
      out.push(pending, n, ...held);
      pending = null; held = [];
    } else {
      pending = n;
    }
  }
  if (pending) { pending.classList.add('is-solo'); out.push(pending, ...held); }
  out.forEach((n) => grid.appendChild(n));
}

/** Content arrives after the browser's own jump, so redo it once everything is drawn. */
export function scrollToHash() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id) return;
  const t = document.getElementById(id);
  if (!t) return;
  // :target does not match elements inserted after load, so mark it ourselves.
  document.querySelectorAll('.is-target').forEach((n) => n.classList.remove('is-target'));
  t.classList.add('is-target');
  requestAnimationFrame(() => t.scrollIntoView({ block: 'start' }));
}
