// Methods register: data/methods.json as a searchable list with one anchor per entry.

import { loadIndex, fetchJSON, href } from './config.js';
import { esc, fmtDay } from './format.js';
import { setStamp } from './chrome.js';
import { pageHeader, scrollToHash } from './page.js';

export async function renderMethods(main) {
  pageHeader(main, {
    kicker: 'European Economy Tracker',
    title: 'Methods',
    lede: 'Where every number comes from, how it is calculated and what to watch out for. One entry per chart.',
  });
  let index = null;
  try { index = await loadIndex(); setStamp(index.built_at); } catch { /* methods still render */ }
  const chartPage = new Map();
  for (const p of (index && index.pages) || []) for (const s of p.sections || []) for (const id of [...(s.charts || []), ...(s.tables || [])]) chartPage.set(id, p.id);

  const body = document.createElement('div');
  body.className = 'wrap methods';
  main.appendChild(body);
  let data;
  try { data = await fetchJSON('methods.json', { version: index && index.built_at }); } catch (e) {
    body.innerHTML = '<div class="coming-soon"><p class="kicker">Coming soon</p><p>The methods register appears here after the next data build.</p></div>';
    return;
  }
  const entries = (data.entries || []).slice().sort((a, b) => String(a.title).localeCompare(String(b.title)));
  body.innerHTML = `
    <div class="methods-tools">
      <label class="search"><span class="sr-only">Search methods</span><input type="search" placeholder="Search: inflation, Eurostat, wages…" autocomplete="off"></label>
      <label class="check"><input type="checkbox" data-originals> Original measures only</label>
      <p class="methods-count" aria-live="polite"></p>
    </div>
    <div class="methods-list"></div>`;
  const list = body.querySelector('.methods-list');
  list.innerHTML = entries.map((e) => {
    const page = chartPage.get(e.id);
    const sources = (e.sources || []).map((s) => `${s.url ? `<a href="${esc(s.url)}" rel="noopener">${esc(s.dataset || s.name)}</a>` : esc(s.dataset || s.name)}`).join('; ');
    return `<article class="method" id="${esc(e.id)}" data-text="${esc([e.title, e.what, e.transform, e.caveats, e.frequency, ...(e.sources || []).flatMap((s) => [s.name, s.dataset])].join(' ').toLowerCase())}" data-original="${e.original ? 1 : 0}">
      <h2>${esc(e.title)}${e.original ? ' <span class="tag-original">Original</span>' : ''}</h2>
      <dl>
        ${e.what ? `<div><dt>What it shows</dt><dd>${esc(e.what)}</dd></div>` : ''}
        ${e.transform ? `<div><dt>How it is calculated</dt><dd>${esc(e.transform)}</dd></div>` : ''}
        ${sources ? `<div><dt>Source</dt><dd>${sources}</dd></div>` : ''}
        ${e.frequency ? `<div><dt>Frequency</dt><dd>${esc(e.frequency)}</dd></div>` : ''}
        ${e.caveats ? `<div><dt>Caveats</dt><dd>${esc(e.caveats)}</dd></div>` : ''}
        ${e.updated ? `<div><dt>Last updated</dt><dd>${esc(fmtDay(e.updated))}</dd></div>` : ''}
      </dl>
      ${page ? `<a class="more" href="${href(page, e.id)}">See the chart →</a>` : ''}
    </article>`;
  }).join('') + '<p class="methods-empty" hidden>Nothing matches that search.</p>';

  const input = body.querySelector('input[type="search"]');
  const orig = body.querySelector('[data-originals]');
  const count = body.querySelector('.methods-count');
  const empty = body.querySelector('.methods-empty');
  function filter() {
    const q = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let n = 0;
    list.querySelectorAll('.method').forEach((a) => {
      const ok = q.every((w) => a.dataset.text.includes(w)) && (!orig.checked || a.dataset.original === '1');
      a.hidden = !ok;
      if (ok) n++;
    });
    count.textContent = `Showing ${n} of ${entries.length} entries`;
    empty.hidden = n > 0;
  }
  input.addEventListener('input', filter);
  orig.addEventListener('change', filter);
  filter();
  scrollToHash();
  window.addEventListener('hashchange', scrollToHash);
}
