/* ============================================================
   NAVIGATION — injected into <div id="nav-root">
   ============================================================ */
const NAV_LINKS = [
  { href: 'index.html',        label: 'Home',         page: 'home' },
  { href: 'research.html',     label: 'Research',     page: 'research' },
  { href: 'publications.html', label: 'Publications', page: 'publications' },
  { href: 'projects.html',     label: 'Projects',     page: 'projects' },
  { href: 'skills.html',       label: 'Skills',       page: 'skills' },
  { href: 'cv.html',           label: 'CV',           page: 'cv' },
];

function buildNav() {
  const root = document.getElementById('nav-root');
  if (!root) return;

  const currentPage = document.body.dataset.page || '';

  const linksHtml = NAV_LINKS.map(l =>
    `<a href="${l.href}" class="${l.page === currentPage ? 'active' : ''}">${l.label}</a>`
  ).join('');

  const mobileLinksHtml = NAV_LINKS.map(l =>
    `<a href="${l.href}" class="${l.page === currentPage ? 'active' : ''}">${l.label}</a>`
  ).join('');

  root.innerHTML = `
    <nav>
      <div class="nav-inner">
        <a href="index.html" class="nav-brand">Elaine Zhelan Chen</a>
        <div class="nav-right">
          <div class="nav-links">${linksHtml}</div>
          <button class="dark-toggle" aria-label="Toggle dark mode">
            <svg class="icon-moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
            <svg class="icon-sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          </button>
          <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false">
            <span></span><span></span><span></span>
          </button>
        </div><!-- /.nav-right -->
      </div>
    </nav>
    <div class="nav-mobile" id="nav-mobile">${mobileLinksHtml}</div>
  `;

  const toggle = root.querySelector('.nav-toggle');
  const mobile = document.getElementById('nav-mobile');

  function openMenu()  { mobile.classList.add('open');    toggle.setAttribute('aria-expanded', 'true'); }
  function closeMenu() { mobile.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }

  toggle.addEventListener('click', () =>
    mobile.classList.contains('open') ? closeMenu() : openMenu()
  );
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
  document.addEventListener('click',   e => { if (!root.contains(e.target)) closeMenu(); });
  mobile.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
}

/* ============================================================
   FOOTER — injected into <div id="footer-root">
   ============================================================ */
function buildFooter() {
  const root = document.getElementById('footer-root');
  if (!root) return;

  root.innerHTML = `
    <footer>
      <div class="footer-links">
        <a href="mailto:zchen119@jhu.edu">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-label="Email">
            <rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
          </svg>
          zchen119@jhu.edu
        </a>
        <a href="https://www.linkedin.com/in/zhelan-elaine-chen" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor" aria-label="LinkedIn">
            <path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/>
          </svg>
          LinkedIn
        </a>
      </div>
      <p class="footer-copy">© 2026 Elaine Zhelan Chen</p>
    </footer>
  `;
}

/* ============================================================
   DARK MODE — toggle + localStorage persistence
   ============================================================ */
function initDarkMode() {
  // Apply saved preference before paint
  let dark = false;
  try { dark = localStorage.getItem('dark_mode') === '1'; } catch(e) {}
  if (dark) document.body.classList.add('dark');

  // Wire toggle button (injected by buildNav, so it's available now)
  const btn = document.querySelector('.dark-toggle');
  if (!btn) return;

  btn.addEventListener('click', () => {
    const isDark = document.body.classList.toggle('dark');
    try { localStorage.setItem('dark_mode', isDark ? '1' : '0'); } catch(e) {}
  });
}

/* ============================================================
   INIT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  buildNav();
  buildFooter();
  initDarkMode();
});
