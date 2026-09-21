/* UAE Premium Numbers — premium scroll reveal + micro-interactions
   Adds .is-visible to elements with .reveal as they enter viewport.
   Marks plan/pricing cards and section headings as reveal targets if they
   don't already have the class — zero-config enhancement. */
(function () {
  'use strict';

  if (typeof window === 'undefined' || !('IntersectionObserver' in window)) return;

  const SELECTORS = [
    '.section-heading',
    '.plan-card',
    '.pricing-card',
    '.intent-btn',
    'section h2',
    'section h3',
    '.trust-badges > div > div',
    '[data-reveal]'
  ];

  function autoTagReveal() {
    SELECTORS.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (!el.classList.contains('reveal')) el.classList.add('reveal');
      });
    });
  }

  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  });

  function init() {
    autoTagReveal();
    document.querySelectorAll('.reveal').forEach(function (el) {
      observer.observe(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

/* 2026-09-21 Floating WhatsApp button on every page that loads this file.
   Same look and data-cta as the hand-built .wa-fab on /choose-number/, so Ref codes read FLOATINGFAB everywhere.
   Skipped where a page already has one (.wa-fab) or a sticky WhatsApp bar (.sticky-cta on number pages).
   Sits above the Tawk.to bubble on pages that load Tawk (home, /ar/) instead of covering it.
   Click tracking: tracking.js's global wa.me auto-wire adds the Ref; this reports the GA/Meta Contact once. */
(function () {
  'use strict';
  if (typeof document === 'undefined') return;

  var ICON = 'M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z';

  function addFloat() {
    if (document.getElementById('upn-wa-float') || document.querySelector('.wa-fab, .sticky-cta')) return;
    var arabic = (document.documentElement.lang || '').toLowerCase().indexOf('ar') === 0;
    var title = (document.title || '').split('|')[0].trim().slice(0, 90);
    var msg = arabic ? 'مرحبا، لدي سؤال عن: ' + title : 'Hi, I have a question about: ' + title;
    var tawk = !!(window.Tawk_API || document.querySelector('script[src*="tawk.to"]'));
    var lift = tawk ? 84 : 0;

    var css = document.createElement('style');
    css.textContent =
      '#upn-wa-float{position:fixed!important;right:22px;bottom:calc(' + (22 + lift) + 'px + env(safe-area-inset-bottom,0px));z-index:9998;' +
      'width:60px;height:60px;border-radius:50%;background:#25D366;display:flex;align-items:center;justify-content:center;' +
      'box-shadow:0 4px 14px rgba(0,0,0,.35);animation:upnWaPulse 2.4s ease-out infinite;transition:transform .15s ease}' +
      '#upn-wa-float:hover{transform:scale(1.08);animation-play-state:paused}' +
      '#upn-wa-float svg{width:32px;height:32px;fill:#fff}' +
      '@keyframes upnWaPulse{0%{box-shadow:0 4px 14px rgba(0,0,0,.35),0 0 0 0 rgba(37,211,102,.55)}' +
      '70%{box-shadow:0 4px 14px rgba(0,0,0,.35),0 0 0 18px rgba(37,211,102,0)}100%{box-shadow:0 4px 14px rgba(0,0,0,.35),0 0 0 0 rgba(37,211,102,0)}}' +
      '@media (max-width:600px){#upn-wa-float{width:56px;height:56px;right:16px;bottom:calc(' + (16 + lift) + 'px + env(safe-area-inset-bottom,0px))}}' +
      '@media (prefers-reduced-motion:reduce){#upn-wa-float{animation:none}}' +
      '@media print{#upn-wa-float{display:none}}';
    document.head.appendChild(css);

    var a = document.createElement('a');
    a.id = 'upn-wa-float';
    a.href = 'https://wa.me/971569028087?text=' + encodeURIComponent(msg);
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.setAttribute('data-cta', 'floating_fab');
    a.setAttribute('aria-label', arabic ? 'تواصل عبر واتساب' : 'Chat on WhatsApp');
    a.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + ICON + '"/></svg>';
    a.addEventListener('click', function () {
      if (window.GN && window.GN.trackWhatsAppClick) window.GN.trackWhatsAppClick('Floating WhatsApp', location.pathname);
    });
    document.body.appendChild(a);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addFloat);
  } else {
    addFloat();
  }
})();
