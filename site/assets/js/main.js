// Entry point for every page. The page id comes from <body data-page="...">.

import { renderChrome, setStamp } from './chrome.js';
import { loadIndex } from './config.js';

const pageId = document.body.dataset.page || 'home';
renderChrome(pageId);
const main = document.getElementById('main');

async function run() {
  if (pageId === 'home') return (await import('./home.js')).renderHome(main);
  if (pageId === 'methods') return (await import('./methods.js')).renderMethods(main);
  if (pageId === 'calendar') return (await import('./calendar.js')).renderCalendar(main);
  if (pageId === 'about') {
    try { setStamp((await loadIndex()).built_at); } catch { /* static page */ }
    return;
  }
  return (await import('./page.js')).renderPage(pageId, main);
}

run().catch((e) => console.error('[eet] page failed to render', e));
