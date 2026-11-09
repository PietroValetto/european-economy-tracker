// Home: product header, the 12-tile key-indicator strip, the next releases, and one teaser
// per page (that page's first chart and a link).

import { loadIndex, fetchJSON, PAGES, href } from './config.js';
import { esc, fmtNum, inferDecimals, periodLabel, flagLabel, todayBrussels, fmtDay } from './format.js';
import { setStamp } from './chrome.js';
import { failedLookup, mountChart, indexError, scrollToHash } from './page.js';

function hero(main) {
  const head = document.createElement('header');
  head.className = 'page-head home-head wrap';
  head.innerHTML = `
    <p class="kicker">By Popular Economics</p>
    <h1>European Economy Tracker</h1>
    <div class="amber-rule" aria-hidden="true"></div>
    <p class="lede">Your prices, your pay, your mortgage rate: the euro area economy in plain charts, rebuilt every time the official numbers come out.</p>
    <p class="stamp" data-eet="stamp"></p>`;
  main.appendChild(head);
}

function tile(item) {
  const dec = Number.isInteger(item.decimals) ? item.decimals : Math.max(inferDecimals(item.value), inferDecimals(item.previous));
  const v = fmtNum(item.value, dec);
  let arrow = '', cls = 'is-flat', change = '';
  if (item.previous != null && item.value != null) {
    const same = fmtNum(item.previous, dec) === v;
    const up = item.value > item.previous;
    if (same) { arrow = '→'; change = 'unchanged'; }
    else {
      arrow = up ? '↑' : '↓';
      change = `from ${fmtNum(item.previous, dec)}`;
      const gd = item.good_direction;
      cls = gd === 'up' ? (up ? 'is-good' : 'is-bad') : gd === 'down' ? (up ? 'is-bad' : 'is-good') : 'is-neutral';
    }
  }
  const dir = arrow === '↑' ? 'up' : arrow === '↓' ? 'down' : 'no change';
  const target = item.chart_id ? href(item.page, item.chart_id) : href(item.page);
  const unit = item.unit || '';
  const sr = `${item.label}: ${v} ${unit}${item.flag ? ` (${flagLabel(item.flag)})` : ''}, ${periodLabel(item.period)}. ${dir === 'no change' ? 'Unchanged' : `${dir === 'up' ? 'Up' : 'Down'} from ${fmtNum(item.previous, dec)}`}.`;
  return `<li><a class="tile" href="${target}" aria-label="${esc(sr)}">
      <span class="tile-label">${esc(item.label)}</span>
      <span class="tile-figure"><span class="tile-num">${esc(v)}</span>${item.flag ? `<sup class="flag" title="${esc(flagLabel(item.flag))}">${esc(item.flag)}</sup>` : ''}<span class="tile-unit">${esc(unit)}</span></span>
      <span class="tile-meta"><span class="tile-change ${cls}">${arrow ? `<span class="tile-arrow" aria-hidden="true">${arrow}</span> ` : ''}${esc(change)}</span><span class="tile-period">${esc(periodLabel(item.period))}</span></span>
    </a></li>`;
}

function strip(main, index) {
  const items = index.strip || [];
  if (!items.length) return;
  const sec = document.createElement('section');
  sec.className = 'strip wrap';
  sec.setAttribute('aria-labelledby', 'strip-h');
  const flags = [...new Set(items.map((i) => i.flag).filter(Boolean))];
  sec.innerHTML = `
    <div class="strip-head"><h2 id="strip-h" class="kicker">Key indicators</h2><p class="strip-note">Euro area, latest reading. Arrows compare with the reading before; green is the direction you would want.</p></div>
    <ul class="tiles">${items.map(tile).join('')}</ul>
    ${flags.length ? `<p class="chart-note"><span class="flag-key">${flags.map((f) => `<b>${esc(f)}</b> ${esc(flagLabel(f))}`).join(' · ')}</span></p>` : ''}`;
  main.appendChild(sec);
}

async function comingUp(main, index) {
  let cal;
  try { cal = await fetchJSON('calendar.json', { version: index.built_at }); } catch { return; }
  const today = todayBrussels();
  const next = (cal.events || []).filter((e) => e.date >= today && (e.tier || 3) <= 2)
    .sort((a, b) => (a.date + (a.time || '')).localeCompare(b.date + (b.time || ''))).slice(0, 4);
  if (!next.length) return;
  const sec = document.createElement('section');
  sec.className = 'coming-up wrap';
  sec.setAttribute('aria-labelledby', 'cu-h');
  sec.innerHTML = `<h2 id="cu-h" class="kicker">Coming up</h2>
    <ul>${next.map((e) => `<li><span class="cu-date">${e.date === today ? 'Today' : esc(fmtDay(e.date).replace(/ \d{4}$/, ''))}</span> <span class="cu-title">${esc(e.title)}</span> <span class="cu-pub">${esc(e.publisher || '')}</span></li>`).join('')}</ul>
    <a class="more" href="${href('calendar')}">Full calendar →</a>`;
  const after = main.querySelector('.strip');
  if (after) after.after(sec); else main.appendChild(sec);
}

export async function renderHome(main) {
  hero(main);
  let index;
  try { index = await loadIndex(); } catch (e) { indexError(main, e); return; }
  setStamp(index.built_at);
  strip(main, index);
  comingUp(main, index);

  const isFailed = failedLookup(index);
  const wrap = document.createElement('section');
  wrap.className = 'teasers wrap';
  wrap.setAttribute('aria-label', 'Pages');
  main.appendChild(wrap);
  const jobs = [];
  for (const p of PAGES.filter((x) => x.data)) {
    const page = (index.pages || []).find((x) => x.id === p.id);
    const title = page ? page.title : p.title;
    const first = page && (page.sections || []).flatMap((s) => s.charts || [])[0];
    const block = document.createElement('article');
    block.className = 'teaser';
    block.innerHTML = `
      <header class="teaser-head">
        <h2><a href="${href(p.id)}">${esc(title)}</a></h2>
        ${page && page.description ? `<p>${esc(page.description)}</p>` : ''}
      </header>`;
    wrap.appendChild(block);
    if (first) {
      const fig = document.createElement('figure');
      block.appendChild(fig);
      jobs.push(mountChart(fig, first, index, isFailed, { compact: true }));
      const more = document.createElement('a');
      more.className = 'more';
      more.href = href(p.id);
      more.textContent = `All ${title} charts →`;
      block.appendChild(more);
    } else {
      const soon = document.createElement('p');
      soon.className = 'section-soon';
      soon.textContent = 'Coming soon.';
      block.appendChild(soon);
    }
  }
  await Promise.all(jobs);
  scrollToHash();
}
