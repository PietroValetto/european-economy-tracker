// Paths, page list and the cached data loader. Every URL is relative: the site lives
// under /european-economy-tracker/ on GitHub Pages.

const meta = document.querySelector('meta[name="eet-root"]');
export const ROOT = meta ? meta.getAttribute('content') : './';

const params = new URLSearchParams(location.search);
export const FIXTURES = params.get('fixtures') === '1';
export const DATA_BASE = ROOT + (FIXTURES ? '_fixtures/' : 'data/');

export const SUBSTACK = 'https://populareconomics.substack.com/';

// Fixed page order (CONTRACT section 4). Titles here are fallbacks; index.json wins.
export const PAGES = [
  { id: 'gdp', title: 'GDP', data: true },
  { id: 'labour', title: 'Labour', data: true },
  { id: 'wages', title: 'Wages', data: true },
  { id: 'inflation', title: 'Inflation', data: true },
  { id: 'financial', title: 'Financial', data: true },
  { id: 'ecb', title: 'ECB', data: true },
  { id: 'fiscal', title: 'Fiscal', data: true },
  { id: 'international', title: 'International', data: true },
  { id: 'europe', title: 'Europe', data: true },
  { id: 'calendar', title: 'Calendar' },
  { id: 'methods', title: 'Methods' },
  { id: 'about', title: 'About' },
];

/** Link to a page (and optional anchor), keeping ?fixtures=1 while developing. */
export function href(pageId, hash) {
  const path = !pageId || pageId === 'home' ? '' : `${pageId}/`;
  const q = FIXTURES ? '?fixtures=1' : '';
  return `${ROOT}${path}${q}${hash ? '#' + hash : ''}`;
}

const cache = new Map();

/** Fetch JSON relative to the data folder. Cached per URL for the life of the page. */
export function fetchJSON(rel, { version } = {}) {
  const url = DATA_BASE + rel + (version ? `?v=${encodeURIComponent(version)}` : '');
  if (!cache.has(url)) {
    const p = fetch(url, { cache: version ? 'default' : 'no-cache' }).then((r) => {
      if (!r.ok) {
        const err = new Error(`${r.status} ${r.statusText} for ${rel}`);
        err.status = r.status;
        throw err;
      }
      return r.json();
    });
    cache.set(url, p);
    p.catch(() => cache.delete(url));
  }
  return cache.get(url);
}

let indexPromise;
export function loadIndex() {
  if (!indexPromise) indexPromise = fetchJSON('index.json');
  return indexPromise;
}

export function loadChart(id, index) {
  return fetchJSON(`charts/${id}.json`, { version: index && index.built_at });
}
