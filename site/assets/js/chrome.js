// Site header (brand, nav, mobile menu) and footer. Rendered from a constant so the
// navigation appears before any data has loaded.

import { PAGES, ROOT, SUBSTACK, FIXTURES, href } from './config.js';
import { esc, fmtStamp } from './format.js';

// Pietro's personal website: the tracker links back to it from the header, phone menu and footer.
export const PERSONAL_SITE = 'https://pietrovaletto.github.io/';

export const MARK_SVG = `<svg class="pe-mark" viewBox="0 0 100 100" aria-hidden="true" focusable="false"><g transform="translate(50,50) scale(0.75) translate(-50,-45)"><rect x="16" y="56" width="16" height="30" rx="8" fill="#1F8A5B"/><circle cx="24" cy="44" r="8" fill="#1F8A5B"/><rect x="42" y="40" width="16" height="46" rx="8" fill="#F0A93B"/><circle cx="50" cy="28" r="8" fill="#F0A93B"/><rect x="68" y="24" width="16" height="62" rx="8" fill="#1F8A5B"/><circle cx="76" cy="12" r="8" fill="#1F8A5B"/></g></svg>`;

export function renderChrome(pageId) {
  const header = document.querySelector('[data-eet="header"]') || document.body.insertBefore(document.createElement('header'), document.body.firstChild);
  header.className = 'site-header';
  header.setAttribute('data-eet', 'header');

  const links = PAGES.map((p) => {
    const cur = p.id === pageId ? ' aria-current="page"' : '';
    const cls = p.data ? 'nav-data' : 'nav-meta';
    return `<li class="${cls}"><a href="${href(p.id)}"${cur}>${esc(p.title)}</a></li>`;
  }).join('');

  header.innerHTML = `
    <a class="skip-link" href="#main">Skip to content</a>
    <div class="wrap header-row">
      <a class="brand" href="${href('home')}"${pageId === 'home' ? ' aria-current="page"' : ''}>
        ${MARK_SVG}
        <span class="brand-text"><span class="brand-name">European Economy Tracker</span><span class="brand-by">by Popular Economics</span></span>
      </a>
      <div class="header-actions">
        <a class="home-link" href="${PERSONAL_SITE}">Pietro Valetto <span aria-hidden="true">→</span></a>
        <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
      </div>
    </div>
    <nav id="site-nav" class="site-nav" aria-label="Pages">
      <ul class="wrap nav-list">${links}<li class="nav-meta nav-home"><a href="${PERSONAL_SITE}">Pietro Valetto's website →</a></li></ul>
    </nav>`;

  const btn = header.querySelector('.menu-toggle');
  const nav = header.querySelector('.site-nav');
  btn.addEventListener('click', () => {
    const open = btn.getAttribute('aria-expanded') !== 'true';
    btn.setAttribute('aria-expanded', String(open));
    btn.textContent = open ? 'Close' : 'Menu';
    nav.classList.toggle('is-open', open);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('is-open')) {
      btn.click();
      btn.focus();
    }
  });

  let footer = document.querySelector('[data-eet="footer"]');
  if (!footer) {
    footer = document.createElement('footer');
    document.body.appendChild(footer);
  }
  footer.className = 'site-footer';
  footer.setAttribute('data-eet', 'footer');
  footer.innerHTML = `
    <div class="wrap footer-inner">
      <div class="footer-brand">
        ${MARK_SVG}
        <p><strong>European Economy Tracker</strong> by <a href="${SUBSTACK}">Popular Economics</a></p>
      </div>
      <ul class="footer-links">
        <li><a href="${SUBSTACK}">Newsletter on Substack</a></li>
        <li><a href="${href('methods')}">Methods</a></li>
        <li><a href="${href('about')}">About</a></li>
        <li><a href="${PERSONAL_SITE}">Pietro Valetto's website</a></li>
      </ul>
      <p class="footer-note">Data: Eurostat, ECB, European Commission and others. Built automatically; may contain errors.</p>
      <p class="footer-stamp" data-eet="footer-stamp"></p>
    </div>`;
}

/** Fill every "as of" slot once index.json is in. */
export function setStamp(builtAt) {
  const text = builtAt ? `Data as of ${fmtStamp(builtAt)}` : '';
  document.querySelectorAll('[data-eet="stamp"], [data-eet="footer-stamp"]').forEach((el) => {
    el.textContent = text + (FIXTURES ? ' · development fixtures' : '');
    if (builtAt) el.setAttribute('title', builtAt);
  });
}

export { ROOT };
