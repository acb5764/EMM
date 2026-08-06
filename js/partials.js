function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('emrTheme', theme);
  document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
    btn.textContent = theme === 'light' ? '🌙 Dark' : '☀️ Light';
    btn.setAttribute('aria-label', theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
  });
}

function currentTheme() {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

class SiteHeader extends HTMLElement {
  connectedCallback() {
    const current = document.body.dataset.page || '';
    const navItem = (href, label, page, extra = '') => {
      const isCurrent = page === current ? ' aria-current="page"' : '';
      return `<a href="${href}"${isCurrent}>${label}${extra}</a>`;
    };

    this.innerHTML = `
      <div class="header-inner">
        <a href="index.html" class="brand">
          <img src="images/site/logo.jpg" alt="Earth Mother Mango" class="brand-logo">
          <span>Em_R_Mangoes</span>
        </a>
        <div class="header-actions">
          <button type="button" class="theme-toggle" data-theme-toggle></button>
          <button type="button" class="nav-toggle" aria-label="Toggle navigation" aria-expanded="false">☰</button>
        </div>
        <nav class="site-nav">
          ${navItem('index.html', 'Home', 'home')}
          ${navItem('about.html', 'About', 'about')}
          ${navItem('catalog.html', 'Catalog', 'catalog')}
          ${navItem('request.html', 'Request to Buy', 'request', ' <span class="cart-badge" data-cart-badge hidden>0</span>')}
          ${navItem('contact.html', 'Contact', 'contact')}
        </nav>
      </div>`;

    const toggle = this.querySelector('.nav-toggle');
    const nav = this.querySelector('.site-nav');
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });

    const themeBtn = this.querySelector('[data-theme-toggle]');
    applyTheme(currentTheme());
    themeBtn.addEventListener('click', () => {
      applyTheme(currentTheme() === 'light' ? 'dark' : 'light');
    });

    if (typeof updateCartBadge === 'function') updateCartBadge();
  }
}
customElements.define('site-header', SiteHeader);

class SiteFooter extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="footer-inner">
        <p><strong>Em_R_Mangoes</strong> — Grown here, prepared here, and enjoyed by all!</p>
        <p>3555 Tadlock Avenue, Malabar, FL &middot; <a href="tel:13042791714">304-279-1714</a> &middot; <a href="mailto:Em.r.mangos@gmail.com">Em.r.mangos@gmail.com</a></p>
        <p class="footer-note">By appointment only. &copy; <span data-year></span> Em_R_Mangoes.</p>
      </div>`;
    this.querySelector('[data-year]').textContent = String(new Date().getFullYear());
  }
}
customElements.define('site-footer', SiteFooter);
