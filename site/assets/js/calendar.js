// Release calendar: data/calendar.json grouped by day, with a Today marker.

import { loadIndex, fetchJSON, href } from './config.js';
import { esc, todayBrussels, weekdayLong } from './format.js';
import { setStamp } from './chrome.js';
import { pageHeader } from './page.js';

const TIER = { 1: 'Major release', 2: 'Release', 3: 'Minor release' };

export async function renderCalendar(main) {
  pageHeader(main, {
    kicker: 'European Economy Tracker',
    title: 'Calendar',
    lede: 'What comes out next, and when. Times are Brussels time; the charts update shortly after each release.',
  });
  let index = null;
  try { index = await loadIndex(); setStamp(index.built_at); } catch { /* calendar can stand alone */ }
  const chartPage = new Map();
  for (const p of (index && index.pages) || []) for (const s of p.sections || []) for (const id of [...(s.charts || []), ...(s.tables || [])]) chartPage.set(id, p.id);

  const body = document.createElement('div');
  body.className = 'wrap calendar';
  main.appendChild(body);
  let cal;
  try { cal = await fetchJSON('calendar.json', { version: index && index.built_at }); } catch {
    body.innerHTML = '<div class="coming-soon"><p class="kicker">Coming soon</p><p>Calendar coming soon. Release dates appear here once the calendar is built.</p></div>';
    return;
  }
  const today = todayBrussels();
  const byDay = new Map();
  for (const e of (cal.events || []).slice().sort((a, b) => (a.date + (a.time || '')).localeCompare(b.date + (b.time || '')))) {
    if (!byDay.has(e.date)) byDay.set(e.date, []);
    byDay.get(e.date).push(e);
  }
  if (!byDay.has(today)) byDay.set(today, []);
  const days = [...byDay.keys()].sort();
  if (!(cal.events || []).length) {
    body.innerHTML = '<div class="coming-soon"><p>No releases are scheduled in the next few weeks.</p></div>';
    return;
  }
  body.innerHTML = `<ol class="cal-days">${days.map((d) => {
    const isToday = d === today;
    const past = d < today;
    const events = byDay.get(d);
    return `<li class="cal-day${isToday ? ' is-today' : ''}${past ? ' is-past' : ''}" id="d-${d}">
      <h2 class="cal-date">${isToday ? '<span class="today-mark">Today</span> ' : ''}${esc(weekdayLong(d))}</h2>
      ${events.length ? `<ul class="cal-events">${events.map((e) => {
        const links = (e.chart_ids || []).filter((id) => chartPage.has(id));
        return `<li class="cal-event tier-${e.tier || 3}">
          <span class="cal-time">${esc(e.time || '')}</span>
          <span class="cal-what">
            <span class="cal-title">${esc(e.title)}</span>
            <span class="cal-meta">${esc(e.publisher || '')}${e.tier ? ` · ${esc(TIER[e.tier] || `Tier ${e.tier}`)}` : ''}${links.length ? ` · ${links.map((id, i) => `<a href="${href(chartPage.get(id), id)}">${i === 0 ? 'See the chart' : `chart ${i + 1}`}</a>`).join(', ')}` : ''}</span>
          </span>
        </li>`;
      }).join('')}</ul>` : '<p class="cal-none">No releases scheduled.</p>'}
    </li>`;
  }).join('')}</ol>`;
  const t = body.querySelector('.is-today');
  if (t && !location.hash) requestAnimationFrame(() => t.scrollIntoView({ block: 'center' }));
}
