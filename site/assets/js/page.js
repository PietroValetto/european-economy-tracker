// Section pages, driven entirely by index.json: page header, section blocks (charts on the
// left, tables on the right), "Coming soon" for empty pages and sections, "Not updated" for
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
    // Charts left, tables right: the lead chart sits beside the section's tables.
    if (tables.length) {
      const lead = document.createElement('div');
      lead.className = 'lead-row';
      const left = document.createElement('div');
      left.className = 'lead-chart';
      const right = document.createElement('aside');
      right.className = 'lead-tables';
      lead.append(left, right);
      block.appendChild(lead);
      if (charts[0]) {
        const fig = document.createElement('figure');
        left.appendChild(fig);
        jobs.push(mountChart(fig, charts[0], index, isFailed));
      }
      for (const t of tables) {
        const fig = document.createElement('figure');
        right.appendChild(fig);
        jobs.push(mountChart(fig, t, index, isFailed));
      }
    }
    const rest = tables.length ? charts.slice(1) : charts;
    if (rest.length) {
      const grid = document.createElement('div');
      grid.className = 'chart-grid' + (rest.length === 1 ? ' is-single' : '');
      block.appendChild(grid);
      for (const id of rest) {
        const fig = document.createElement('figure');
        grid.appendChild(fig);
        jobs.push(mountChart(fig, id, index, isFailed));
      }
    }
  }
  await Promise.all(jobs);
  scrollToHash();
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
